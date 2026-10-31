"""Canal de actualización de yt-dlp: configuración y repositorio por canal.

Sin ventanas: la red es el único doble (`urlopen`). Todo lo demás es el
cableado real, con un `config.ini` temporal.
"""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bellbird.core import config
from bellbird.downloads import ytdlp_actualizar
from tests.rutas_temporales import redirigir_rutas


ESTABLE_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
DIARIO_API = ("https://api.github.com/repos/yt-dlp/"
              "yt-dlp-nightly-builds/releases/latest")


class _RespuestaFalsa:
    """Doble de la respuesta de `urlopen`: sirve texto o binario por trozos."""

    def __init__(self, cuerpo, trozos=False):
        self._cuerpo = cuerpo
        self._trozos = trozos
        self._pos = 0
        if isinstance(cuerpo, bytes):
            self.headers = {"Content-Length": str(len(cuerpo))}
        else:
            self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, n=-1):
        if isinstance(self._cuerpo, str):
            dato, self._cuerpo = self._cuerpo, ""
            return dato
        if not self._trozos or n is None or n < 0:
            dato = self._cuerpo[self._pos:]
            self._pos = len(self._cuerpo)
            return dato
        dato = self._cuerpo[self._pos:self._pos + n]
        self._pos += len(dato)
        return dato


class _RedFalsa:
    """Sirve la API, las firmas y el binario de cada canal, y anota pedidos."""

    def __init__(self):
        self.pedidos = []
        self.binario = b"yt-dlp falso"
        self.firma = hashlib.sha256(self.binario).hexdigest()

    def release(self, repo, etiqueta):
        base = f"https://github.com/{repo}/releases/download/{etiqueta}"
        return {"tag_name": etiqueta,
                "assets": [
                    {"name": "yt-dlp.exe",
                     "browser_download_url": base + "/yt-dlp.exe"},
                    {"name": "SHA2-256SUMS",
                     "browser_download_url": base + "/SHA2-256SUMS"}]}

    def __call__(self, solicitud, timeout=None):
        url = solicitud.full_url
        self.pedidos.append(url)
        if url == ESTABLE_API:
            cuerpo = json.dumps(self.release("yt-dlp/yt-dlp", "2026.01.01"))
            return _RespuestaFalsa(cuerpo)
        if url == DIARIO_API:
            cuerpo = json.dumps(self.release("yt-dlp/yt-dlp-nightly-builds",
                                             "2026.10.29.232701"))
            return _RespuestaFalsa(cuerpo)
        if url.endswith("/SHA2-256SUMS"):
            return _RespuestaFalsa((self.firma + "  yt-dlp.exe\n").encode())
        return _RespuestaFalsa(self.binario, trozos=True)


class TestCanalYtdlp(unittest.TestCase):

    def _carpeta(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ruta = Path(tmp.name)
        (ruta / "config.ini").write_text(config._CONFIG_FALLBACK,
                                         encoding="utf-8")
        return ruta

    def _opciones_base(self):
        return {"formato": "mp4", "bitrate": 192, "resolucion": 0,
                "carpeta": "/x/y", "enumerar": False, "simultaneas": 2,
                "limite": 0, "carpeta_lista": False,
                "plantilla": "titulo_id"}

    def test_guardar_diario_se_lee(self):
        ruta = self._carpeta()
        with redirigir_rutas(ruta):
            opciones = self._opciones_base()
            opciones["canal_ytdlp"] = "diario"
            config.guardar_opciones_descarga(opciones)
            self.assertEqual(config.obtener_opciones_descarga()["canal_ytdlp"],
                             "diario")

    def test_sin_clave_vale_estable(self):
        ruta = self._carpeta()
        with redirigir_rutas(ruta):
            self.assertEqual(config.obtener_opciones_descarga()["canal_ytdlp"],
                             "estable")

    def test_valor_raro_vale_estable(self):
        ruta = self._carpeta()
        (ruta / "config.ini").write_text("[descargas]\ncanal_ytdlp = beta\n",
                                         encoding="utf-8")
        with redirigir_rutas(ruta):
            self.assertEqual(config.obtener_opciones_descarga()["canal_ytdlp"],
                             "estable")
            opciones = self._opciones_base()
            opciones["canal_ytdlp"] = "beta"
            config.guardar_opciones_descarga(opciones)
            self.assertEqual(config.obtener_opciones_descarga()["canal_ytdlp"],
                             "estable")

    def test_actualizar_con_diario_pide_repositorio_diario(self):
        ruta = self._carpeta()
        (ruta / "config.ini").write_text(
            "[descargas]\ncanal_ytdlp = diario\n", encoding="utf-8")
        red = _RedFalsa()
        with redirigir_rutas(ruta), \
                mock.patch.object(ytdlp_actualizar, "urlopen", red):
            estado = ytdlp_actualizar.actualizar_ytdlp()
        self.assertIn(DIARIO_API, red.pedidos)
        self.assertNotIn(ESTABLE_API, red.pedidos)
        self.assertTrue(any("nightly-builds" in pedido
                            for pedido in red.pedidos
                            if pedido.endswith("/yt-dlp.exe")))
        self.assertEqual(estado[0], "actualizado")
        self.assertEqual(estado[2], "2026.10.29.232701")

    def test_actualizar_sin_clave_pide_estable(self):
        ruta = self._carpeta()
        red = _RedFalsa()
        with redirigir_rutas(ruta), \
                mock.patch.object(ytdlp_actualizar, "urlopen", red):
            estado = ytdlp_actualizar.actualizar_ytdlp()
        self.assertIn(ESTABLE_API, red.pedidos)
        self.assertNotIn(DIARIO_API, red.pedidos)
        self.assertEqual(estado[0], "actualizado")
        self.assertEqual(estado[2], "2026.01.01")

    def test_asegurar_con_diario_pide_estable(self):
        ruta = self._carpeta()
        (ruta / "config.ini").write_text(
            "[descargas]\ncanal_ytdlp = diario\n", encoding="utf-8")
        destino = ruta / "yt-dlp.exe"
        red = _RedFalsa()
        with redirigir_rutas(ruta), \
                mock.patch.object(ytdlp_actualizar, "urlopen", red):
            resultado = ytdlp_actualizar.asegurar_ytdlp(destino)
        self.assertIn(ESTABLE_API, red.pedidos)
        self.assertNotIn(DIARIO_API, red.pedidos)
        self.assertTrue(resultado.correcta)
        self.assertEqual(destino.read_bytes(), red.binario)

    def test_cambiar_de_canal_instala_aunque_sea_mas_vieja(self):
        ruta = self._carpeta()
        red = _RedFalsa()
        from bellbird.downloads import ytdlp_bin
        with redirigir_rutas(ruta), \
                mock.patch.object(ytdlp_actualizar, "urlopen", red), \
                mock.patch.object(ytdlp_bin, "ruta_ytdlp",
                                  return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin, "version_ytdlp",
                                  return_value="2026.10.29.232701"), \
                mock.patch.object(ytdlp_actualizar, "descargar_ytdlp",
                                  return_value=ytdlp_actualizar.ResultadoDescarga(
                                      True, "yt-dlp actualizado")) as descargar:
            estado = ytdlp_actualizar.actualizar_ytdlp()
        self.assertEqual(estado[0], "actualizado")
        descargar.assert_called_once()


if __name__ == "__main__":
    unittest.main()
