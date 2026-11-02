"""Pruebas del registro de grabaciones, sin ventanas y con archivos reales."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from bellbird.obs import grabaciones


class TestAnotarYLeer(unittest.TestCase):

    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.carpeta = Path(self.temporal.name)
        self.ruta = self.carpeta / "grabaciones.json"

    def _archivo(self, nombre, bytes_=16):
        ruta = self.carpeta / nombre
        ruta.write_bytes(b"x" * bytes_)
        return ruta

    def test_anota_y_lee_con_un_archivo_real(self):
        archivo = self._archivo("primera.mp4")
        grabaciones.anotar(archivo, ruta=self.ruta, ahora=1000)
        self.assertEqual(grabaciones.leer(self.ruta), [
            {"ruta": str(archivo), "fecha": 1000}])

    def test_lo_mas_nuevo_queda_primero(self):
        primero = self._archivo("primera.mp4")
        segunda = self._archivo("segunda.mp4")
        grabaciones.anotar(primero, ruta=self.ruta, ahora=1000)
        grabaciones.anotar(segunda, ruta=self.ruta, ahora=2000)
        self.assertEqual([e["ruta"] for e in grabaciones.leer(self.ruta)],
                         [str(segunda), str(primero)])

    def test_conserva_como_mucho_doscientas(self):
        for numero in range(205):
            grabaciones.anotar(self._archivo(f"{numero}.mp4"),
                               ruta=self.ruta, ahora=numero)
        entradas = grabaciones.leer(self.ruta)
        self.assertEqual(len(entradas), 200)
        self.assertEqual(entradas[0]["fecha"], 204)
        self.assertEqual(entradas[-1]["fecha"], 5)

    def test_archivo_ilegible_da_lista_vacia(self):
        self.ruta.write_text("{roto", encoding="utf-8")
        self.assertEqual(grabaciones.leer(self.ruta), [])

    def test_archivo_ausente_da_lista_vacia(self):
        self.assertEqual(grabaciones.leer(self.carpeta / "no-existe.json"), [])

    def test_un_fallo_de_disco_al_anotar_se_registra_y_no_lanza(self):
        with mock.patch.object(grabaciones.archivos, "leer_json",
                               side_effect=OSError("sin disco")):
            with self.assertLogs(grabaciones.logger, level="DEBUG"):
                grabaciones.anotar(self._archivo("clip.mp4"), ruta=self.ruta)


class TestExistentes(unittest.TestCase):

    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.carpeta = Path(self.temporal.name)
        self.ruta = self.carpeta / "grabaciones.json"

    def test_devuelve_solo_lo_que_sigue_en_el_disco_con_su_tamano(self):
        queda = self.carpeta / "queda.mp4"
        queda.write_bytes(b"x" * (2 * 1024 * 1024))
        borrado = self.carpeta / "borrado.mp4"
        borrado.write_bytes(b"x" * 10)
        grabaciones.anotar(queda, ruta=self.ruta, ahora=1000)
        grabaciones.anotar(borrado, ruta=self.ruta, ahora=2000)
        borrado.unlink()

        entradas = grabaciones.existentes(self.ruta)
        self.assertEqual(len(entradas), 1)
        self.assertEqual(entradas[0]["ruta"], str(queda))
        self.assertEqual(entradas[0]["tamano"], 2 * 1024 * 1024)

    def test_mantiene_el_orden_de_lo_mas_nuevo_a_lo_mas_viejo(self):
        viejo = self.carpeta / "viejo.mp4"
        nuevo = self.carpeta / "nuevo.mp4"
        viejo.write_bytes(b"x")
        nuevo.write_bytes(b"x")
        grabaciones.anotar(viejo, ruta=self.ruta, ahora=1000)
        grabaciones.anotar(nuevo, ruta=self.ruta, ahora=2000)
        self.assertEqual([e["ruta"] for e in grabaciones.existentes(self.ruta)],
                         [str(nuevo), str(viejo)])


class TestQuitar(unittest.TestCase):

    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.carpeta = Path(self.temporal.name)
        self.ruta = self.carpeta / "grabaciones.json"
        self.archivo = self.carpeta / "queda.mp4"
        self.archivo.write_bytes(b"x")
        self.otro = self.carpeta / "otro.mp4"
        self.otro.write_bytes(b"x")

    def test_un_fallo_de_disco_al_quitar_se_registra_y_no_lanza(self):
        with mock.patch.object(grabaciones.archivos, "leer_json",
                               side_effect=OSError("sin disco")):
            with self.assertLogs(grabaciones.logger, level="DEBUG"):
                grabaciones.quitar(self.archivo, ruta=self.ruta)

    def test_saca_la_entrada_y_no_borra_el_archivo(self):
        grabaciones.anotar(self.archivo, ruta=self.ruta, ahora=1000)
        grabaciones.anotar(self.otro, ruta=self.ruta, ahora=2000)
        grabaciones.quitar(self.archivo, ruta=self.ruta)
        self.assertTrue(self.archivo.is_file())
        self.assertEqual([e["ruta"] for e in grabaciones.leer(self.ruta)],
                         [str(self.otro)])


class TestTextoFila(unittest.TestCase):

    def test_nombre_fecha_y_tamano(self):
        fecha = datetime(2026, 11, 2, 0, 15, 51).timestamp()
        entrada = {"ruta": "C:/Users/x/Videos/clip.mp4", "fecha": fecha,
                   "tamano": 2 * 1024 * 1024}
        self.assertEqual(grabaciones.texto_fila(entrada),
                         "clip.mp4, 02/11/2026 00:15, 2 MB")


if __name__ == "__main__":
    unittest.main()
