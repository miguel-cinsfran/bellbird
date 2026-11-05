"""Pruebas de la fila compartida de botones de Preferencias.

Abren ventanas. `fila_botones` junta en una fila partible los botones de
una misma sección, en el orden dado.
"""

import unittest

import wx

from guyrapu.ui.preferencias_comun import (
    fijar_zona, fila_botones, opciones_con_elegida)
from tests.ventanas_prueba import app_de_prueba, destruir


class TestFilaBotones(unittest.TestCase):
    # Con ventana: los botones necesitan un padre real.

    def setUp(self):
        self.app = app_de_prueba()

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


class TestFijarZona(unittest.TestCase):

    def setUp(self):
        self.app = app_de_prueba()
        self.marco = wx.Frame(None)
        self.addCleanup(destruir, self.marco)
        self.zona = wx.ScrolledWindow(self.marco)
        self.rotulo = wx.StaticText(self.zona, label="Rótulo")
        self.campo = wx.TextCtrl(self.zona)
        self.contenido = wx.BoxSizer(wx.VERTICAL)
        self.contenido.Add(self.rotulo, 0, wx.ALL, 6)
        self.contenido.Add(self.campo, 0, wx.EXPAND | wx.ALL, 6)

    def test_fija_el_sizer_y_un_alto_que_entra_en_la_pantalla(self):
        fijar_zona(self.marco, self.zona, self.contenido)
        self.assertIs(self.zona.GetSizer(), self.contenido)
        disponible = wx.Display(self.marco).GetClientArea().GetHeight() - 120
        self.assertEqual(self.zona.GetMinSize().GetHeight(),
                         min(self.contenido.GetMinSize().GetHeight(),
                             disponible))

    def test_iguala_el_ancho_de_los_rotulos_de_todos_los_grupos(self):
        otro = wx.StaticText(self.zona, label="Un rótulo bastante más largo")
        self.contenido.Add(otro, 0, wx.ALL, 6)
        fijar_zona(self.marco, self.zona, self.contenido)
        self.assertEqual(self.rotulo.GetMinSize().GetWidth(),
                         otro.GetMinSize().GetWidth())
        self.assertEqual(self.rotulo.GetMinSize().GetWidth(),
                         otro.GetBestSize().GetWidth())


class TestOpcionesConElegida(unittest.TestCase):
    # Sin ventana: mezcla pura de nombres.

    def test_automatico_solo(self):
        self.assertEqual(opciones_con_elegida("Elegir", "", []), ["Elegir"])

    def test_elegida_y_encontradas_sin_repetir(self):
        self.assertEqual(
            opciones_con_elegida("Elegir", "Vieja", ["Nueva", "Vieja", ""]),
            ["Elegir", "Vieja", "Nueva"])

    def test_elegida_vacia_no_suma(self):
        self.assertEqual(
            opciones_con_elegida("Elegir", "", ["Una"]),
            ["Elegir", "Una"])


if __name__ == "__main__":
    unittest.main()
