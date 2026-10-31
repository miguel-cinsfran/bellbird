"""Pruebas de la fila compartida de botones de Preferencias.

Abren ventanas. `fila_botones` junta en una fila partible los botones de
una misma sección, en el orden dado.
"""

import unittest

import wx

from bellbird.ui.preferencias_comun import fila_botones
from tests.ventanas_prueba import destruir


class TestFilaBotones(unittest.TestCase):
    # Con ventana: los botones necesitan un padre real.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _botones(self, cantidad=3):
        marco = wx.Frame(None)
        self.addCleanup(destruir, marco)
        panel = wx.Panel(marco)
        return [wx.Button(panel, label="B%d" % i)
                for i in range(cantidad)]

    def test_devuelve_una_fila_partible_con_los_botones_en_orden(self):
        botones = self._botones()
        fila = fila_botones(botones)
        self.assertIsInstance(fila, wx.WrapSizer)
        en_fila = [elemento.GetWindow()
                   for elemento in fila.GetChildren()]
        self.assertEqual(en_fila, botones)

    def test_el_borde_por_defecto_es_seis(self):
        botones = self._botones()
        fila = fila_botones(botones)
        bordes = [elemento.GetBorder()
                  for elemento in fila.GetChildren()]
        self.assertEqual(bordes, [6] * len(botones))

    def test_el_borde_se_puede_pedir(self):
        botones = self._botones(2)
        fila = fila_botones(botones, borde=10)
        bordes = [elemento.GetBorder()
                  for elemento in fila.GetChildren()]
        self.assertEqual(bordes, [10] * len(botones))


if __name__ == "__main__":
    unittest.main()
