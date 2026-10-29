"""Pruebas de la autocomprobación del paquete armado."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from babel.messages import catalog, pofile

from scripts import traducciones
from bellbird.core import autocomprobacion
from bellbird.core import paths


RAIZ = Path(__file__).resolve().parents[1]


class TestComprobar(unittest.TestCase):

    def test_una_pieza_que_falla_no_frena_las_demas(self):
        corridas = []

        def pasa():
            corridas.append("pasa")

        def falla():
            corridas.append("falla")
            raise ImportError("x")

        def pasa_dos():
            corridas.append("pasa_dos")

        piezas = (("Uno", pasa), ("Dos", falla), ("Tres", pasa_dos))
        resultados = autocomprobacion.comprobar(piezas)

        self.assertEqual(corridas, ["pasa", "falla", "pasa_dos"])
        self.assertEqual(resultados, [
            ("Uno", None),
            ("Dos", "ImportError: x"),
            ("Tres", None),
        ])


class TestLineas(unittest.TestCase):

    def test_ok_y_falla(self):
        self.assertEqual(
            autocomprobacion.lineas(
                [("wxPython", None), ("Prism", "ImportError: x")]),
            ["OK wxPython", "FALLA Prism: ImportError: x"])


class TestPrincipal(unittest.TestCase):

    def test_todo_ok_devuelve_cero_y_escribe_las_lineas(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "r.txt"
            with mock.patch.object(
                    autocomprobacion, "comprobar",
                    return_value=[("wxPython", None), ("VLC", None)]):
                codigo = autocomprobacion.principal([str(destino)])
            self.assertEqual(codigo, 0)
            self.assertEqual(destino.read_text(encoding="utf-8"),
                             "OK wxPython\nOK VLC\n")

    def test_una_falla_devuelve_uno_y_escribe_las_lineas(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "r.txt"
            with mock.patch.object(
                    autocomprobacion, "comprobar",
                    return_value=[("wxPython", None),
                                  ("Prism", "ImportError: x")]):
                codigo = autocomprobacion.principal([str(destino)])
            self.assertEqual(codigo, 1)
            self.assertEqual(destino.read_text(encoding="utf-8"),
                             "OK wxPython\nFALLA Prism: ImportError: x\n")

    def test_ruta_en_carpeta_inexistente_devuelve_dos(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "no-existe" / "r.txt"
            with mock.patch.object(
                    autocomprobacion, "comprobar",
                    return_value=[("wxPython", None)]):
                codigo = autocomprobacion.principal([str(destino)])
            self.assertEqual(codigo, 2)


class TestPiezaIdiomas(unittest.TestCase):
    """La pieza Idiomas carga cada catálogo compilado, sin red de fallback."""

    def _pieza(self):
        piezas = dict(autocomprobacion.PIEZAS)
        self.assertIn("Idiomas", piezas)
        return piezas["Idiomas"]

    def test_sin_catalogos_da_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(paths, "carpeta_idiomas",
                                   return_value=Path(tmp)):
                resultados = autocomprobacion.comprobar(
                    [("Idiomas", self._pieza())])
        self.assertEqual(resultados, [("Idiomas", None)])

    def test_mo_bueno_compilado_da_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            idiomas = Path(tmp)
            destino = idiomas / "en" / "LC_MESSAGES"
            destino.mkdir(parents=True)
            catalogo = catalog.Catalog(locale="en", domain="bellbird")
            catalogo.add("Guardado", string="Saved")
            with (destino / "bellbird.po").open("wb") as salida:
                pofile.write_po(salida, catalogo)
            compilados = traducciones.compilar(idiomas)
            self.assertEqual(len(compilados), 1)
            with mock.patch.object(paths, "carpeta_idiomas",
                                   return_value=idiomas):
                resultados = autocomprobacion.comprobar(
                    [("Idiomas", self._pieza())])
        self.assertEqual(resultados, [("Idiomas", None)])

    def test_mo_basura_da_falla(self):
        with tempfile.TemporaryDirectory() as tmp:
            idiomas = Path(tmp)
            destino = idiomas / "en" / "LC_MESSAGES"
            destino.mkdir(parents=True)
            (destino / "bellbird.mo").write_bytes(
                b"esto no es un catalogo gettext")
            with mock.patch.object(paths, "carpeta_idiomas",
                                   return_value=idiomas):
                resultados = autocomprobacion.comprobar(
                    [("Idiomas", self._pieza())])
        self.assertEqual(len(resultados), 1)
        nombre, error = resultados[0]
        self.assertEqual(nombre, "Idiomas")
        self.assertIsNotNone(error)


class TestPiezas(unittest.TestCase):

    def test_los_ocho_nombres_en_orden(self):
        self.assertEqual(
            [nombre for nombre, _ in autocomprobacion.PIEZAS],
            ["wxPython", "Prism", "pytchat", "TikTokLive", "API de Google",
             "yt-dlp", "VLC", "Idiomas"])


class TestPiezasReales(unittest.TestCase):
    """Corre las piezas de verdad en este .venv, sin abrir ventana alguna."""

    def test_las_piezas_criticas_cargan(self):
        resultados = dict(autocomprobacion.comprobar())
        for nombre in ("pytchat", "TikTokLive", "API de Google", "yt-dlp",
                       "Prism"):
            self.assertIsNone(resultados[nombre],
                              f"{nombre}: {resultados[nombre]}")
        self.assertIn("wxPython", resultados)
        self.assertIn("VLC", resultados)


class TestCorridaRealDeMain(unittest.TestCase):
    """Lanza `main.py --autocomprobar` de verdad, en un subproceso."""

    def test_escribe_ocho_ok_y_sale_cero(self):
        destino_data = RAIZ / "data"
        habia_data = destino_data.exists()
        with tempfile.TemporaryDirectory() as tmp:
            archivo = Path(tmp) / "autocomp.txt"
            resultado = subprocess.run(
                [sys.executable, str(RAIZ / "main.py"), "--autocomprobar",
                 str(archivo)],
                cwd=str(RAIZ), capture_output=True, timeout=120)
            self.assertEqual(
                resultado.returncode, 0,
                resultado.stderr.decode("utf-8", "replace"))
            lineas = archivo.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lineas, [
            "OK wxPython",
            "OK Prism",
            "OK pytchat",
            "OK TikTokLive",
            "OK API de Google",
            "OK yt-dlp",
            "OK VLC",
            "OK Idiomas",
        ])
        if not habia_data:
            self.assertFalse(destino_data.exists())


if __name__ == "__main__":
    unittest.main()
