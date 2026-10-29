"""Pruebas de `ytchat.player.flujo_tiktok`, sin wx ni red externa."""

import http.server
import io
import threading
import time
import unittest
import urllib.error
from unittest import mock

from ytchat.player import flujo_tiktok


class _Respuesta:
    def __init__(self, estado=200, tipo="video/mp4", cuerpo=b"0123456789"):
        self.status = estado
        self.headers = {"Content-Type": tipo}
        self._cuerpo = cuerpo
        self.cerrada = False

    def read(self, cantidad=None):
        return self._cuerpo[:cantidad] if cantidad is not None else self._cuerpo

    def close(self):
        self.cerrada = True


class TestResumenUrl(unittest.TestCase):

    def test_con_expire_dice_vence_y_cuanto_queda(self):
        url = ("https://example.com/live/stream.flv"
               "?expire=1700000000&sign=abcdef123456&otro=1")
        resumen = flujo_tiktok.resumen_url(url, ahora=1699999900)
        vence = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(1700000000))
        self.assertEqual(
            resumen,
            f"servidor=example.com ruta=/live/stream.flv "
            f"vence={vence} quedan=100 s")

    def test_sin_expire_no_dice_vence_ni_queda(self):
        url = "https://example.com/live/stream.flv?sign=abcdef123456"
        resumen = flujo_tiktok.resumen_url(url, ahora=1700000000)
        self.assertEqual(
            resumen, "servidor=example.com ruta=/live/stream.flv")

    def test_no_copia_la_firma_ni_la_consulta(self):
        url = ("https://example.com/live/stream.flv"
               "?expire=1700000000&sign=abcdef123456")
        resumen = flujo_tiktok.resumen_url(url, ahora=1699999900)
        self.assertNotIn("sign", resumen)
        self.assertNotIn("abcdef123456", resumen)
        self.assertNotIn("expire", resumen)


class TestMismoFlujo(unittest.TestCase):

    URL_A = ("https://pull-flv-l1-sg01.tiktokcdn.com"
             "/game/stream-2137954827079778396_hd.flv"
             "?expire=1761247296&sign=aaaa")
    URL_B = ("https://pull-flv-l1-sg01.tiktokcdn.com"
             "/game/stream-2137954827079778396_hd.flv"
             "?expire=1761247356&sign=bbbb")
    URL_OTRA_RUTA = ("https://pull-flv-l1-sg01.tiktokcdn.com"
                     "/game/stream-9999_hd.flv"
                     "?expire=1761247356&sign=bbbb")

    def test_misma_ruta_con_distinta_firma_es_mismo_flujo(self):
        self.assertTrue(flujo_tiktok.mismo_flujo(self.URL_A, self.URL_B))

    def test_distinta_ruta_no_es_mismo_flujo(self):
        self.assertFalse(flujo_tiktok.mismo_flujo(self.URL_A, self.URL_OTRA_RUTA))

    def test_distinto_servidor_no_es_mismo_flujo(self):
        otra = self.URL_B.replace("sg01", "sg02")
        self.assertFalse(flujo_tiktok.mismo_flujo(self.URL_A, otra))

    def test_con_una_vacia_no_es_mismo_flujo(self):
        self.assertFalse(flujo_tiktok.mismo_flujo("", self.URL_B))
        self.assertFalse(flujo_tiktok.mismo_flujo(self.URL_A, ""))


class TestSondear(unittest.TestCase):

    def test_pide_rango_y_resume_codigo_tipo_y_bytes(self):
        vistas = []

        def abrir(peticion, timeout=None):
            vistas.append((peticion, timeout))
            return _Respuesta()

        resultado = flujo_tiktok.sondear(
            "https://example.com/flujo.flv", abrir=abrir, plazo_s=3)
        self.assertEqual(resultado, "http=200 tipo=video/mp4 bytes=10")
        peticion, timeout = vistas[0]
        self.assertEqual(peticion.get_header("Range"), "bytes=0-2047")
        self.assertEqual(timeout, 3)

    def test_un_403_con_cuerpo_se_informa_como_http(self):
        def abrir(peticion, timeout=None):
            raise urllib.error.HTTPError(
                peticion.full_url, 403, "Forbidden",
                {"Content-Type": "text/plain"}, io.BytesIO(b"no"))

        resultado = flujo_tiktok.sondear(
            "https://example.com/flujo.flv", abrir=abrir)
        self.assertEqual(resultado, "http=403 tipo=text/plain bytes=2")

    def test_un_timeout_se_informa_como_error_y_no_lanza(self):
        def abrir(peticion, timeout=None):
            raise TimeoutError("sin respuesta")

        resultado = flujo_tiktok.sondear(
            "https://example.com/flujo.flv", abrir=abrir)
        self.assertEqual(resultado, "error=TimeoutError: sin respuesta")

    def test_una_excepcion_cualquiera_se_informa_y_no_lanza(self):
        def abrir(peticion, timeout=None):
            raise RuntimeError("roto")

        resultado = flujo_tiktok.sondear(
            "https://example.com/flujo.flv", abrir=abrir)
        self.assertEqual(resultado, "error=RuntimeError: roto")


class _Manejador404(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"no")

    def log_message(self, formato, *argumentos):
        pass


class TestFronteraReal(unittest.TestCase):

    def test_contra_un_servidor_local_que_contesta_404(self):
        servidor = http.server.HTTPServer(("127.0.0.1", 0), _Manejador404)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        try:
            puerto = servidor.server_address[1]
            resultado = flujo_tiktok.sondear(
                f"http://127.0.0.1:{puerto}/nada")
        finally:
            servidor.shutdown()
            servidor.server_close()
            hilo.join(2)
        self.assertIn("http=404", resultado)


class TestSondearEnHilo(unittest.TestCase):

    def test_usa_un_hilo_daemon_llamado_tiktok_sonda(self):
        hilos = []
        real = flujo_tiktok.diagnostico.crear_hilo

        def crear(target, nombre, **extra):
            hilo = real(target, nombre, **extra)
            hilos.append(hilo)
            return hilo

        with mock.patch.object(flujo_tiktok.diagnostico, "crear_hilo",
                               side_effect=crear), \
                mock.patch.object(flujo_tiktok, "sondear",
                                  return_value="http=200 tipo=video/mp4 bytes=2"), \
                mock.patch.object(flujo_tiktok.logger, "warning") as aviso:
            flujo_tiktok.sondear_en_hilo(
                "https://example.com/flujo.flv?expire=1700000000")
            hilos[0].join(2)

        self.assertEqual(hilos[0].name, "tiktok-sonda")
        self.assertTrue(hilos[0].daemon)
        aviso.assert_called_once()
        argumentos = aviso.call_args.args
        self.assertEqual(argumentos[0], "TIKTOK_FLUJO_SONDA %s %s")
        self.assertIn("servidor=example.com", argumentos[1])
        self.assertIn("ruta=/flujo.flv", argumentos[1])
        self.assertEqual(argumentos[2], "http=200 tipo=video/mp4 bytes=2")


if __name__ == "__main__":
    unittest.main()
