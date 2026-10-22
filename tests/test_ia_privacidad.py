"""Pruebas del aviso de privacidad de la IA, sin red.

Con wx: las corre el advisor en otra PC. No correr aquí.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

import wx

from ytchat.ui import ia_privacidad


def _ajustes(aceptada):
    return SimpleNamespace(privacidad_aceptada=aceptada)


class TestConfirmar(unittest.TestCase):

    def test_ya_aceptada_no_muestra_nada(self):
        with mock.patch.object(ia_privacidad.wx, "MessageBox") as caja:
            self.assertTrue(
                ia_privacidad.confirmar(None, _ajustes(True), "OpenAI"))
        caja.assert_not_called()

    def test_si_guarda_y_da_verdadero(self):
        with mock.patch.object(ia_privacidad.wx, "MessageBox",
                               return_value=wx.YES) as caja, \
                mock.patch.object(ia_privacidad.ajustes_ia,
                                  "guardar_privacidad_aceptada",
                                  return_value=True) as guardar:
            self.assertTrue(
                ia_privacidad.confirmar(None, _ajustes(False), "OpenAI"))
        caja.assert_called_once_with(
            ia_privacidad.TEXTO_AVISO.format(proveedor="OpenAI"),
            ia_privacidad.TITULO_AVISO,
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_INFORMATION, None)
        guardar.assert_called_once_with(ia_privacidad.paths.config_ini(),
                                        True)

    def test_no_no_guarda_y_da_falso(self):
        with mock.patch.object(ia_privacidad.wx, "MessageBox",
                               return_value=wx.NO), \
                mock.patch.object(ia_privacidad.ajustes_ia,
                                  "guardar_privacidad_aceptada") as guardar:
            self.assertFalse(
                ia_privacidad.confirmar(None, _ajustes(False), "OpenAI"))
        guardar.assert_not_called()

    def test_si_el_guardado_falla_igual_deja_pasar(self):
        def falla_con_valor():
            return mock.patch.object(ia_privacidad.ajustes_ia,
                                     "guardar_privacidad_aceptada",
                                     return_value=False)

        def falla_con_error():
            return mock.patch.object(ia_privacidad.ajustes_ia,
                                     "guardar_privacidad_aceptada",
                                     side_effect=OSError("sin disco"))

        for fabrica in (falla_con_valor, falla_con_error):
            with self.subTest(fabrica=fabrica.__name__), \
                    mock.patch.object(ia_privacidad.wx, "MessageBox",
                                      return_value=wx.YES), \
                    fabrica(), \
                    mock.patch.object(ia_privacidad.logger,
                                      "warning") as aviso:
                self.assertTrue(
                    ia_privacidad.confirmar(None, _ajustes(False), "OpenAI"))
            aviso.assert_called_once()


if __name__ == "__main__":
    unittest.main()
