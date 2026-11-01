"""Pruebas de la lógica pura del barrido con pseudotraducción."""

import importlib.util
import unittest
from pathlib import Path

_QA = Path(__file__).resolve().parent.parent / "qa"


def _cargar():
    ruta = _QA / "pseudo.py"
    paquete = importlib.util.spec_from_file_location("pseudo_qa", ruta)
    modulo = importlib.util.module_from_spec(paquete)
    paquete.loader.exec_module(modulo)
    return modulo


pseudo = _cargar()


class TestSinMarcar(unittest.TestCase):

    def test_marcado_entero(self):
        self.assertIsNone(pseudo.sin_marcar("[¡Conectado!]"))

    def test_marcado_en_dos_tramos(self):
        self.assertIsNone(pseudo.sin_marcar("[¡Conectado!] [¡YouTube!]"))

    def test_marcado_anidado(self):
        self.assertIsNone(pseudo.sin_marcar("[¡[¡Conectado!]!]"))

    def test_texto_suelto(self):
        self.assertEqual(pseudo.sin_marcar("Conectado"), "Conectado")

    def test_mezcla_de_marcado_y_suelto(self):
        self.assertEqual(pseudo.sin_marcar("Conectado a [¡YouTube!]"),
                         "Conectado a [¡YouTube!]")

    def test_nombre_propio_solo(self):
        self.assertIsNone(pseudo.sin_marcar("YouTube"))

    def test_atajo_solo(self):
        self.assertIsNone(pseudo.sin_marcar("Ctrl+S"))

    def test_tecla_de_funcion_sola(self):
        self.assertIsNone(pseudo.sin_marcar("F2"))

    def test_version_sola(self):
        self.assertIsNone(pseudo.sin_marcar("v1.2.3"))

    def test_texto_de_propios(self):
        self.assertIsNone(
            pseudo.sin_marcar("Directo de prueba", ("Directo de prueba",)))

    def test_nombre_interno_de_wx(self):
        self.assertIsNone(pseudo.sin_marcar("panel"))


if __name__ == "__main__":
    unittest.main()
