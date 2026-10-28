"""Tests de la traducción de atajos a combos wx para la pantalla completa.

Necesita wxPython (por las constantes wx.WXK_*/wx.MOD_*), así que se salta
donde no esté instalado (p. ej. CI en Linux), como el resto de lo que toca GUI.
"""

import unittest
from unittest import mock

try:
    import wx  # noqa: F401
    _HAY_WX = True
except Exception:
    _HAY_WX = False


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestComboWx(unittest.TestCase):

    def setUp(self):
        from ytchat.ui import teclas_wx
        self.combo = teclas_wx.combo_wx

    def test_ctrl_letra(self):
        import wx
        self.assertEqual(self.combo("ctrl+p"), (wx.MOD_CONTROL, ord("P")))

    def test_ctrl_flecha(self):
        import wx
        self.assertEqual(self.combo("ctrl+left"), (wx.MOD_CONTROL, wx.WXK_LEFT))
        self.assertEqual(self.combo("ctrl+up"), (wx.MOD_CONTROL, wx.WXK_UP))

    def test_tecla_f_sin_modificador(self):
        import wx
        self.assertEqual(self.combo("f5"), (wx.MOD_NONE, wx.WXK_F5))
        self.assertEqual(self.combo("f12"), (wx.MOD_NONE, wx.WXK_F12))

    def test_alt_enter(self):
        import wx
        self.assertEqual(self.combo("alt+enter"), (wx.MOD_ALT, wx.WXK_RETURN))

    def test_invalidos(self):
        self.assertIsNone(self.combo(""))
        self.assertIsNone(self.combo("xyz+q"))
        self.assertIsNone(self.combo("ctrl+"))
        self.assertIsNone(self.combo(None))


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestCableadoAnuncioAjuste(unittest.TestCase):

    def test_flecha_registra_y_ajustar_anuncia_solo_el_valor(self):
        from ytchat.core import anuncio_ajuste
        from ytchat.core.anuncio_ajuste import AnuncioAjuste
        from ytchat.player import reproductor
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._vol = 40
        panel._player = None
        panel._video_id = "video-cargado"
        panel.sld_vol = mock.Mock()
        with mock.patch.object(anuncio_ajuste, "COMPARTIDO", AnuncioAjuste()), \
                mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._vol_flecha(+1)
            anunciar.assert_not_called()
            panel.ajustar_volumen(+1)
        anunciar.assert_called_once_with("42 por ciento")


if __name__ == "__main__":
    unittest.main()
