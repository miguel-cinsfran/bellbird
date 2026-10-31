"""Pruebas de scripts/bajar_deno.py, sin red: el zip se arma en la prueba."""

import hashlib
import unittest
import zipfile
from pathlib import Path
import tempfile

from scripts import bajar_deno


class TestFirmaGetFileHash(unittest.TestCase):

    def test_lee_la_linea_hash_en_mayusculas(self):
        texto = ("Algorithm : SHA256\r\n"
                 "Hash      : AB12AB12AB12AB12AB12AB12AB12AB12AB12AB12AB12AB12AB12AB12AB12AB12\r\n")
        firma = bajar_deno.firma_desde_get_file_hash(texto)
        self.assertEqual(
            firma, "ab12ab12ab12ab12ab12ab12ab12ab12ab12ab12ab12ab12ab12ab12ab12ab12")

    def test_sin_linea_hash_da_vacio(self):
        self.assertEqual(bajar_deno.firma_desde_get_file_hash("sin hash"), "")


class TestInstalarZip(unittest.TestCase):

    def _zip_con_deno(self, carpeta: Path, contenido: bytes) -> Path:
        ruta = carpeta / "deno.zip"
        with zipfile.ZipFile(ruta, "w") as archivo:
            archivo.writestr("deno.exe", contenido)
        return ruta

    def test_firma_distinta_no_deja_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            ruta_zip = self._zip_con_deno(tmp, b"falso deno")
            destino = tmp / "salida"
            destino.mkdir()
            ok, _motivo = bajar_deno.instalar_zip(
                ruta_zip, destino, "0" * 64)
            self.assertFalse(ok)
            self.assertFalse((destino / "deno.exe").exists())

    def test_firma_correcta_deja_deno(self):
        contenido = b"falso deno"
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            ruta_zip = self._zip_con_deno(tmp, contenido)
            firma = hashlib.sha256(ruta_zip.read_bytes()).hexdigest()
            destino = tmp / "salida"
            destino.mkdir()
            ok, _motivo = bajar_deno.instalar_zip(ruta_zip, destino, firma)
            self.assertTrue(ok)
            self.assertEqual((destino / "deno.exe").read_bytes(), contenido)


if __name__ == "__main__":
    unittest.main()
