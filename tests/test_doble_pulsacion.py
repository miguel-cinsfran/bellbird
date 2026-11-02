"""Detección genérica de la doble pulsación de un atajo, sin wx."""

import unittest

from bellbird.core.doble_pulsacion import DoblePulsacion


class TestDoblePulsacion(unittest.TestCase):

    def test_la_primera_es_cero_y_la_segunda_uno(self):
        contador = DoblePulsacion()
        self.assertEqual(contador.contar("F2", 100.0), 0)
        self.assertEqual(contador.contar("F2", 100.3), 1)

    def test_pasado_el_intervalo_vuelve_a_contar_desde_cero(self):
        contador = DoblePulsacion()
        self.assertEqual(contador.contar("F2", 100.0), 0)
        self.assertEqual(contador.contar("F2", 100.7), 0)

    def test_el_limite_de_medio_segundo_no_es_doble(self):
        contador = DoblePulsacion()
        self.assertEqual(contador.contar("F2", 100.0), 0)
        self.assertEqual(contador.contar("F2", 100.5), 0)

    def test_otro_atajo_en_medio_corta_la_racha(self):
        contador = DoblePulsacion()
        self.assertEqual(contador.contar("F2", 100.0), 0)
        self.assertEqual(contador.contar("F3", 100.1), 0)
        self.assertEqual(contador.contar("F2", 100.2), 0)
        self.assertEqual(contador.contar("F2", 100.3), 1)

    def test_despues_de_la_segunda_cuenta_desde_cero(self):
        contador = DoblePulsacion()
        self.assertEqual(contador.contar("F2", 100.0), 0)
        self.assertEqual(contador.contar("F2", 100.3), 1)
        self.assertEqual(contador.contar("F2", 100.4), 0)


if __name__ == "__main__":
    unittest.main()
