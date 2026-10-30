"""Pseudotraducción de la sección de clave de IA de Preferencias.

Abre ventanas.
Construye la sección sobre un panel propio con la pseudotraducción y
exige que no deje ningún texto visible sin envolver.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

import wx

from bellbird.ui import preferencias_ia_clave
from bellbird.ui.preferencias_ia_clave import SeccionClaveIA
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import destruir


class TestPseudoClaveIA(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        proveedor = SimpleNamespace(id="gemini", nombre="Gemini")
        # Nunca el Administrador de credenciales real.
        with mock.patch.object(preferencias_ia_clave.claves, "leer",
                               return_value=""):
            with con_pseudo():
                marco = wx.Frame(None)
                self.addCleanup(destruir, marco)
                panel = wx.Panel(marco)
                sizer = wx.BoxSizer(wx.VERTICAL)
                seccion = SeccionClaveIA(lambda: proveedor, lambda: None)
                seccion.construir(panel, sizer)
                panel.SetSizer(sizer)
                sin_marcar = textos_sin_marcar(panel)

        self.assertEqual([], sin_marcar)


if __name__ == "__main__":
    unittest.main()
