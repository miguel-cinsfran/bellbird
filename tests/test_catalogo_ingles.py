"""Prueba del catálogo inglés: compila, carga y revisa el .po del repositorio."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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
            [sys.executable, "herramientas/revisar-po.py", str(po)],
            capture_output=True, text=True, cwd=RAIZ, check=False)
        self.assertEqual(
            proceso.returncode, 0, proceso.stdout + proceso.stderr)


if __name__ == "__main__":
    unittest.main()
