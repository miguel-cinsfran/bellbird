"""Pruebas del alcance que la fase 3 del smoke declara, sin abrir ventanas.

La fase 3 solo audita la pantalla desconectada. Este texto existe para que un
«OK» del smoke no se lea como «todos los controles tienen nombre», así que hay
que comprobar que dice las dos cosas: que es solo sin conectar, y quién cubre
el resto.
"""

import unittest

from scripts.smoke_test import ALCANCE_FASE3


class AlcanceFase3Test(unittest.TestCase):

    def test_nombra_al_banco_de_qa(self):
        self.assertIn("qa/conducir.py", ALCANCE_FASE3)

    def test_dice_que_solo_cubre_la_pantalla_sin_conectar(self):
        self.assertIn("sin conectar", ALCANCE_FASE3)


if __name__ == "__main__":
    unittest.main()
