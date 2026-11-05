"""Pruebas del canal de actualizaciones, sin interfaz.

La lista de publicaciones se arma a mano y la descarga se prueba contra un
servidor local, como el de `tests/test_actualizacion.py`.
"""

import http.server
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from guyrapu.core import canal_app
from tests.rutas_temporales import redirigir_rutas


def _publicacion(tag, draft=False, con_paquete=True,
                 base="https://ejemplo.com"):
    publicacion = {
        "tag_name": tag,
        "body": "",
        "draft": draft,
        "prerelease": "-beta." in tag,
    }
    if con_paquete:
        publicacion["assets"] = [
            {"name": "App.zip", "browser_download_url": f"{base}/App.zip",
             "size": 10},
            {"name": "App.zip.sha256",
             "browser_download_url": f"{base}/App.zip.sha256"},
        ]
    return publicacion


class ServidorPublicaciones(http.server.BaseHTTPRequestHandler):
    contenido = []

    def do_GET(self):
        if self.path != "/releases":
            self.send_error(404)
            return
        cuerpo = json.dumps(type(self).contenido).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *args):
        pass


class TestNormalizarCanal(unittest.TestCase):

    def test_acepta_los_dos_canales_y_lo_demas_vale_estable(self):
        casos = (
            ("estable", "estable"),
            (" Beta ", "beta"),
            ("BETA", "beta"),
            ("raro", "estable"),
            ("", "estable"),
            (None, "estable"),
            (3, "estable"),
        )
        for valor, esperado in casos:
            with self.subTest(valor=valor):
                self.assertEqual(canal_app.normalizar_canal(valor), esperado)


class TestCanalGuardado(unittest.TestCase):

    def _config(self, texto):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ruta = Path(tmp.name) / "config.ini"
        ruta.write_text(texto, encoding="utf-8")
        return tmp.name

    def test_lee_el_canal_y_lo_demas_vale_estable(self):
        casos = (
            ("[actualizaciones]\ncanal = beta\n", "beta"),
            ("[actualizaciones]\ncanal = estable\n", "estable"),
            ("[actualizaciones]\ncanal = raro\n", "estable"),
            ("[actualizaciones]\nbuscar_al_iniciar = true\n", "estable"),
            ("[ui]\ntamanio_fuente_chat = 12\n", "estable"),
            ("", "estable"),
        )
        for texto, esperado in casos:
            with self.subTest(texto=texto):
                with redirigir_rutas(self._config(texto)):
                    self.assertEqual(canal_app.canal_guardado(), esperado)

    def test_no_escribe_el_ini(self):
        carpeta = self._config("[actualizaciones]\ncanal = raro\n")
        ruta = Path(carpeta) / "config.ini"
        antes = ruta.read_text(encoding="utf-8")
        with redirigir_rutas(carpeta):
            self.assertEqual(canal_app.canal_guardado(), "estable")
        self.assertEqual(ruta.read_text(encoding="utf-8"), antes)


class TestElegirPublicacion(unittest.TestCase):

    def test_elige_la_mayor_entre_betas_y_estables(self):
        casos = (
            (["3.0.0-beta.10", "3.0.0-beta.2", "2.9.0"], "3.0.0-beta.10"),
            (["3.0.0-beta.10", "3.0.0", "2.9.0"], "3.0.0"),
            (["3.0.0-beta.1", "3.0.1"], "3.0.1"),
        )
        for tags, esperada in casos:
            with self.subTest(tags=tags):
                publicaciones = [_publicacion(tag) for tag in tags]
                elegido = canal_app.elegir_publicacion(publicaciones)
                self.assertEqual(elegido.version, esperada)

    def test_saltea_borradores_y_publicaciones_sin_paquete(self):
        publicaciones = [
            _publicacion("3.2.0-beta.1", draft=True),
            _publicacion("3.1.0", con_paquete=False),
            _publicacion("3.0.0"),
        ]
        elegido = canal_app.elegir_publicacion(publicaciones)
        self.assertEqual(elegido.version, "3.0.0")

    def test_sin_publicaciones_validas_da_none(self):
        self.assertIsNone(canal_app.elegir_publicacion([]))
        self.assertIsNone(canal_app.elegir_publicacion(None))
        self.assertIsNone(canal_app.elegir_publicacion(
            [_publicacion("3.0.0", draft=True)]))


class TestConsultarUltimaBeta(unittest.TestCase):

    def _servidor(self):
        servidor = http.server.HTTPServer(("127.0.0.1", 0),
                                          ServidorPublicaciones)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        self.addCleanup(servidor.server_close)
        self.addCleanup(servidor.shutdown)
        return servidor

    def test_pide_la_lista_y_devuelve_la_mayor(self):
        ServidorPublicaciones.contenido = [
            _publicacion("2.5.1"),
            _publicacion("3.0.0-beta.4"),
        ]
        servidor = self._servidor()
        url = f"http://127.0.0.1:{servidor.server_port}/releases"
        with mock.patch.object(canal_app, "URL_PUBLICACIONES", url):
            elegido = canal_app.consultar_ultima_beta()
        self.assertEqual("3.0.0-beta.4", elegido.version)

    def test_error_de_red_da_none(self):
        with mock.patch.object(canal_app, "urlopen",
                               side_effect=URLError("sin red")):
            self.assertIsNone(canal_app.consultar_ultima_beta())


if __name__ == "__main__":
    unittest.main()
