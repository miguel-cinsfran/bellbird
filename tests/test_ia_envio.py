"""Pruebas del envío de IA contra un servidor HTTP local de verdad."""

import http.server
import json
import socket
import threading
import time
import unittest

from ytchat.ai import envio_ia
from ytchat.ai import protocolos


CLAVE = "clave-secreta-de-prueba"
IMAGEN = b"\xff\xd8\xfffoto\xff\xd9"


class ServidorIA(http.server.BaseHTTPRequestHandler):
    estado = 200
    cuerpo = "{}"
    demora = 0.0
    recibido = None

    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        crudo = self.rfile.read(largo) if largo else b""
        try:
            datos = json.loads(crudo.decode("utf-8")) if crudo else None
        except ValueError:
            datos = None
        type(self).recibido = {
            "metodo": self.command,
            "ruta": self.path,
            "cabeceras": {k.lower(): v for k, v in self.headers.items()},
            "json": datos,
            "crudo": crudo,
        }
        if type(self).demora:
            time.sleep(type(self).demora)
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


def _pedido_chat():
    return protocolos.armar_pedido(
        protocolos.CHAT, "http://127.0.0.1:9", "modelo-x", CLAVE,
        "Respondé en una palabra.",
        [protocolos.Mensaje("usuario", "¿De qué color es?", IMAGEN)], 64)


class TestEnvio(unittest.TestCase):

    def _servidor(self, estado=200, cuerpo="{}", demora=0.0):
        ServidorIA.estado = estado
        ServidorIA.cuerpo = cuerpo
        ServidorIA.demora = demora
        ServidorIA.recibido = None
        servidor = http.server.HTTPServer(("127.0.0.1", 0), ServidorIA)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        self.addCleanup(servidor.server_close)
        self.addCleanup(servidor.shutdown)
        return servidor

    def _pedido_a(self, servidor):
        pedido = _pedido_chat()
        pedido.url = (f"http://127.0.0.1:{servidor.server_port}"
                      "/chat/completions")
        return pedido

    def test_200_llega_como_texto_y_el_servidor_recibe_el_pedido(self):
        cuerpo = json.dumps({"choices": [
            {"finish_reason": "stop",
             "message": {"role": "assistant", "content": "  Red  "}}]})
        servidor = self._servidor(estado=200, cuerpo=cuerpo)
        respuesta = envio_ia.enviar(
            self._pedido_a(servidor), CLAVE, 10)
        self.assertEqual(respuesta.texto, "Red")
        self.assertFalse(respuesta.cortada)
        recibido = ServidorIA.recibido
        self.assertEqual(recibido["metodo"], "POST")
        self.assertEqual(recibido["ruta"], "/chat/completions")
        self.assertEqual(
            recibido["cabeceras"]["authorization"], f"Bearer {CLAVE}")
        self.assertEqual(
            recibido["cabeceras"]["content-type"], "application/json")
        self.assertEqual(recibido["json"]["model"], "modelo-x")
        self.assertEqual(recibido["json"]["max_tokens"], 64)
        self.assertEqual(recibido["json"]["messages"][0]["role"],
                         "system")

    def test_401_llega_clasificado_y_sin_la_clave(self):
        cuerpo = json.dumps({"error": {"type": "server_error",
                                       "message": "Upstream request failed: "
                                       f"Invalid credential {CLAVE}"}})
        servidor = self._servidor(estado=401, cuerpo=cuerpo)
        with self.assertRaises(protocolos.ErrorIA) as salida:
            envio_ia.enviar(self._pedido_a(servidor), CLAVE, 10)
        error = salida.exception
        self.assertEqual(error.tipo, protocolos.CLAVE_RECHAZADA)
        self.assertNotIn(CLAVE, error.detalle)
        self.assertIn("<clave>", error.detalle)

    def test_tiempo_agotado(self):
        servidor = self._servidor(estado=200, cuerpo="{}", demora=1.5)
        with self.assertRaises(protocolos.ErrorIA) as salida:
            envio_ia.enviar(self._pedido_a(servidor), CLAVE, 0.2)
        self.assertEqual(salida.exception.tipo,
                         protocolos.TIEMPO_AGOTADO)

    def test_puerto_cerrado_es_sin_red(self):
        with socket.socket() as sondeo:
            sondeo.bind(("127.0.0.1", 0))
            puerto = sondeo.getsockname()[1]
        pedido = _pedido_chat()
        pedido.url = f"http://127.0.0.1:{puerto}/chat/completions"
        with self.assertRaises(protocolos.ErrorIA) as salida:
            envio_ia.enviar(pedido, CLAVE, 5)
        self.assertEqual(salida.exception.tipo, protocolos.SIN_RED)


if __name__ == "__main__":
    unittest.main()
