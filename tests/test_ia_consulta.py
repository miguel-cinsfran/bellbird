"""Pruebas de la consulta a la IA, sin red salvo el cableado final."""

import http.server
import json
import threading
import unittest

from ytchat.ai import catalogo
from ytchat.ai import consulta
from ytchat.ai import conversacion
from ytchat.ai import protocolos
from ytchat.ai.ajustes_ia import AjustesIA
from ytchat.ai.conversacion import Conversacion

IMAGEN = b"\xff\xd8\xfffoto\xff\xd9"


def _muestra_opencode_go():
    return {
        "version": catalogo.VERSION,
        "fecha": "2026-10-21",
        "proveedores": {
            "opencode-go": {
                "nombre": "OpenCode Go",
                "modelos": [
                    {"id": "claude-oro",
                     "nombre": "Claude Oro",
                     "protocolo": protocolos.ANTHROPIC,
                     "base": "https://opencode.ai/inference/go/anthropic/v1",
                     "gratis": False, "contributor": False,
                     "piensa": True, "tope_salida": 128000},
                    {"id": "mini-rapido",
                     "nombre": "Mini Rápido",
                     "protocolo": protocolos.CHAT,
                     "base": "https://opencode.ai/inference/go/openai/v1",
                     "gratis": False, "contributor": False,
                     "piensa": False, "tope_salida": 500},
                ],
            },
        },
    }


def _charla_con_captura(texto_inicial="¿Qué se ve?"):
    charla = Conversacion()
    charla.agregar_captura(IMAGEN, "OBS", "10:00")
    return charla


def _ajustes(modelo="claude-oro", proveedor="opencode-go", clave="k"):
    return AjustesIA(proveedor=proveedor, modelo=modelo), clave


class TestValidacion(unittest.TestCase):

    def test_proveedor_desconocido(self):
        charla = _charla_con_captura()
        ajustes = AjustesIA(proveedor="inventado", modelo="m")
        with self.assertRaises(consulta.FaltaConfiguracion) as salida:
            consulta.preparar(charla, "hola", ajustes, {}, "clave", "")
        self.assertEqual(
            str(salida.exception),
            "Elige un proveedor en Preferencias, Inteligencia artificial.")

    def test_modelo_vacio(self):
        charla = _charla_con_captura()
        for vacio in ("", "   "):
            with self.subTest(modelo=repr(vacio)):
                ajustes = AjustesIA(proveedor="gemini", modelo=vacio)
                with self.assertRaises(consulta.FaltaConfiguracion) as salida:
                    consulta.preparar(charla, "hola", ajustes, {}, "c", "")
                self.assertEqual(
                    str(salida.exception),
                    "Elige un modelo en Preferencias, "
                    "Inteligencia artificial.")

    def test_sin_clave_nombra_al_proveedor(self):
        charla = _charla_con_captura()
        for clave in ("", None, "   "):
            with self.subTest(clave=repr(clave)):
                ajustes = AjustesIA(proveedor="gemini", modelo="m")
                with self.assertRaises(consulta.FaltaConfiguracion) as salida:
                    consulta.preparar(charla, "hola", ajustes, {}, clave, "")
                self.assertEqual(
                    str(salida.exception),
                    "Falta la clave de Google Gemini. Guárdala "
                    "en Preferencias, Inteligencia artificial.")

    def test_direccion_mala(self):
        charla = _charla_con_captura()
        ajustes = AjustesIA(proveedor="otro", modelo="m",
                            direccion="mio.example.com/v1")
        with self.assertRaises(consulta.FaltaConfiguracion) as salida:
            consulta.preparar(charla, "hola", ajustes, {}, "clave", "")
        self.assertEqual(
            str(salida.exception),
            "Escribe una dirección válida para el proveedor "
            "en Preferencias, Inteligencia artificial.")

    def test_orden_de_validacion(self):
        charla = _charla_con_captura()
        ajustes = AjustesIA(proveedor="inventado", modelo="",
                            direccion="mala")
        with self.assertRaises(consulta.FaltaConfiguracion) as salida:
            consulta.preparar(charla, "hola", ajustes, {}, None, "")
        self.assertEqual(
            str(salida.exception),
            "Elige un proveedor en Preferencias, Inteligencia artificial.")
        ajustes = AjustesIA(proveedor="otro", modelo="", direccion="mala")
        with self.assertRaises(consulta.FaltaConfiguracion) as salida:
            consulta.preparar(charla, "hola", ajustes, {}, None, "")
        self.assertEqual(
            str(salida.exception),
            "Elige un modelo en Preferencias, Inteligencia artificial.")
        ajustes = AjustesIA(proveedor="otro", modelo="m", direccion="mala")
        with self.assertRaises(consulta.FaltaConfiguracion) as salida:
            consulta.preparar(charla, "hola", ajustes, {}, None, "")
        self.assertTrue(str(salida.exception).startswith("Falta la clave de"))

    def test_sin_captura_y_sin_texto_pasan_tal_cual(self):
        charla = Conversacion()
        ajustes = AjustesIA(proveedor="gemini", modelo="m")
        with self.assertRaises(conversacion.SinCaptura):
            consulta.preparar(charla, "hola", ajustes, {}, "clave", "")
        con_captura = _charla_con_captura()
        pedido = con_captura.preparar("hola", conversacion.PREGUNTA_INICIAL)
        con_captura.confirmar(pedido[-1].texto, "Se ve algo")
        with self.assertRaises(conversacion.SinTexto):
            consulta.preparar(con_captura, "   ", ajustes, {}, "clave", "")


class TestPreparar(unittest.TestCase):

    def test_no_cambia_la_conversacion(self):
        charla = _charla_con_captura()
        ajustes, clave = _ajustes()
        antes_mensajes = list(charla.mensajes)
        antes_filas = list(charla.filas)
        consulta.preparar(charla, "¿Qué se ve?", ajustes,
                           _muestra_opencode_go(), clave, "")
        self.assertEqual(charla.mensajes, antes_mensajes)
        self.assertEqual(charla.filas, antes_filas)
        self.assertIsNotNone(charla._pendiente)

    def test_opencode_go_usa_catalogo_y_sesion(self):
        charla = _charla_con_captura()
        ajustes, clave = _ajustes()
        preparada = consulta.preparar(charla, "¿Qué se ve?", ajustes,
                                      _muestra_opencode_go(), clave, "")
        self.assertEqual(preparada.pedido.protocolo, protocolos.ANTHROPIC)
        self.assertTrue(preparada.pedido.url.startswith(
            "https://opencode.ai/inference/go/anthropic/v1"))
        self.assertEqual(preparada.pedido.cabeceras["x-opencode-session"],
                         charla.sesion)
        self.assertEqual(preparada.texto_enviado, "¿Qué se ve?")
        self.assertEqual(preparada.tiempo_espera, ajustes.tiempo_espera)

    def test_modelo_ausente_usa_tope_de_quien_piensa(self):
        charla = _charla_con_captura()
        ajustes = AjustesIA(proveedor="opencode-go",
                            modelo="modelo-escrito-a-mano")
        preparada = consulta.preparar(charla, "hola", ajustes,
                                      _muestra_opencode_go(), "clave", "")
        self.assertEqual(preparada.pedido.protocolo, protocolos.CHAT)
        self.assertTrue(preparada.pedido.url.startswith(
            "https://opencode.ai/inference/go/openai/v1"))
        self.assertEqual(preparada.pedido.cuerpo["max_tokens"], 4900)

    def test_modelo_en_catalogo_usa_su_piensa_y_su_tope(self):
        charla = _charla_con_captura()
        ajustes = AjustesIA(proveedor="opencode-go",
                            modelo="mini-rapido")
        preparada = consulta.preparar(charla, "hola", ajustes,
                                      _muestra_opencode_go(), "clave", "")
        self.assertEqual(preparada.pedido.cuerpo["max_tokens"], 500)

    def test_texto_enviado_es_el_ultimo_de_preparar(self):
        charla = _charla_con_captura()
        ajustes = AjustesIA(proveedor="gemini", modelo="m",
                            pregunta="  pregunta propia  ")
        preparada = consulta.preparar(charla, "", ajustes, {}, "clave", "")
        self.assertEqual(preparada.texto_enviado, "pregunta propia")


def _respuesta(texto, cortada=False):
    return protocolos.Respuesta(texto, cortada=cortada)


class TestConsultar(unittest.TestCase):

    def test_confirma_solo_si_sale_bien(self):
        charla = _charla_con_captura()
        ajustes, clave = _ajustes()
        preparada = consulta.preparar(charla, "¿Qué se ve?", ajustes,
                                      _muestra_opencode_go(), clave, "")
        texto = consulta.consultar(charla, preparada, clave,
                                   enviar=lambda p, c, t: _respuesta("Se ve"))
        self.assertEqual(texto, "Se ve")
        self.assertEqual(len(charla.mensajes), 2)
        self.assertEqual(charla.mensajes[0].texto, "¿Qué se ve?")
        self.assertIs(charla.mensajes[0].imagen, IMAGEN)
        self.assertEqual(charla.mensajes[1].texto, "Se ve")
        self.assertIsNone(charla._pendiente)

    def test_si_enviar_falla_no_confirma(self):
        charla = _charla_con_captura()
        ajustes, clave = _ajustes()
        preparada = consulta.preparar(charla, "¿Qué se ve?", ajustes,
                                      _muestra_opencode_go(), clave, "")

        def _falla(pedido, clave_pedida, espera):
            raise protocolos.ErrorIA(protocolos.SERVIDOR, "caído")

        with self.assertRaises(protocolos.ErrorIA):
            consulta.consultar(charla, preparada, clave, enviar=_falla)
        self.assertEqual(charla.mensajes, [])
        self.assertIsNotNone(charla._pendiente)

    def test_cortada_agrega_la_frase_sin_tocarla_en_charla(self):
        charla = _charla_con_captura()
        ajustes, clave = _ajustes()
        preparada = consulta.preparar(charla, "hola", ajustes,
                                      _muestra_opencode_go(), clave, "")
        texto = consulta.consultar(
            charla, preparada, clave,
            enviar=lambda p, c, t: _respuesta("Parte", cortada=True))
        self.assertEqual(
            texto, "Parte La respuesta quedó cortada por el largo "
                   "elegido en Preferencias.")
        self.assertEqual(charla.mensajes[1].texto, "Parte")


class TestTextoDeError(unittest.TestCase):

    def test_todos_los_tipos(self):
        esperados = {
            protocolos.CLAVE_RECHAZADA:
                "El proveedor rechazó la clave. Revísala en Preferencias, "
                "Inteligencia artificial.",
            protocolos.CUOTA:
                "Se agotó la cuota del proveedor. Espera un rato o elige "
                "otro modelo.",
            protocolos.MODELO_INEXISTENTE:
                "El proveedor no ofrece ese modelo. Elige otro "
                "en Preferencias, Inteligencia artificial.",
            protocolos.BLOQUEADA:
                "El proveedor bloqueó la respuesta con su filtro "
                "de contenido.",
            protocolos.SIN_TEXTO_POR_TOKENS:
                "El modelo gastó todo el espacio pensando y no respondió. "
                "Elige una respuesta más larga en Preferencias.",
            protocolos.RESPUESTA_VACIA:
                "El modelo no devolvió ninguna respuesta. Vuelve "
                "a intentarlo.",
            protocolos.SERVIDOR:
                "El proveedor tuvo un fallo. Vuelve a intentarlo en un rato.",
            protocolos.RECHAZO:
                "El proveedor rechazó la consulta. Puede que el modelo ya "
                "no esté disponible: en Preferencias, Inteligencia "
                "artificial, pulsa Actualizar la lista de modelos o "
                "elige otro.",
            protocolos.SIN_RED:
                "No hay conexión con el proveedor. Comprueba la conexión "
                "a internet.",
            protocolos.TIEMPO_AGOTADO:
                "El proveedor tardó demasiado en responder. Vuelve "
                "a intentarlo.",
        }
        for tipo, frase in esperados.items():
            with self.subTest(tipo=tipo):
                error = protocolos.ErrorIA(tipo, "detalle-secreto-xyz")
                self.assertEqual(consulta.texto_de_error(error), frase)
                self.assertNotIn("detalle-secreto-xyz",
                                 consulta.texto_de_error(error))

    def test_cuota_sin_nivel_gratuito_tiene_su_frase(self):
        error = protocolos.ErrorIA(
            protocolos.CUOTA, "detalle", sin_nivel_gratuito=True)
        self.assertEqual(
            consulta.TEXTO_SIN_NIVEL_GRATUITO,
            "Este modelo no está en el nivel gratuito de tu clave. "
            "Elige otro modelo.")
        self.assertEqual(consulta.texto_de_error(error),
                         consulta.TEXTO_SIN_NIVEL_GRATUITO)

    def test_cuota_acotada_sigue_con_el_texto_de_cuota(self):
        error = protocolos.ErrorIA(protocolos.CUOTA, "detalle")
        self.assertEqual(
            consulta.texto_de_error(error),
            "Se agotó la cuota del proveedor. Espera un rato o elige "
            "otro modelo.")

    def test_sin_captura_sin_texto_y_falta(self):
        self.assertEqual(consulta.texto_de_error(
            conversacion.SinCaptura("x")), "Agrega una captura antes de "
                                           "preguntar.")
        self.assertEqual(consulta.texto_de_error(
            conversacion.SinTexto("x")), "Escribe una pregunta.")
        falta = consulta.FaltaConfiguracion("Falta la clave de X. Guárdala.")
        self.assertEqual(consulta.texto_de_error(falta),
                         "Falta la clave de X. Guárdala.")

    def test_desconocido_no_muestra_el_detalle(self):
        raro = protocolos.ErrorIA("tipo_nuevo", "detalle-secreto-xyz")
        self.assertEqual(consulta.texto_de_error(raro),
                         "No se pudo completar la consulta. "
                         "Vuelve a intentarlo.")
        self.assertEqual(consulta.texto_de_error(ValueError("boom")),
                         "No se pudo completar la consulta. "
                         "Vuelve a intentarlo.")


class _ServidorChat(http.server.BaseHTTPRequestHandler):
    estado = 200
    cuerpo = "{}"
    recibido = None

    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        crudo = self.rfile.read(largo) if largo else b""
        try:
            datos = json.loads(crudo.decode("utf-8")) if crudo else None
        except ValueError:
            datos = None
        type(self).recibido = {"ruta": self.path, "json": datos,
                               "crudo": crudo}
        cuerpo = type(self).cuerpo.encode("utf-8")
        try:
            self.send_response(type(self).estado)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
        except (BrokenPipeError, ConnectionResetError,
                ConnectionAbortedError):
            pass

    def log_message(self, *args):
        pass


class TestCableado(unittest.TestCase):

    def _servidor(self, cuerpo):
        _ServidorChat.cuerpo = cuerpo
        _ServidorChat.recibido = None
        servidor = http.server.HTTPServer(("127.0.0.1", 0), _ServidorChat)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        self.addCleanup(servidor.server_close)
        self.addCleanup(servidor.shutdown)
        return servidor

    def test_de_punta_a_punta_por_chat(self):
        import base64
        cuerpo = json.dumps({"choices": [
            {"finish_reason": "stop",
             "message": {"role": "assistant",
                         "content": "Se ve un juego"}}]})
        servidor = self._servidor(cuerpo)
        base = "http://127.0.0.1:{}/v1".format(servidor.server_port)
        charla = Conversacion()
        charla.agregar_captura(IMAGEN, "OBS", "10:00")
        ajustes = AjustesIA(proveedor="otro", modelo="modelo-local",
                            direccion=base)
        preparada = consulta.preparar(charla, "¿Qué se ve?", ajustes, {},
                                      "clave", "Juego al aire")
        self.assertEqual(preparada.pedido.protocolo, protocolos.CHAT)
        texto = consulta.consultar(charla, preparada, "clave")
        self.assertEqual(texto, "Se ve un juego")
        recibido = _ServidorChat.recibido
        self.assertEqual(recibido["ruta"], "/v1/chat/completions")
        crudo = recibido["crudo"].decode("utf-8")
        self.assertIn("¿Qué se ve?", crudo)
        self.assertIn(base64.b64encode(IMAGEN).decode("ascii"), crudo)
        self.assertIn("Juego al aire", crudo)
        self.assertEqual(len(charla.mensajes), 2)
        self.assertEqual(charla.mensajes[0].texto, "¿Qué se ve?")
        self.assertIs(charla.mensajes[0].imagen, IMAGEN)
        self.assertEqual(charla.mensajes[1].texto, "Se ve un juego")
        self.assertIsNone(charla.mensajes[1].imagen)


if __name__ == "__main__":
    unittest.main()
