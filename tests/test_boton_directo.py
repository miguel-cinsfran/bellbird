"""Pruebas del botón directo de transmisión.

Las clases con ventana las corre el advisor (abren ventanas de verdad y
aquí no se corren): aquí solo se corre TestGuardarDestino, sin ventana.
"""

import queue
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False

from ytchat.ui import gui


class TestGuardarDestino(unittest.TestCase):
    # Sin ventana: _guardar_destino_transmision solo toca el dict y el INI.

    def _frame(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._config = {}
        return frame

    def test_destino_valido_se_guarda(self):
        frame = self._frame()
        with mock.patch.object(gui, "guardar_opcion") as guardar:
            resultado = frame._guardar_destino_transmision("TikTok")
        self.assertEqual(resultado, "TikTok")
        self.assertEqual(frame._config["transmision_destino"], "TikTok")
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "transmision", "destino", "TikTok")

    def test_destino_invalido_se_guarda_vacio(self):
        frame = self._frame()
        with mock.patch.object(gui, "guardar_opcion") as guardar:
            resultado = frame._guardar_destino_transmision("Twitch")
        self.assertEqual(resultado, "")
        self.assertEqual(frame._config["transmision_destino"], "")
        guardar.assert_called_once_with(
            gui.RUTA_CONFIG, "transmision", "destino", "")


class TestTransmitirSinVentana(unittest.TestCase):
    # Sin ventana: pedir_destino y la revisión de OBS van con dobles.

    def _boton(self, **config):
        from ytchat.ui import boton_directo
        boton = boton_directo.BotonDirecto.__new__(
            boton_directo.BotonDirecto)
        marco = mock.Mock()
        marco._alive = True
        marco._config = {"transmision_destino": "TikTok",
                         "tiktok_usuario": "guardado"}
        marco._config.update(config)
        marco._guardar_destino_transmision = mock.Mock(
            side_effect=lambda d: marco._config.update(
                {"transmision_destino": d}) or d)
        marco._guardar_usuario_tiktok = mock.Mock(
            side_effect=lambda u: marco._config.update(
                {"tiktok_usuario": u}) or u)
        marco._supervisar_transmision = mock.Mock()
        marco._actualizar_boton_directo = mock.Mock()
        boton._marco = marco
        boton.boton = mock.Mock()
        return boton, marco

    def test_cancelar_anuncia_y_no_revisa(self):
        from ytchat.ui import boton_directo
        boton, marco = self._boton()
        with mock.patch(
                "ytchat.ui.gui_elegir_destino.pedir_destino",
                return_value=None) as pedir, \
                mock.patch.object(boton_directo.diagnostico,
                                  "crear_hilo") as hilos, \
                mock.patch.object(boton_directo, "anunciar") as anunciar:
            boton._transmitir()
        pedir.assert_called_once_with(marco, "TikTok", "guardado")
        anunciar.assert_called_once_with("No se transmitió.")
        hilos.assert_not_called()
        marco._guardar_destino_transmision.assert_not_called()

    def test_youtube_guarda_y_revisa_aunque_el_guardado_decia_tiktok(self):
        from ytchat.ui import boton_directo
        boton, marco = self._boton(transmision_destino="TikTok",
                                   tiktok_usuario="guardado")
        hilos = []
        revision = mock.sentinel.revision
        preparacion = SimpleNamespace(ya_transmitiendo=False,
                                      revision=revision)

        class Hilo:
            def __init__(self, target, *args, **kwargs):
                self.target = target

            def start(self):
                hilos.append(self.target)
                self.target()

        with mock.patch(
                "ytchat.ui.gui_elegir_destino.pedir_destino",
                return_value=("YouTube", "")), \
                mock.patch.object(boton_directo.diagnostico,
                                  "crear_hilo",
                                  side_effect=lambda f, n: Hilo(f)), \
                mock.patch.object(boton_directo.transmision_directa,
                                  "preparar",
                                  return_value=preparacion) as preparar, \
                mock.patch.object(boton_directo, "anunciar"), \
                mock.patch.object(boton_directo._snd, "reproducir"), \
                mock.patch.object(boton_directo.wx,
                                  "CallAfter",
                                  side_effect=lambda f, *a: f(*a)):
            boton._transmitir()
        marco._guardar_destino_transmision.assert_called_once_with(
            "YouTube")
        preparar.assert_called_once()
        args, _ = preparar.call_args
        self.assertEqual(args[1], "YouTube")
        marco._supervisar_transmision.assert_called_once_with(
            "iniciar", "YouTube", "", revision=revision)

    def test_tiktok_guarda_usuario_y_revisa(self):
        from ytchat.ui import boton_directo
        boton, marco = self._boton()
        preparacion = SimpleNamespace(ya_transmitiendo=False,
                                      revision=mock.sentinel.revision)

        class Hilo:
            def __init__(self, target, *args, **kwargs):
                self.target = target

            def start(self):
                self.target()

        with mock.patch(
                "ytchat.ui.gui_elegir_destino.pedir_destino",
                return_value=("TikTok", "nuevo")), \
                mock.patch.object(boton_directo.diagnostico,
                                  "crear_hilo",
                                  side_effect=lambda f, n: Hilo(f)), \
                mock.patch.object(boton_directo.transmision_directa,
                                  "preparar",
                                  return_value=preparacion), \
                mock.patch.object(boton_directo, "anunciar"), \
                mock.patch.object(boton_directo._snd, "reproducir"), \
                mock.patch(
                    "ytchat.ui.gui_transmision.confirmar_transmision",
                    return_value=True), \
                mock.patch.object(boton_directo.wx,
                                  "CallAfter",
                                  side_effect=lambda f, *a: f(*a)):
            boton._transmitir()
        marco._guardar_destino_transmision.assert_called_once_with(
            "TikTok")
        marco._guardar_usuario_tiktok.assert_called_once_with("nuevo")


class TestRevisionListaSinVentana(unittest.TestCase):
    # Sin ventana: confirmar y supervisar van con dobles.

    def _boton(self):
        from ytchat.ui import boton_directo
        boton = boton_directo.BotonDirecto.__new__(
            boton_directo.BotonDirecto)
        marco = mock.Mock()
        marco._alive = True
        marco._supervisar_transmision = mock.Mock()
        marco._actualizar_boton_directo = mock.Mock()
        boton._marco = marco
        boton.boton = mock.Mock()
        return boton, marco

    def test_youtube_no_confirma_y_pasa_la_revision(self):
        from ytchat.ui import boton_directo
        boton, marco = self._boton()
        revision = mock.sentinel.revision
        preparacion = SimpleNamespace(ya_transmitiendo=False,
                                      revision=revision)
        with mock.patch(
                "ytchat.ui.gui_transmision.confirmar_transmision") as confirmar:
            boton._revision_lista(preparacion, "YouTube", "")
        confirmar.assert_not_called()
        marco._supervisar_transmision.assert_called_once_with(
            "iniciar", "YouTube", "", revision=revision)

    def test_tiktok_confirma_como_hoy(self):
        from ytchat.ui import boton_directo
        boton, marco = self._boton()
        preparacion = SimpleNamespace(ya_transmitiendo=False,
                                      revision=mock.sentinel.revision)
        with mock.patch(
                "ytchat.ui.gui_transmision.confirmar_transmision",
                return_value=True) as confirmar:
            boton._revision_lista(preparacion, "TikTok", "usuario")
        confirmar.assert_called_once_with(marco, preparacion.revision)
        marco._supervisar_transmision.assert_called_once_with(
            "iniciar", "TikTok", "usuario")

    def test_tiktok_cancelar_anuncia_y_no_inicia(self):
        from ytchat.ui import boton_directo
        boton, marco = self._boton()
        preparacion = SimpleNamespace(ya_transmitiendo=False,
                                      revision=mock.sentinel.revision)
        with mock.patch(
                "ytchat.ui.gui_transmision.confirmar_transmision",
                return_value=False), \
                mock.patch.object(boton_directo, "anunciar") as anunciar:
            boton._revision_lista(preparacion, "TikTok", "usuario")
        anunciar.assert_called_once_with("No se transmitió.")
        marco._supervisar_transmision.assert_not_called()


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestBotonDirectoVentana(unittest.TestCase):
    # Con ventana: las corre el advisor. No correr aquí.

    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()

    def _ventana(self, **config_extra):
        configuracion = {
            "atajos_raw": {}, "filtro_activo": "todos",
            "mostrar_botones_reproductor": False, "mostrar_metadatos": True,
            "mostrar_total_superchats": True, "overlay_activo": False,
            "programados_activo": False, "tiktok_usuario": "",
            "transmision_destino": "",
        }
        configuracion.update(config_extra)
        stats = SimpleNamespace(leidos=0, superchats=0, descartados=0)
        worker = SimpleNamespace(get_rate=lambda: 0, get_volume=lambda: 100)
        with mock.patch.object(gui.diagnostico, "crear_hilo"):
            frame = gui.YTChatFrame(None, configuracion, queue.Queue(),
                                    stats, worker, threading.Event())
        self.addCleanup(frame.Destroy)
        frame.ShowWithoutActivating()
        gui.wx.Yield()
        return frame

    @staticmethod
    def _sin_reproductor_ni_comentarios(frame):
        # configurar_tiktok no necesita el reproductor de verdad para lo
        # que aquí se comprueba (visibilidad del botón).
        frame._rep_panel = mock.Mock()
        frame._com_panel = mock.Mock()

    def test_en_inicio_hijo_del_panel_visible_tras_conectar_y_con_nombre(self):
        frame = self._ventana()
        boton = frame._boton_directo.boton
        self.assertIs(boton.GetParent(), frame._panel_principal)
        self.assertTrue(boton.IsShown())
        hijos = list(frame._panel_principal.GetChildren())
        self.assertEqual(hijos.index(boton),
                         hijos.index(frame.btn_conectar) + 1)
        self.assertEqual(boton.GetLabel(), "Transm&itir en directo")
        self.assertEqual(boton.GetName(), "Transmitir en directo")

    def test_con_usuario_ajeno_queda_oculto(self):
        frame = self._ventana(tiktok_usuario="mio")
        self._sin_reproductor_ni_comentarios(frame)
        frame.set_conectado(True)
        gui.wx.Yield()
        frame.configurar_tiktok("otro", "http://flujo")
        gui.wx.Yield()
        self.assertFalse(frame._boton_directo.boton.IsShown())

    def test_con_usuario_guardado_queda_visible(self):
        frame = self._ventana(tiktok_usuario="mio")
        self._sin_reproductor_ni_comentarios(frame)
        frame.set_conectado(True)
        gui.wx.Yield()
        frame.configurar_tiktok("mio", "http://flujo")
        gui.wx.Yield()
        boton = frame._boton_directo.boton
        self.assertTrue(boton.IsShown())
        self.assertEqual(boton.GetLabel(), "Transm&itir en directo")
        self.assertEqual(boton.GetName(), "Transmitir en directo")

    def test_set_conectado_sin_conexion_propia_oculta(self):
        # Prueba de cableado: sin la llamada a _actualizar_boton_directo
        # en _set_conectado_ui, el botón seguiría visible y fallaría.
        frame = self._ventana()
        self.assertTrue(frame._boton_directo.boton.IsShown())
        frame.set_conectado(True)
        gui.wx.Yield()
        self.assertFalse(frame._boton_directo.boton.IsShown())


if __name__ == "__main__":
    unittest.main()
