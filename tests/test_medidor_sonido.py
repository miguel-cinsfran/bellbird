"""Pruebas del medidor de sonido de Windows (`qa/medidor_sonido.py`).

Sin ventanas ni sonido: solo se lee el medidor. La primera y la segunda
prueba van DE VERDAD contra COM, sin dobles. La tercera parcha `pico`
porque lo que mide es el máximo entre lecturas, no el COM. La cuarta
parcha `_sesiones` porque lo que mide es el filtro por pid, que con
cero sesiones reales no se podría romper a propósito.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "qa"))

import medidor_sonido

_HAY_MEDIDOR = sys.platform == "win32" and medidor_sonido.DISPONIBLE

_PID_INEXISTENTE = 2147483646


@unittest.skipUnless(_HAY_MEDIDOR, "sin medidor: no es Windows o falta comtypes")
class TestPico(unittest.TestCase):

    def test_pid_inexistente_devuelve_none_sin_lanzar(self):
        self.assertIsNone(medidor_sonido.pico([_PID_INEXISTENTE]))

    def test_pid_propio_se_mide_de_verdad_contra_com(self):
        valor = medidor_sonido.pico([os.getpid()])
        self.assertTrue(valor is None or 0.0 <= valor <= 1.0,
                        f"pico imposible: {valor!r}")

    def test_filtra_por_pid_aunque_haya_sesiones_de_otros(self):
        pares = [(111111, 0.5), (222222, 0.25)]
        with mock.patch.object(medidor_sonido, "_sesiones",
                               return_value=list(pares)):
            self.assertIsNone(medidor_sonido.pico([333333]))
            self.assertEqual(medidor_sonido.pico([111111]), 0.5)
            self.assertEqual(medidor_sonido.pico([111111, 222222]), 0.5)


@unittest.skipUnless(_HAY_MEDIDOR, "sin medidor: no es Windows o falta comtypes")
class TestPicoMaximo(unittest.TestCase):

    def test_devuelve_el_mayor_de_las_lecturas(self):
        with mock.patch.object(medidor_sonido, "pico",
                               side_effect=[0.0, 0.3, 0.1]):
            self.assertEqual(
                medidor_sonido.pico_maximo([123], segundos=0.2, cada=0.05),
                0.3)

    def test_todo_none_devuelve_none(self):
        with mock.patch.object(medidor_sonido, "pico", return_value=None):
            self.assertIsNone(
                medidor_sonido.pico_maximo([123], segundos=0.2, cada=0.05))


if __name__ == "__main__":
    unittest.main()
