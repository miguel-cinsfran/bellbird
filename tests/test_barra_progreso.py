"""Pruebas de `tramo`, sin wx: decide qué imagen lleva cada fila."""

import math
import unittest

from bellbird.ui import barra_progreso


class TestTramoBordes(unittest.TestCase):

    def test_bordes_de_avance(self):
        casos = [(0, 0), (4.9, 1), (5, 1), (97.5, 20), (100, 20)]
        for progreso, esperado in casos:
            with self.subTest(progreso=progreso):
                for estado in ("descargando", "en_cola"):
                    self.assertEqual(
                        barra_progreso.tramo(estado, progreso), esperado)

    def test_completado_da_20(self):
        for progreso in (0, 45, 100):
            with self.subTest(progreso=progreso):
                self.assertEqual(
                    barra_progreso.tramo("completado", progreso), 20)

    def test_sin_avance_da_menos_uno(self):
        for estado in ("error", "cancelado", "desconocido", ""):
            with self.subTest(estado=estado):
                self.assertEqual(barra_progreso.tramo(estado, 50), -1)


class TestTramoPropiedad(unittest.TestCase):

    def test_avance_siempre_entre_0_y_20(self):
        progresos = ([-100.0, -1.0, -0.1] + [n * 2.5 for n in range(49)]
                     + [100.0, 100.1, 150.0, float("inf"),
                        float("-inf"), float("nan")])
        for estado in ("descargando", "en_cola", "completado"):
            for progreso in progresos:
                with self.subTest(estado=estado, progreso=progreso):
                    tramo = barra_progreso.tramo(estado, progreso)
                    self.assertGreaterEqual(tramo, 0)
                    self.assertLessEqual(tramo, 20)

    def test_menos_uno_solo_sin_texto_de_avance(self):
        progresos = ([-5.0, 0, 45.0, 100.0, 130.0, float("nan")]
                     + [n * 7.0 for n in range(16)])
        for estado in ("descargando", "en_cola", "completado", "error",
                       "cancelado", "parcial", "desconocido", ""):
            for progreso in progresos:
                with self.subTest(estado=estado, progreso=progreso):
                    if estado in ("descargando", "en_cola", "completado"):
                        self.assertNotEqual(
                            barra_progreso.tramo(estado, progreso), -1)
                    else:
                        self.assertEqual(
                            barra_progreso.tramo(estado, progreso), -1)
                    self.assertFalse(
                        math.isnan(barra_progreso.tramo(estado, progreso)))


if __name__ == "__main__":
    unittest.main()
