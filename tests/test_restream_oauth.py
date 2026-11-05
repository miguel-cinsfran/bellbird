"""Pruebas del inicio de sesión en Restream y de las llamadas al servicio."""

import contextlib
import http.server
import io
import json
import socket
import threading
import time
import unittest
from urllib.parse import parse_qs, urlsplit

import httpx

from guyrapu.restream import oauth, sesion


class TestServidorLocalVersion(unittest.TestCase):

    def test_el_servidor_dice_el_nombre_de_la_app(self):
        from guyrapu.core.config import APP_NAME
        self.assertEqual(oauth._Manejador.server_version, f"{APP_NAME}/1.0")


CODIGO = "codigo-de-prueba"
TOKEN = "renovacion-de-prueba"
VUELTA = "http://127.0.0.1:47615/callback"


def _hasta(condicion, plazo=3.0):
    limite = time.monotonic() + plazo
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.01)
    return False


def _abrir_con(pedidos, salida=None, visto=None):
    """Abre la dirección de autorización y hace los pedidos de vuelta."""

    def abrir(url):
        consulta = parse_qs(urlsplit(url).query)
        redirect_uri = consulta["redirect_uri"][0]
        estado = consulta["state"][0]
        if visto is not None:
            visto["state"] = estado
            visto["redirect_uri"] = redirect_uri

        def pedir():
            for ruta, extra in pedidos(estado):
                destino = redirect_uri.replace(oauth.RUTA_VUELTA, ruta)
                respuesta = httpx.get(destino, params=extra, timeout=5)
                if salida is not None:
                    salida.append((respuesta.status_code, respuesta.text))

        threading.Thread(target=pedir, daemon=True).start()

    return abrir


class _ServicioFalso(http.server.BaseHTTPRequestHandler):
    respuesta = (200, {})
    recibido = []

    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        crudo = self.rfile.read(largo) if largo else b""
        try:
            datos = json.loads(crudo.decode("utf-8")) if crudo else None
        except ValueError:
            datos = None
        type(self).recibido.append({
            "ruta": self.path,
            "tipo": self.headers.get("Content-Type", ""),
            "json": datos,
        })
        estado, cuerpo = type(self).respuesta
        contenido = json.dumps(cuerpo).encode("utf-8")
        self.send_response(estado)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(contenido)))
        self.end_headers()
        self.wfile.write(contenido)

    def log_message(self, *argumentos):
        pass


@contextlib.contextmanager
def _servicio(estado, cuerpo):
    _ServicioFalso.respuesta = (estado, cuerpo)
    _ServicioFalso.recibido = []
    servidor = http.server.HTTPServer(("127.0.0.1", 0), _ServicioFalso)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        yield f"http://127.0.0.1:{servidor.server_port}"
    finally:
        servidor.shutdown()
        servidor.server_close()


def _sesion_con(servicio, guardar):
    return sesion.Sesion(
        cargar=lambda: {
            "acceso": "acceso-viejo",
            "renovacion": TOKEN,
            "vence": 1000.0,
            "permisos": "",
        },
        guardar=guardar,
        renovar=lambda token: oauth.renovar(servicio, token),
        reloj=lambda: 1000.0,
    )


class TestAutorizacion(unittest.TestCase):

    def test_p1_la_direccion_lleva_lo_justo_y_sin_scope(self):
        url = oauth.url_autorizacion(VUELTA, "estado-de-prueba")
        partes = urlsplit(url)
        self.assertEqual(
            f"{partes.scheme}://{partes.netloc}{partes.path}",
            "https://api.restream.io/login")
        consulta = parse_qs(partes.query)
        self.assertEqual(consulta["response_type"], ["code"])
        self.assertEqual(consulta["client_id"], [oauth.CLIENT_ID])
        self.assertEqual(consulta["redirect_uri"], [VUELTA])
        self.assertEqual(consulta["state"], ["estado-de-prueba"])
        self.assertNotIn("scope", consulta)


class TestServidorLocal(unittest.TestCase):

    def test_p2_p3_p4_vuelta_buena_devuelve_codigo_y_pagina(self):
        salida = []
        visto = {}
        abrir = _abrir_con(
            lambda estado: [("/callback", {"code": CODIGO, "state": estado})],
            salida, visto)
        codigo, redirect_uri = oauth.esperar_codigo(abrir, plazo=5)
        self.assertEqual(codigo, CODIGO)
        self.assertTrue(redirect_uri.startswith("http://127.0.0.1:"))
        self.assertTrue(redirect_uri.endswith(oauth.RUTA_VUELTA))
        self.assertTrue(_hasta(lambda: len(salida) == 1))
        self.assertEqual(salida[0][0], 200)
        self.assertIn("Guyrapu ya tiene acceso", salida[0][1])
        self.assertTrue(visto["state"])

    def test_p3_ruta_equivocada_responde_404_y_sigue_esperando(self):
        salida = []
        abrir = _abrir_con(
            lambda estado: [
                ("/otra", {"code": CODIGO, "state": estado}),
                ("/callback", {"code": CODIGO, "state": estado}),
            ], salida)
        codigo, _redirect_uri = oauth.esperar_codigo(abrir, plazo=5)
        self.assertEqual(codigo, CODIGO)
        self.assertTrue(_hasta(lambda: len(salida) == 2))
        self.assertEqual(salida[0][0], 404)
        self.assertEqual(salida[1][0], 200)

    def test_p3_state_equivocado_responde_400_y_sigue_esperando(self):
        salida = []
        abrir = _abrir_con(
            lambda estado: [
                ("/callback", {"code": CODIGO, "state": "equivocado"}),
                ("/callback", {"code": CODIGO, "state": estado}),
            ], salida)
        codigo, _redirect_uri = oauth.esperar_codigo(abrir, plazo=5)
        self.assertEqual(codigo, CODIGO)
        self.assertTrue(_hasta(lambda: len(salida) == 2))
        self.assertEqual(salida[0][0], 400)
        self.assertEqual(salida[1][0], 200)

    def test_p4_error_de_restream_es_cancelacion(self):
        salida = []
        abrir = _abrir_con(
            lambda estado: [
                ("/callback", {"error": "access_denied", "state": estado})],
            salida)
        with self.assertRaises(oauth.InicioCancelado):
            oauth.esperar_codigo(abrir, plazo=5)
        self.assertTrue(_hasta(lambda: len(salida) == 1))
        self.assertEqual(salida[0][0], 200)
        self.assertIn("No se completó el inicio de sesión", salida[0][1])

    def test_p4_plazo_vencido_y_el_servidor_se_cierra(self):
        puerto = {}
        with self.assertRaises(oauth.PlazoVencido):
            oauth.esperar_codigo(lambda url: _solo_puerto(url, puerto),
                                 plazo=1.0)
        with socket.socket() as libre:
            libre.bind(("127.0.0.1", puerto["puerto"]))

    def test_p4_parada_activa_es_plazo_vencido(self):
        parada = threading.Event()
        parada.set()
        with self.assertRaises(oauth.PlazoVencido):
            oauth.esperar_codigo(lambda url: None, plazo=5, parada=parada)

    def test_p4_la_parada_corta_la_espera_y_libera_el_puerto(self):
        parada = threading.Event()
        puerto = {}

        def abrir(url):
            _solo_puerto(url, puerto)
            threading.Timer(0.3, parada.set).start()

        inicio = time.monotonic()
        with self.assertRaises(oauth.PlazoVencido):
            oauth.esperar_codigo(abrir, plazo=60, parada=parada)
        self.assertLess(time.monotonic() - inicio, 3.0)
        with socket.socket() as libre:
            libre.bind(("127.0.0.1", puerto["puerto"]))

    def test_p2_puerto_ocupado_usa_el_siguiente(self):
        ocupado = _ocupar(oauth.PUERTOS[0])
        if ocupado is None:
            self.skipTest(f"el puerto {oauth.PUERTOS[0]} ya está ocupado")
        self.addCleanup(ocupado.close)
        if not _libre(oauth.PUERTOS[1]):
            self.skipTest(f"el puerto {oauth.PUERTOS[1]} ya está ocupado")
        salida = []
        abrir = _abrir_con(
            lambda estado: [("/callback", {"code": CODIGO, "state": estado})],
            salida)
        codigo, redirect_uri = oauth.esperar_codigo(abrir, plazo=5)
        self.assertEqual(codigo, CODIGO)
        self.assertEqual(urlsplit(redirect_uri).port, oauth.PUERTOS[1])

    def test_p2_los_dos_puertos_ocupados_es_error_propio(self):
        ocupados = []
        try:
            for puerto in oauth.PUERTOS:
                tomado = _ocupar(puerto)
                if tomado is None:
                    self.skipTest(f"el puerto {puerto} ya está ocupado")
                ocupados.append(tomado)
        finally:
            for tomado in ocupados:
                self.addCleanup(tomado.close)
        with self.assertRaises(oauth.PuertosOcupados) as salida:
            oauth.esperar_codigo(lambda url: None, plazo=1)
        self.assertIn("47615", str(salida.exception))
        self.assertIn("47616", str(salida.exception))


def _solo_puerto(url, destino):
    consulta = parse_qs(urlsplit(url).query)
    destino["puerto"] = urlsplit(consulta["redirect_uri"][0]).port


def _ocupar(puerto):
    tomado = socket.socket()
    try:
        tomado.bind(("127.0.0.1", puerto))
    except OSError:
        tomado.close()
        return None
    return tomado


def _libre(puerto):
    sonda = _ocupar(puerto)
    if sonda is None:
        return False
    sonda.close()
    return True


class TestServicio(unittest.TestCase):

    def test_la_direccion_es_la_del_worker_renombrado(self):
        self.assertEqual(
            oauth.SERVICIO, "https://restream-tokens.guyrapu.workers.dev")

    def test_p6_canje_manda_json_y_devuelve_tokens(self):
        with _servicio(200, {"access_token": "acceso",
                             "refresh_token": "renovacion",
                             "expires_in": 3600}) as servicio:
            tokens = oauth.canjear(servicio, CODIGO, VUELTA)
        self.assertIsInstance(tokens, sesion.Tokens)
        self.assertEqual(tokens.acceso, "acceso")
        self.assertEqual(tokens.renovacion, "renovacion")
        recibido = _ServicioFalso.recibido[0]
        self.assertEqual(recibido["ruta"], "/exchange")
        self.assertIn("application/json", recibido["tipo"])
        self.assertEqual(recibido["json"], {
            "code": CODIGO,
            "redirect_uri": VUELTA,
            "client_id": oauth.CLIENT_ID,
        })

    def test_p6_renovacion_manda_json_y_devuelve_la_respuesta(self):
        with _servicio(200, {"access_token": "acceso-nuevo",
                             "refresh_token": "renovacion-nueva",
                             "expires_in": 3600}) as servicio:
            datos = oauth.renovar(servicio, TOKEN)
        self.assertEqual(datos["access_token"], "acceso-nuevo")
        self.assertEqual(datos["refresh_token"], "renovacion-nueva")
        recibido = _ServicioFalso.recibido[0]
        self.assertEqual(recibido["ruta"], "/refresh")
        self.assertEqual(recibido["json"], {
            "refresh_token": TOKEN,
            "client_id": oauth.CLIENT_ID,
        })

    def test_p7_invalid_grant_es_rechazo_de_concesion(self):
        with _servicio(400, {"error": "invalid_grant"}) as servicio:
            with self.assertRaises(sesion.RechazoDeConcesion):
                oauth.renovar(servicio, TOKEN)

    def test_p7_otro_fallo_es_error_de_servicio(self):
        with _servicio(500, {"error": "server_error"}) as servicio:
            with self.assertRaises(oauth.FalloServicio):
                oauth.renovar(servicio, TOKEN)
        with _servicio(500, {"error": "server_error"}) as servicio:
            with self.assertRaises(oauth.FalloServicio):
                oauth.canjear(servicio, CODIGO, VUELTA)

    def test_p7_renovar_se_enchufa_en_la_sesion(self):
        guardado = []
        with _servicio(200, {"access_token": "acceso-nuevo",
                             "refresh_token": "renovacion-nueva",
                             "expires_in": 3600}) as servicio:
            actual = _sesion_con(servicio, guardado.append)
            self.assertEqual(actual.token(), "acceso-nuevo")
        self.assertEqual(guardado[-1]["acceso"], "acceso-nuevo")
        self.assertEqual(guardado[-1]["renovacion"], "renovacion-nueva")

        guardado = []
        with _servicio(400, {"error": "invalid_grant"}) as servicio:
            actual = _sesion_con(servicio, guardado.append)
            with self.assertRaises(sesion.SesionVencida):
                actual.token()

    def test_p8_revocar_manda_formulario_sin_secreto(self):
        visto = {}

        def manejar(pedido):
            visto["metodo"] = pedido.method
            visto["url"] = str(pedido.url)
            visto["cuerpo"] = pedido.content.decode("utf-8")
            return httpx.Response(200, json={})

        cliente = httpx.Client(transport=httpx.MockTransport(manejar))
        self.addCleanup(cliente.close)
        oauth.revocar(TOKEN, cliente=cliente)
        self.assertEqual(visto["metodo"], "POST")
        self.assertEqual(visto["url"],
                         "https://api.restream.io/oauth/revoke")
        datos = parse_qs(visto["cuerpo"])
        self.assertEqual(datos["token"], [TOKEN])
        self.assertEqual(datos["token_type_hint"], ["refresh_token"])
        self.assertNotIn("secret", visto["cuerpo"])

    def test_p8_revocar_nunca_lanza(self):
        def falla(pedido):
            raise httpx.ConnectError("sin red")

        cliente = httpx.Client(transport=httpx.MockTransport(falla))
        self.addCleanup(cliente.close)
        with self.assertLogs(oauth.logger, level="WARNING") as registro:
            oauth.revocar(TOKEN, cliente=cliente)
        self.assertNotIn(TOKEN, "\n".join(registro.output))


class TestSinSecretos(unittest.TestCase):

    def test_p9_ni_codigo_ni_state_en_registro_ni_stderr(self):
        salida = []
        visto = {}
        abrir = _abrir_con(
            lambda estado: [("/callback", {"code": CODIGO, "state": estado})],
            salida, visto)
        errores = io.StringIO()
        with self.assertLogs(oauth.logger, level="DEBUG") as registro, \
                contextlib.redirect_stderr(errores):
            codigo, _redirect_uri = oauth.esperar_codigo(abrir, plazo=5)
        textos = "\n".join(registro.output) + errores.getvalue()
        self.assertNotIn(codigo, textos)
        self.assertNotIn(visto["state"], textos)

    def test_p9_el_token_no_aparece_en_el_error_del_servicio(self):
        with _servicio(500, {"error": "server_error", "token": TOKEN}) as servicio:
            with self.assertRaises(oauth.FalloServicio) as salida:
                oauth.renovar(servicio, TOKEN)
        self.assertNotIn(TOKEN, str(salida.exception))


if __name__ == "__main__":
    unittest.main()
