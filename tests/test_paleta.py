"""Pruebas de la paleta compartida y de su uso en las ventanas grises.

Crean diálogos de verdad: abren ventanas.
"""

import unittest
from unittest import mock

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False

from bellbird.ui import paleta
from bellbird.ui.tema import _T
from tests.ventanas_prueba import destruir


def _hilo_directo(target, nombre, **kwargs):
    args = kwargs.get("args", ())
    target(*args)
    hilo = mock.Mock()
    hilo.start.return_value = None
    return hilo


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPintarVentana(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _dialogo(self):
        dialogo = wx.Dialog(None, title="Prueba", name="DialogoPrueba")
        self.panel = wx.Panel(dialogo, name="Panel")
        self.campo = wx.TextCtrl(self.panel, value="x", name="Campo")
        self.lista = wx.ListBox(self.panel, choices=["a"], name="Lista")
        self.boton = wx.Button(self.panel, label="&Ir", name="Ir")
        self.casilla = wx.CheckBox(self.panel, label="&Marcar",
                                   name="Marcar")
        self.mapa = wx.StaticBitmap(self.panel, bitmap=wx.NullBitmap,
                                    name="Mapa")
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_pinta_cada_clase_con_su_color(self):
        dialogo = self._dialogo()
        fondo_mapa_antes = self.mapa.GetBackgroundColour()
        paleta.pintar_ventana(dialogo)
        self.assertEqual(dialogo.GetBackgroundColour(), _T.bg)
        self.assertEqual(self.panel.GetBackgroundColour(), _T.bg)
        self.assertEqual(self.panel.GetForegroundColour(), _T.text)
        self.assertEqual(self.campo.GetBackgroundColour(), _T.field)
        self.assertEqual(self.campo.GetForegroundColour(), _T.text)
        self.assertEqual(self.lista.GetBackgroundColour(), _T.field)
        self.assertEqual(self.lista.GetForegroundColour(), _T.text)
        self.assertEqual(self.boton.GetBackgroundColour(), _T.btn)
        self.assertEqual(self.boton.GetForegroundColour(), _T.btn_t)
        self.assertEqual(self.casilla.GetForegroundColour(), _T.text)
        self.assertEqual(self.mapa.GetBackgroundColour(),
                         fondo_mapa_antes)

    def test_con_alto_contraste_no_cambia_nada(self):
        dialogo = self._dialogo()
        antes = (dialogo.GetBackgroundColour(),
                 self.panel.GetBackgroundColour(),
                 self.campo.GetBackgroundColour(),
                 self.boton.GetBackgroundColour(),
                 self.casilla.GetForegroundColour())
        with mock.patch.object(paleta.gui, "ALTO_CONTRASTE", True):
            paleta.pintar_ventana(dialogo)
        despues = (dialogo.GetBackgroundColour(),
                   self.panel.GetBackgroundColour(),
                   self.campo.GetBackgroundColour(),
                   self.boton.GetBackgroundColour(),
                   self.casilla.GetForegroundColour())
        self.assertEqual(antes, despues)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestFondoActualizacion(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_fondo_es_el_de_la_principal(self):
        from bellbird.ui import gui_actualizacion as actualizacion
        dialogo = actualizacion.DialogoActualizacion(None, "Algo")
        self.addCleanup(destruir, dialogo)
        dialogo.Show()
        self.assertEqual(dialogo.GetBackgroundColour(), _T.bg)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestFondoElegirDestino(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_fondo_es_el_de_la_principal(self):
        from bellbird.ui import gui_elegir_destino as elegir
        dialogo = elegir.DialogoElegirDestino(None, destino="YouTube",
                                             usuario="")
        self.addCleanup(destruir, dialogo)
        self.assertEqual(dialogo.GetBackgroundColour(), _T.bg)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestFondoDirectoYoutube(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_fondo_es_el_de_la_principal(self):
        from bellbird.ui import gui_directo_youtube as directo
        dialogo = directo.DialogoDirectoYoutube(None)
        self.addCleanup(destruir, dialogo)
        self.assertEqual(dialogo.GetBackgroundColour(), _T.bg)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestFondoAgregarCaptura(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)
        from bellbird.ui import ia_agregar_captura as agregar
        parche_hilo = mock.patch.object(
            agregar.diagnostico, "crear_hilo", side_effect=_hilo_directo)
        parche_hilo.start()
        self.addCleanup(parche_hilo.stop)
        parche_llamada = mock.patch.object(
            agregar.wx, "CallAfter",
            side_effect=lambda funcion, *args, **kwargs: funcion(*args,
                                                                 **kwargs))
        parche_llamada.start()
        self.addCleanup(parche_llamada.stop)

    def test_fondo_es_el_de_la_principal(self):
        from bellbird.ui import ia_agregar_captura as agregar
        with mock.patch.object(agregar.obs_captura_ia, "opciones",
                               return_value=[]):
            dialogo = agregar.DialogoAgregarCaptura(None, mock.Mock())
        self.addCleanup(destruir, dialogo)
        self.assertEqual(dialogo.GetBackgroundColour(), _T.bg)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestFondoVentanaIA(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_mensaje_fondo_es_el_de_la_principal(self):
        from bellbird.ui import ia_ventana as ventana
        dialogo = ventana.DialogoMensaje(None, "hola")
        self.addCleanup(destruir, dialogo)
        self.assertEqual(dialogo.GetBackgroundColour(), _T.bg)

    def test_ventana_fondo_es_el_de_la_principal(self):
        from bellbird.ui import ia_ventana as ventana
        dialogo = ventana.VentanaIA(None)
        self.addCleanup(destruir, dialogo)
        self.assertEqual(dialogo.GetBackgroundColour(), _T.bg)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestFondoPreferencias(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _dialogo(self):
        from bellbird.ui import gui_preferencias as preferencias
        from bellbird.voice import motores
        with mock.patch.object(motores, "listar_voces",
                               return_value=["Voz de prueba"]):
            dialogo = preferencias.PreferenciasDialog(None, {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_fondo_es_el_de_la_principal(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo.GetBackgroundColour(), _T.bg)

    def test_casilla_con_texto_y_categorias_en_superficie(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo.chk_total_sc.GetForegroundColour(),
                         _T.text)
        self.assertEqual(dialogo.lista_categorias.GetBackgroundColour(),
                         _T.surface)


if __name__ == "__main__":
    unittest.main()
