"""Pruebas del índice de QA en «Colecciones», sin ventanas ni teclas.

Solo cubren lo puro (`indice_coleccion_qa`) y que el módulo importa sin
abrir nada. La escena real la corre el banco en la otra PC.
"""

import importlib.util
import unittest
from pathlib import Path

_QA = Path(__file__).resolve().parent.parent / "qa"


def _cargar(nombre, archivo):
    ruta = _QA / archivo
    paquete = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(paquete)
    paquete.loader.exec_module(modulo)
    return modulo


musica_colecciones = _cargar("musica_colecciones_qa", "musica_colecciones.py")


BIBLIOTECA = "Biblioteca: 6"
QA = "QA música real: 10"


class TestIndiceColeccionQa(unittest.TestCase):

    def test_sin_listas_propias_da_uno(self):
        filas = [BIBLIOTECA, QA]
        self.assertEqual(
            musica_colecciones.indice_coleccion_qa(filas, BIBLIOTECA, QA), 1)

    def test_propia_antes_da_dos(self):
        filas = [BIBLIOTECA, "Aardvark: 3", QA]
        self.assertEqual(
            musica_colecciones.indice_coleccion_qa(filas, BIBLIOTECA, QA), 2)

    def test_propia_despues_da_uno(self):
        filas = [BIBLIOTECA, QA, "Relax: 52"]
        self.assertEqual(
            musica_colecciones.indice_coleccion_qa(filas, BIBLIOTECA, QA), 1)

    def test_biblioteca_con_otra_cantidad_da_none(self):
        filas = ["Biblioteca: 5", QA]
        self.assertIsNone(
            musica_colecciones.indice_coleccion_qa(filas, BIBLIOTECA, QA))

    def test_qa_ausente_da_none(self):
        filas = [BIBLIOTECA, "Relax: 52"]
        self.assertIsNone(
            musica_colecciones.indice_coleccion_qa(filas, BIBLIOTECA, QA))

    def test_qa_dos_veces_da_none(self):
        filas = [BIBLIOTECA, QA, QA]
        self.assertIsNone(
            musica_colecciones.indice_coleccion_qa(filas, BIBLIOTECA, QA))

    def test_filas_vacia_da_none(self):
        self.assertIsNone(
            musica_colecciones.indice_coleccion_qa([], BIBLIOTECA, QA))

    def test_filas_none_da_none(self):
        self.assertIsNone(
            musica_colecciones.indice_coleccion_qa(None, BIBLIOTECA, QA))


if __name__ == "__main__":
    unittest.main()
