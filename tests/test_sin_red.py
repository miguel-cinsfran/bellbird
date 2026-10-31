"""La suite no sale a internet: el bloqueo de tests/__init__.py."""

import http.server
import os
import socket
import threading
import time
import unittest


class _Manejador(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, formato, *args):
        pass


class TestBloqueo(unittest.TestCase):

    @unittest.skipUnless(
        os.environ.get("BELLBIRD_PRUEBAS_CON_RED") != "1",
        "prueba del bloqueo desactivada: BELLBIRD_PRUEBAS_CON_RED=1")
    def test_destino_publico_falla_sin_esperar(self):
        sock = socket.socket()
        sock.settimeout(2.0)
        inicio = time.monotonic()
        try:
            with self.assertRaises(OSError) as capturado:
                sock.connect(("192.0.2.1", 80))
        finally:
            sock.close()
        demora = time.monotonic() - inicio
        self.assertIn("192.0.2.1", str(capturado.exception))
        self.assertLess(demora, 1.0)

    def test_servidor_local_funciona(self):
        servidor = http.server.HTTPServer(("127.0.0.1", 0), _Manejador)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        try:
            for host in ("127.0.0.1", "localhost"):
                with self.subTest(host=host):
                    sock = socket.socket()
                    sock.settimeout(2.0)
                    try:
                        sock.connect((host, servidor.server_port))
                        sock.sendall(b"GET / HTTP/1.0\r\n\r\n")
                        datos = b""
                        while True:
                            trozo = sock.recv(1024)
                            if not trozo:
                                break
                            datos += trozo
                    finally:
                        sock.close()
                    self.assertIn(b"ok", datos)
        finally:
            servidor.shutdown()
            servidor.server_close()
            hilo.join(timeout=2.0)


if __name__ == "__main__":
    unittest.main()
