"""Pruebas de la cuenta de Restream: conectar, desconectar y canales."""

import contextlib
import http.server
import json
import tempfile
import threading
import time
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest import mock

import httpx

from guyrapu.restream import api, cuenta, oauth, sesion
from guyrapu.youtube import credenciales
from tests.rutas_temporales import redirigir_rutas


ACCESO = "acceso-de-prueba"
RENOVACION = "renovacion-de-prueba"
CODIGO = "codigo-de-prueba"


class _ServicioFalso(http.server.BaseHTTPRequestHandler):
    recibido = []

    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        crudo = self.rfile.read(largo) if largo else b""
        try:
            datos = json.loads(crudo.decode("utf-8")) if crudo else None
        except ValueError:
            datos = None
        type(self).recibido.append({"ruta": self.path, "json": datos})
        cuerpo = json.dumps({
            "access_token": ACCESO,
            "refresh_token": RENOVACION,
            "expires_in": 3600,
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *argumentos):
        pass


@contextlib.contextmanager
def _servicio():
    _ServicioFalso.recibido = []
    servidor = http.server.HTTPServer(("127.0.0.1", 0), _ServicioFalso)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        yield f"http://127.0.0.1:{servidor.server_port}"
    finally:
        servidor.shutdown()
        servidor.server_close()


def _abrir_con(visto=None):
    def abrir(url):
        consulta = parse_qs(urlsplit(url).query)
        redirect_uri = consulta["redirect_uri"][0]
        estado = consulta["state"][0]
        if visto is not None:
            visto["url"] = url
            visto["redirect_uri"] = redirect_uri

        def pedir():
            httpx.get(redirect_uri, params={"code": CODIGO, "state": estado},
                      timeout=5)

        threading.Thread(target=pedir, daemon=True).start()

    return abrir


class TestCuenta(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._rutas = redirigir_rutas(self._tmp.name)
        self._rutas.__enter__()
        self.addCleanup(self._rutas.__exit__, None, None, None)
        cuenta._reiniciar()
        self.addCleanup(cuenta._reiniciar)

    def _conectar(self, visto=None):
        with _servicio() as servicio, \
                mock.patch.object(oauth, "SERVICIO", servicio):
            cuenta.conectar(abrir=_abrir_con(visto))

    def _sesion_conectada(self):
        cuenta.sesion().establecer(
            sesion.Tokens(ACCESO, RENOVACION, time.time() + 3600))

    def test_p1_una_sesion_nueva_encuentra_los_tokens_guardados(self):
        self._conectar()

        guardado = credenciales.cargar()["restream_token"]
        self.assertEqual(guardado["acceso"], ACCESO)
        self.assertEqual(guardado["renovacion"], RENOVACION)

        cuenta._reiniciar()
        self.assertTrue(cuenta.sesion().conectada())
        self.assertEqual(cuenta.sesion().token(), ACCESO)

    def test_sesion_renueva_con_el_servicio_publicado(self):
        viejo = sesion.Tokens("acceso-viejo", "renovacion-vieja",
                              time.time() + 100)
        self.assertTrue(credenciales.guardar_campo(
            "restream_token", viejo.a_dict()))

        with _servicio() as servicio, \
                mock.patch.object(oauth, "SERVICIO", servicio):
            self.assertEqual(ACCESO, cuenta.sesion().token())

        recibido = _ServicioFalso.recibido[0]
        self.assertEqual("/refresh", recibido["ruta"])
        self.assertEqual("renovacion-vieja",
                         recibido["json"]["refresh_token"])
        guardado = credenciales.cargar()["restream_token"]
        self.assertEqual(ACCESO, guardado["acceso"])
        self.assertEqual(RENOVACION, guardado["renovacion"])

    def test_p2_conectar_abre_el_navegador_canjea_y_deja_la_sesion(self):
        visto = {}
        self._conectar(visto)

        self.assertTrue(visto["url"].startswith(
            "https://api.restream.io/login"))
        self.assertTrue(visto["redirect_uri"].startswith("http://127.0.0.1:"))
        recibido = _ServicioFalso.recibido[0]
        self.assertEqual("/exchange", recibido["ruta"])
        self.assertEqual(CODIGO, recibido["json"]["code"])
        self.assertEqual(visto["redirect_uri"],
                         recibido["json"]["redirect_uri"])
        self.assertTrue(cuenta.sesion().conectada())
        self.assertEqual(ACCESO, cuenta.sesion().token())

    def test_p3_desconectar_revoca_y_borra_lo_guardado(self):
        self._sesion_conectada()
        visto = {}

        def manejar(pedido):
            visto["metodo"] = pedido.method
            visto["url"] = str(pedido.url)
            visto["cuerpo"] = pedido.content.decode("utf-8")
            return httpx.Response(200, json={})

        cliente = httpx.Client(transport=httpx.MockTransport(manejar))
        self.addCleanup(cliente.close)
        cuenta.desconectar(cliente)

        self.assertEqual("POST", visto["metodo"])
        self.assertEqual("https://api.restream.io/oauth/revoke", visto["url"])
        self.assertEqual([RENOVACION], parse_qs(visto["cuerpo"])["token"])
        self.assertIsNone(credenciales.cargar()["restream_token"])
        self.assertFalse(cuenta.sesion().conectada())
        self.assertEqual("", cuenta.sesion().token_de_renovacion())

    def test_p3_desconectar_borra_aunque_falle_la_revocacion(self):
        self._sesion_conectada()

        def falla(_pedido):
            raise httpx.ConnectError("sin red")

        cliente = httpx.Client(transport=httpx.MockTransport(falla))
        self.addCleanup(cliente.close)
        with self.assertLogs(oauth.logger, level="WARNING") as registro:
            cuenta.desconectar(cliente)

        self.assertIsNone(credenciales.cargar()["restream_token"])
        self.assertFalse(cuenta.sesion().conectada())
        self.assertNotIn(RENOVACION, "\n".join(registro.output))

    def test_canales_usa_el_token_vigente(self):
        self._sesion_conectada()

        with mock.patch.object(api, "canales", return_value=["canal"]) as leer:
            self.assertEqual(["canal"], cuenta.canales("cliente"))

        leer.assert_called_once_with(ACCESO, "cliente")

    def test_canales_sin_sesion_deja_pasar_sesion_vencida(self):
        with self.assertRaises(sesion.SesionVencida):
            cuenta.canales()

    def test_perfil_usa_el_token_vigente(self):
        self._sesion_conectada()

        with mock.patch.object(api, "perfil", return_value="datos") as leer:
            self.assertEqual("datos", cuenta.perfil("cliente"))

        leer.assert_called_once_with(ACCESO, "cliente")

    def test_eliminar_canal_usa_el_token_vigente(self):
        self._sesion_conectada()

        with mock.patch.object(api, "eliminar_canal") as borrar:
            cuenta.eliminar_canal(7, "cliente")

        borrar.assert_called_once_with(ACCESO, 7, "cliente")

    def test_eventos_usa_el_token_vigente(self):
        self._sesion_conectada()

        with mock.patch.object(api, "eventos", return_value=["evento"]) as leer:
            self.assertEqual(["evento"],
                             cuenta.eventos("proximos", "cliente"))

        leer.assert_called_once_with(ACCESO, "proximos", "cliente")

    def test_estadisticas_usa_el_token_vigente(self):
        self._sesion_conectada()

        with mock.patch.object(api, "estadisticas", return_value="cifras") as leer:
            self.assertEqual("cifras", cuenta.estadisticas(7, "cliente"))

        leer.assert_called_once_with(ACCESO, 7, "cliente")

    def test_clave_cuenta_usa_el_token_vigente(self):
        self._sesion_conectada()

        with mock.patch.object(api, "clave_cuenta", return_value="clave") as leer:
            self.assertEqual("clave", cuenta.clave_cuenta("cliente"))

        leer.assert_called_once_with(ACCESO, "cliente")

    def test_activar_canal_usa_el_token_vigente(self):
        self._sesion_conectada()

        with mock.patch.object(api, "activar_canal") as activar:
            cuenta.activar_canal(7, False, "cliente")

        activar.assert_called_once_with(ACCESO, 7, False, "cliente")

    def test_leer_meta_usa_el_token_vigente(self):
        self._sesion_conectada()

        with mock.patch.object(api, "leer_meta", return_value="meta") as leer:
            self.assertEqual("meta", cuenta.leer_meta(7, "cliente"))

        leer.assert_called_once_with(ACCESO, 7, "cliente")

    def test_cambiar_meta_usa_el_token_vigente(self):
        self._sesion_conectada()

        with mock.patch.object(api, "cambiar_meta") as cambiar:
            cuenta.cambiar_meta(7, "título", "descripción", "cliente")

        cambiar.assert_called_once_with(ACCESO, 7, "título", "descripción",
                                        "cliente")

    def test_agregar_canal_manual_usa_el_token_vigente(self):
        self._sesion_conectada()

        with mock.patch.object(api, "agregar_canal_manual") as agregar:
            cuenta.agregar_canal_manual(67, "nombre", "servidor", "clave",
                                        "cliente")

        agregar.assert_called_once_with(ACCESO, 67, "nombre", "servidor",
                                        "clave", "cliente")


if __name__ == "__main__":
    unittest.main()
