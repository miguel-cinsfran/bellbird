"""Pruebas de las teclas sueltas de la pantalla completa, sin ventana.

`accion_de_tecla` es pura: se prueba sin `wx.App` ni controles, solo con
las constantes de wx y un `AccionesPantalla` de dobles.
"""

import unittest
from unittest import mock

try:
    import wx  # noqa: F401
    _HAY_WX = True
except Exception:
    _HAY_WX = False


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestAccionDeTecla(unittest.TestCase):

    def setUp(self):
        from bellbird.player.pantalla_completa import (
            AccionesPantalla, accion_de_tecla)
        self.acciones = AccionesPantalla(
            salir=mock.Mock(), pausa=mock.Mock(),
            buscar_rel=mock.Mock(), volumen=mock.Mock(),
            silenciar=mock.Mock(), buscar_porcentaje=mock.Mock())
        self.accion_de_tecla = accion_de_tecla

    def _pulsa(self, codigo, mods=None):
        import wx
        accion = self.accion_de_tecla(
            codigo, wx.MOD_NONE if mods is None else mods, self.acciones)
        self.assertIsNotNone(accion)
        accion()
        return accion

    def test_espacio_pausa(self):
        import wx
        self._pulsa(wx.WXK_SPACE)
        self.acciones.pausa.assert_called_once_with()

    def test_tecla_de_medios_pausa(self):
        import wx
        self._pulsa(wx.WXK_MEDIA_PLAY_PAUSE)
        self.acciones.pausa.assert_called_once_with()

    def test_flechas_laterales_buscan_diez_segundos(self):
        import wx
        self._pulsa(wx.WXK_LEFT)
        self.acciones.buscar_rel.assert_called_once_with(-10000)
        self._pulsa(wx.WXK_RIGHT)
        self.acciones.buscar_rel.assert_called_with(10000)
        self.assertEqual(self.acciones.buscar_rel.call_count, 2)

    def test_flechas_verticales_ajustan_volumen(self):
        import wx
        self._pulsa(wx.WXK_UP)
        self.acciones.volumen.assert_called_once_with(5)
        self._pulsa(wx.WXK_DOWN)
        self.acciones.volumen.assert_called_with(-5)
        self.assertEqual(self.acciones.volumen.call_count, 2)

    def test_m_silencia(self):
        self._pulsa(ord("M"))
        self.acciones.silenciar.assert_called_once_with()

    def test_f_sale(self):
        self._pulsa(ord("F"))
        self.acciones.salir.assert_called_once_with()

    def test_digitos_buscan_porcentaje(self):
        import wx
        self._pulsa(ord("3"))
        self.acciones.buscar_porcentaje.assert_called_once_with(30)
        self._pulsa(wx.WXK_NUMPAD3)
        self.acciones.buscar_porcentaje.assert_called_with(30)
        self.assertEqual(self.acciones.buscar_porcentaje.call_count, 2)

    def test_con_modificadores_devuelve_none(self):
        import wx
        self.assertIsNone(self.accion_de_tecla(
            wx.WXK_SPACE, wx.MOD_CONTROL, self.acciones))

    def test_letra_sin_uso_devuelve_none(self):
        import wx
        self.assertIsNone(self.accion_de_tecla(
            ord("X"), wx.MOD_NONE, self.acciones))


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestCableadoPantallaCompleta(unittest.TestCase):
    """El panel pasa a la ventana sus atajos y sus seis acciones.

    Sin ventana ni VLC: el panel se crea sin `__init__` y lo que toca
    afuera (`PantallaCompleta`, `_fijar_salida`, `anunciar`) queda con
    dobles, así no hace falta `wx.App`.
    """

    def test_alternar_pasa_atajos_y_acciones_del_panel(self):
        from bellbird.player import reproductor
        panel = reproductor.ReproductorPanel.__new__(
            reproductor.ReproductorPanel)
        panel._fs = None
        panel._avisar_sin_medio = mock.Mock(return_value=False)
        panel._asegurar_player = mock.Mock(return_value=True)
        centinela = mock.Mock()
        panel._mapa_atajos_fs = mock.Mock(return_value=centinela)
        panel._fijar_salida = mock.Mock()
        with mock.patch.object(reproductor, "PantallaCompleta") as ventana, \
                mock.patch.object(reproductor, "anunciar"):
            panel.alternar_pantalla_completa()
        self.assertEqual(ventana.call_count, 1)
        atajos, acciones = ventana.call_args.args
        self.assertIs(atajos, centinela)
        self.assertEqual(acciones.salir, panel.alternar_pantalla_completa)
        self.assertEqual(acciones.pausa, panel._toggle_play)
        self.assertEqual(acciones.buscar_rel, panel._buscar_rel)
        self.assertEqual(acciones.volumen, panel._vol_flecha)
        self.assertEqual(acciones.silenciar, panel._toggle_mute)
        self.assertEqual(
            acciones.buscar_porcentaje, panel._buscar_porcentaje)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoNombreAccesibleVentana(unittest.TestCase):
    """Con ventana: el nombre accesible del vídeo sale marcado.
    """

    def test_nombre_del_video_sale_marcado(self):
        import wx
        from tests.pseudo_prueba import con_pseudo
        from tests.ventanas_prueba import destruir
        from bellbird.player.pantalla_completa import (
            AccionesPantalla, PantallaCompleta)
        app = wx.App.Get() or wx.App(False)
        acciones = AccionesPantalla(
            salir=mock.Mock(), pausa=mock.Mock(),
            buscar_rel=mock.Mock(), volumen=mock.Mock(),
            silenciar=mock.Mock(), buscar_porcentaje=mock.Mock())
        with con_pseudo():
            ventana = PantallaCompleta({}, acciones)
        self.addCleanup(destruir, ventana)
        nombre = ventana.video.GetName()
        self.assertTrue(nombre.startswith("[¡"), nombre)


if __name__ == "__main__":
    unittest.main()
