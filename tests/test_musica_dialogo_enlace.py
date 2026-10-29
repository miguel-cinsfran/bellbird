"""Pruebas del cuadro de enlace de la música.

Abren ventanas: las corre el advisor en la otra PC, no se corren acá.
"""

import unittest

try:
    import wx
    from bellbird.ui import musica_dialogo_enlace
    from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
    from tests.ventanas_prueba import destruir
    _HAY_WX = True
except Exception:
    wx = None
    musica_dialogo_enlace = None
    _HAY_WX = False


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestDialogoEnlacePseudo(unittest.TestCase):
    """Ningún texto visible del cuadro sin pasar por gettext."""

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.dialogo = None

    def tearDown(self):
        if self.dialogo is not None:
            destruir(self.dialogo)

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            self.dialogo = musica_dialogo_enlace.DialogoEnlace(None)
            sin_marcar = textos_sin_marcar(self.dialogo)
        self.assertEqual([], sin_marcar)


if __name__ == "__main__":
    unittest.main()
