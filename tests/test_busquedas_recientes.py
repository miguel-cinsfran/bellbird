"""Pruebas de las búsquedas recientes, sin interfaz."""

import json
import tempfile
import unittest
from pathlib import Path

from bellbird.downloads import busquedas_recientes as recientes


class TestAgregar(unittest.TestCase):

    def test_lo_nuevo_va_primero_y_sin_duplicados(self):
        self.assertEqual(
            recientes.agregar(["cumbia", "polca"], "guarania"),
            ["guarania", "cumbia", "polca"])
        self.assertEqual(
            recientes.agregar(["cumbia", "polca"], "polca"),
            ["polca", "cumbia"])

    def test_mayusculas_y_vacio(self):
        self.assertEqual(
            recientes.agregar(["Cumbia"], "cumbia"), ["cumbia"])
        self.assertEqual(
            recientes.agregar(["cumbia"], "  "), ["cumbia"])
        self.assertEqual(recientes.agregar(["cumbia"], ""), ["cumbia"])

    def test_tope_de_veinte(self):
        lista = [f"b{i}" for i in range(20)]
        salida = recientes.agregar(lista, "nueva")
        self.assertEqual(len(salida), 20)
        self.assertEqual(salida[0], "nueva")
        self.assertNotIn("b19", salida)


class TestCargarGuardar(unittest.TestCase):

    def test_cargar_roto_devuelve_vacio(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "recientes.json"
            ruta.write_text("{esto no es json", encoding="utf-8")
            self.assertEqual(recientes.cargar(ruta), [])
            ruta.write_text(json.dumps({"no": "una lista"}), encoding="utf-8")
            self.assertEqual(recientes.cargar(ruta), [])

    def test_guardar_y_cargar(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "recientes.json"
            recientes.guardar(ruta, ["guarania", "cumbia"])
            self.assertEqual(recientes.cargar(ruta), ["guarania", "cumbia"])


if __name__ == "__main__":
    unittest.main()
