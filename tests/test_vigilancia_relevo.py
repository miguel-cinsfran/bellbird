"""Pruebas de la vigilancia del relevo de un directo."""

import unittest

from bellbird.player import vigilancia_relevo


class TestAvisoDeCorte(unittest.TestCase):

    def test_avisa_al_caer_el_buffer_por_primera_vez(self):
        self.assertTrue(vigilancia_relevo.aviso_de_corte(99, None))

    def test_avisa_al_recuperarse_el_buffer(self):
        self.assertTrue(vigilancia_relevo.aviso_de_corte(100, 99))

    def test_no_avisa_cada_evento_durante_un_corte(self):
        self.assertEqual(vigilancia_relevo.aviso_de_corte(80, 99), "")
