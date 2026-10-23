"""Ancho del diálogo de directo con barra de desplazamiento (sin ventanas)."""

import unittest

from ytchat.ui.gui_directo_youtube import ancho_con_barra


class TestAnchoConBarra(unittest.TestCase):

    def test_si_cabe_no_suma(self):
        self.assertEqual(ancho_con_barra(400, 500, 700, 17), 400)

    def test_si_cabe_justo_no_suma(self):
        self.assertEqual(ancho_con_barra(400, 700, 700, 17), 400)

    def test_si_supera_suma_el_ancho_de_la_barra(self):
        self.assertEqual(ancho_con_barra(400, 701, 700, 17), 417)

    def test_si_supera_mucho_suma_una_sola_barra(self):
        self.assertEqual(ancho_con_barra(400, 2000, 700, 17), 417)


if __name__ == "__main__":
    unittest.main()
