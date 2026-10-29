"""Prueba del catálogo inglés: compila, carga y revisa el .po del repositorio."""

import contextlib
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from babel.messages import catalog, pofile

from scripts import traducciones
from ytchat.core import idioma

RAIZ = Path(__file__).resolve().parent.parent


class TestCatalogoIngles(unittest.TestCase):
    """El .po inglés compila, traduce textos conocidos y pasa revisar-po."""

    def tearDown(self):
        idioma._reiniciar()

    def test_catalogo_ingles_compila_traduce_y_pasa_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = traducciones.ruta_po(Path(tmp), "en")
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(traducciones.ruta_po(
                traducciones.CARPETA_IDIOMAS, "en"), destino)
            compilados = traducciones.compilar(carpeta_idiomas=Path(tmp))
            self.assertEqual(len(compilados), 1)
            idioma.instalar("en", Path(tmp))
            self.assertEqual(idioma._("&Conectar"), "&Connect")
            self.assertEqual(idioma._("Preferencias"), "Preferences")
            self.assertEqual(
                idioma.ngettext("{n} hora", "{n} horas", 1), "{n} hour")
            self.assertEqual(
                idioma.ngettext("{n} hora", "{n} horas", 5), "{n} hours")
        po = traducciones.ruta_po(traducciones.CARPETA_IDIOMAS, "en")
        proceso = subprocess.run(
            [sys.executable, "scripts/traducciones.py", "revisar", "en"],
            capture_output=True, text=True, cwd=RAIZ, check=False)
        self.assertEqual(
            proceso.returncode, 0, proceso.stdout + proceso.stderr)


def _escribir_po(ruta, entradas):
    """Escribe un .po temporal con (msgid, msgstr) para probar `revisar`."""
    catalogo = catalog.Catalog(locale="en", domain="bellbird")
    for original, traducido in entradas:
        catalogo.add(original, traducido, locations=[("app.py", 1)])
    with ruta.open("wb") as salida:
        pofile.write_po(salida, catalogo)


class TestRevisar(unittest.TestCase):
    """La orden `revisar` detecta huecos cambiados en un .po cualquiera."""

    def _revisar(self, entradas):
        with tempfile.TemporaryDirectory() as tmp:
            po = Path(tmp) / "bellbird.po"
            _escribir_po(po, entradas)
            salida = io.StringIO()
            with contextlib.redirect_stdout(salida):
                codigo = traducciones.revisar(po)
            return codigo, salida.getvalue()

    def test_po_bueno_sale_0(self):
        codigo, _salida = self._revisar(
            [("Hola {nombre}", "Hello {nombre}")])
        self.assertEqual(codigo, 0)

    def test_hueco_cambiado_sale_1_y_nombra_la_entrada(self):
        codigo, salida = self._revisar(
            [("Ver {total}", "See {otro}")])
        self.assertEqual(codigo, 1)
        self.assertIn("Ver {total}", salida)


if __name__ == "__main__":
    unittest.main()
