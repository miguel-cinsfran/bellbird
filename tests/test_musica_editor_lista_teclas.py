"""Prueba wx del Enter en la lista del editor de listas.

Abre una ventana: no se corre en el encargo, la corre el advisor.
"""

import unittest
from unittest import mock

from bellbird.music.modelo import Tema
from tests.ventanas_prueba import destruir

try:
    import wx
    from bellbird.ui import musica_editor_lista
    _HAY_WX = True
except Exception:
    wx = None
    musica_editor_lista = None
    _HAY_WX = False


class Evento:
    """Doble mínimo de un evento de teclado de wx."""

    def __init__(self, keycode):
        self._keycode = keycode
        self.skipped = False

    def GetKeyCode(self):
        return self._keycode

    def Skip(self):
        self.skipped = True


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestEnterEnLaLista(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.dialogo = None

    def tearDown(self):
        if self.dialogo is not None:
            destruir(self.dialogo)

    def _abrir(self, temas):
        self.dialogo = musica_editor_lista.DialogoEditorLista(
            None, "Lista", tuple(temas), ())
        self.dialogo.lb_temas.SetFocus()
        self.dialogo.lb_temas.Focus(0)
        wx.Yield()
        return self.dialogo

    def test_enter_marca_y_desmarca_sin_cerrar_ni_anunciar(self):
        a = Tema("C:/a.mp3", "A")
        b = Tema("C:/b.mp3", "B")
        dialogo = self._abrir((a, b))
        with mock.patch.object(musica_editor_lista, "anunciar") as anunciar, \
                mock.patch.object(dialogo, "EndModal") as fin:
            primero = Evento(wx.WXK_RETURN)
            dialogo._tecla(primero)
            self.assertTrue(dialogo.lb_temas.IsItemChecked(0))
            anunciar.assert_not_called()
            self.assertFalse(primero.skipped)
            segundo = Evento(wx.WXK_NUMPAD_ENTER)
            dialogo._tecla(segundo)
            self.assertFalse(dialogo.lb_temas.IsItemChecked(0))
            anunciar.assert_not_called()
            self.assertFalse(segundo.skipped)
            fin.assert_not_called()

    def test_enter_fuera_de_la_lista_sigue_su_camino(self):
        a = Tema("C:/a.mp3", "A")
        dialogo = self._abrir((a,))
        dialogo.txt_buscar.SetFocus()
        wx.Yield()
        with mock.patch.object(musica_editor_lista, "anunciar") as anunciar:
            evento = Evento(wx.WXK_RETURN)
            dialogo._tecla(evento)
            anunciar.assert_not_called()
        self.assertTrue(evento.skipped)


if __name__ == "__main__":
    unittest.main()
