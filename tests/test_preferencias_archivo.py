"""Pruebas de exportar, importar y restablecer las preferencias.

Lógica pura con archivos de verdad en una carpeta temporal y las rutas de
`paths` apuntadas ahí. No abre ventanas.
"""

import tempfile
import unittest
from pathlib import Path

from bellbird.core import config_predeterminada as pred
from bellbird.core import paths
from bellbird.core import preferencias_archivo as prefs
from tests.pseudo_prueba import con_pseudo
from tests.rutas_temporales import redirigir_rutas


class TestExportar(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.datos = Path(self._tmp.name)
        parche = redirigir_rutas(self.datos)
        parche.__enter__()
        self.addCleanup(parche.__exit__, None, None, None)

    def test_exportar_copia_el_ini_tal_cual(self):
        contenido = "[voz]\nmotor = sapi\n[ui]\ntema = default\n"
        (self.datos / "config.ini").write_text(contenido, encoding="utf-8")
        destino = self.datos / "copia.ini"
        prefs.exportar(destino)
        self.assertEqual(destino.read_bytes(),
                         (self.datos / "config.ini").read_bytes())

    def test_exportar_sin_ini_escribe_el_de_fabrica(self):
        destino = self.datos / "copia.ini"
        prefs.exportar(destino)
        self.assertEqual(destino.read_text(encoding="utf-8"),
                         pred.generar_texto())

    def test_ninguna_operacion_toca_las_credenciales(self):
        secreto = '{"elevenlabs_clave": "secreta"}'
        (self.datos / "credenciales.json").write_text(secreto, encoding="utf-8")
        (self.datos / "config.ini").write_text("[voz]\nmotor = sapi\n",
                                               encoding="utf-8")
        prefs.exportar(self.datos / "copia.ini")
        prefs.importar(self.datos / "copia.ini")
        prefs.restablecer()
        self.assertEqual((self.datos / "credenciales.json").read_text(
            encoding="utf-8"), secreto)


class TestMotivoNoImportable(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.datos = Path(self._tmp.name)

    def _origen(self, nombre, contenido=None, bytes_=None):
        ruta = self.datos / nombre
        if bytes_ is not None:
            ruta.write_bytes(bytes_)
        elif contenido is not None:
            ruta.write_text(contenido, encoding="utf-8")
        return ruta

    def test_ini_valido_se_puede_importar(self):
        ruta = self._origen("bueno.ini", "[voz]\nmotor = sapi\n")
        self.assertIsNone(prefs.motivo_no_importable(ruta))

    def test_falta_el_archivo_no_se_puede_leer(self):
        motivo = prefs.motivo_no_importable(self.datos / "no-existe.ini")
        self.assertIsNotNone(motivo)
        self.assertIn("leer", motivo)

    def test_texto_que_no_es_ini_se_rechaza(self):
        ruta = self._origen("texto.txt", "esto no es un ini\nni [seccion\n")
        motivo = prefs.motivo_no_importable(ruta)
        self.assertIsNotNone(motivo)
        self.assertIn("preferencias", motivo)

    def test_ini_sin_secciones_conocidas_se_rechaza(self):
        ruta = self._origen("otro.ini", "[otro]\nclave = 1\n")
        self.assertIsNotNone(prefs.motivo_no_importable(ruta))

    def test_mas_de_un_mega_se_rechaza(self):
        ruta = self._origen("grande.ini",
                            bytes_=b"[voz]\n" + b"x" * (prefs.LIMITE_BYTES + 1))
        motivo = prefs.motivo_no_importable(ruta)
        self.assertIsNotNone(motivo)
        self.assertIn("1 MB", motivo)


class TestImportar(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.datos = Path(self._tmp.name)
        parche = redirigir_rutas(self.datos)
        parche.__enter__()
        self.addCleanup(parche.__exit__, None, None, None)

    def test_ini_valido_se_importa_y_deja_respaldo(self):
        anterior = "[voz]\nmotor = sapi\n"
        nuevo = "[voz]\nmotor = onecore\n"
        (self.datos / "config.ini").write_text(anterior, encoding="utf-8")
        origen = self.datos / "nuevo.ini"
        origen.write_text(nuevo, encoding="utf-8")
        prefs.importar(origen)
        self.assertEqual((self.datos / "config.ini").read_text(
            encoding="utf-8"), nuevo)
        # La copia de respaldo es una sola y guarda lo anterior.
        self.assertEqual(paths.config_anterior(), self.datos / "config.anterior.ini")
        self.assertEqual((self.datos / "config.anterior.ini").read_text(
            encoding="utf-8"), anterior)

    def test_invalido_no_toca_el_ini(self):
        anterior = "[voz]\nmotor = sapi\n"
        (self.datos / "config.ini").write_text(anterior, encoding="utf-8")
        origen = self.datos / "malo.txt"
        origen.write_text("no es un ini\n", encoding="utf-8")
        with self.assertRaises(prefs.ErrorPreferencias):
            prefs.importar(origen)
        self.assertEqual((self.datos / "config.ini").read_text(
            encoding="utf-8"), anterior)
        self.assertFalse((self.datos / "config.anterior.ini").exists())

    def test_sin_secciones_conocidas_no_toca_el_ini(self):
        anterior = "[voz]\nmotor = sapi\n"
        (self.datos / "config.ini").write_text(anterior, encoding="utf-8")
        origen = self.datos / "otro.ini"
        origen.write_text("[otro]\nclave = 1\n", encoding="utf-8")
        with self.assertRaises(prefs.ErrorPreferencias):
            prefs.importar(origen)
        self.assertEqual((self.datos / "config.ini").read_text(
            encoding="utf-8"), anterior)

    def test_muy_grande_no_toca_el_ini(self):
        anterior = "[voz]\nmotor = sapi\n"
        (self.datos / "config.ini").write_text(anterior, encoding="utf-8")
        origen = self.datos / "grande.ini"
        origen.write_bytes(b"[voz]\n" + b"x" * (prefs.LIMITE_BYTES + 1))
        with self.assertRaises(prefs.ErrorPreferencias):
            prefs.importar(origen)
        self.assertEqual((self.datos / "config.ini").read_text(
            encoding="utf-8"), anterior)


class TestRestablecer(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.datos = Path(self._tmp.name)
        parche = redirigir_rutas(self.datos)
        parche.__enter__()
        self.addCleanup(parche.__exit__, None, None, None)

    def test_deja_el_de_fabrica_y_el_respaldo(self):
        anterior = "[voz]\nmotor = onecore\n"
        (self.datos / "config.ini").write_text(anterior, encoding="utf-8")
        prefs.restablecer()
        self.assertEqual((self.datos / "config.ini").read_text(
            encoding="utf-8"), pred.generar_texto())
        self.assertEqual((self.datos / "config.anterior.ini").read_text(
            encoding="utf-8"), anterior)

    def test_la_respaldo_se_pisa_en_cada_operacion(self):
        (self.datos / "config.ini").write_text("[voz]\nmotor = sapi\n",
                                               encoding="utf-8")
        prefs.restablecer()
        primera = (self.datos / "config.anterior.ini").read_text(
            encoding="utf-8")
        self.assertEqual(primera, "[voz]\nmotor = sapi\n")
        origen = self.datos / "nuevo.ini"
        origen.write_text("[ui]\ntema = default\n", encoding="utf-8")
        prefs.importar(origen)
        self.assertEqual((self.datos / "config.anterior.ini").read_text(
            encoding="utf-8"), pred.generar_texto())


class TestPseudoMotivos(unittest.TestCase):
    """Pseudotraducción: cada motivo de rechazo sale marcado."""

    def test_todos_los_motivos_salen_marcados(self):
        with tempfile.TemporaryDirectory() as carpeta:
            datos = Path(carpeta)
            grande = datos / "grande.ini"
            grande.write_bytes(b"[voz]\n" + b"x" * (prefs.LIMITE_BYTES + 1))
            texto = datos / "texto.txt"
            texto.write_text("esto no es un ini\nni [seccion\n",
                             encoding="utf-8")
            otro = datos / "otro.ini"
            otro.write_text("[otro]\nclave = 1\n", encoding="utf-8")
            with con_pseudo():
                motivos = [
                    prefs.motivo_no_importable(grande),
                    prefs.motivo_no_importable(texto),
                    prefs.motivo_no_importable(otro),
                    prefs.motivo_no_importable(datos / "no-existe.ini"),
                ]
        self.assertEqual(len(motivos), 4)
        for motivo in motivos:
            with self.subTest(motivo=motivo):
                self.assertTrue(motivo.startswith("[¡"), motivo)


if __name__ == "__main__":
    unittest.main()
