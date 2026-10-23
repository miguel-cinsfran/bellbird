"""Adaptador de la captura hacia la ventana (VistaGui)."""

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import wx

import main
from ytchat.ui.vista_captura import VistaGui


class BaseVista(unittest.TestCase):
    def setUp(self):
        self.marco = mock.Mock()
        self.marco._alive = True
        self.gui_falsa = types.SimpleNamespace(
            _gui_frame=self.marco, anunciar=mock.Mock())
        self.modulo_anterior = sys.modules.get("ytchat.ui.gui")
        sys.modules["ytchat.ui.gui"] = self.gui_falsa
        # `from ytchat.ui import gui` mira primero el atributo del paquete:
        # sin esto usaría el módulo real si otra prueba ya lo importó.
        from ytchat import ui as _paquete_ui
        self._parche_paquete = mock.patch.object(
            _paquete_ui, "gui", self.gui_falsa, create=True)
        self._parche_paquete.start()
        llamadas = []

        def ejecutar(fn, *args, **kwargs):
            llamadas.append((fn, args, kwargs))
            return fn(*args, **kwargs)

        self._parche_call = mock.patch.object(
            wx, "CallAfter", side_effect=ejecutar)
        self._parche_call.start()
        self.llamadas = llamadas
        self.vista = VistaGui()

    def tearDown(self):
        self._parche_call.stop()
        self._parche_paquete.stop()
        if self.modulo_anterior is None:
            sys.modules.pop("ytchat.ui.gui", None)
        else:
            sys.modules["ytchat.ui.gui"] = self.modulo_anterior


class TestUrlInvalida(BaseVista):
    def test_programa_con_marco(self):
        self.assertTrue(self.vista.url_invalida())
        self.marco.url_invalida.assert_called_once_with()

    def test_sin_marco_no_hace_nada(self):
        self.gui_falsa._gui_frame = None
        self.assertFalse(self.vista.url_invalida())
        self.assertEqual(self.llamadas, [])

    def test_con_marco_cerrado_igual_programa(self):
        # Hoy solo se comprueba que el marco exista, no _alive.
        self.marco._alive = False
        self.assertTrue(self.vista.url_invalida())
        self.marco.url_invalida.assert_called_once_with()


class TestAgregarMensaje(BaseVista):
    def test_pasa_todos_los_argumentos(self):
        self.assertTrue(self.vista.agregar_mensaje(
            "Ana", "Hola", "12:00", "text", "US$ 5", "CANAL1",
            plataforma="youtube", rol="moderador"))
        self.marco.agregar_mensaje_chat.assert_called_once_with(
            "Ana", "Hola", "12:00", "text", "US$ 5", "CANAL1",
            plataforma="youtube", rol="moderador")

    def test_sin_marco_no_hace_nada(self):
        self.gui_falsa._gui_frame = None
        self.assertFalse(self.vista.agregar_mensaje(
            "Ana", "Hola", "12:00", "text", "", "", plataforma="tiktok"))
        self.assertEqual(self.llamadas, [])

    def test_con_marco_cerrado_no_hace_nada(self):
        self.marco._alive = False
        self.assertFalse(self.vista.agregar_mensaje(
            "Ana", "Hola", "12:00", "text", "", ""))
        self.assertEqual(self.llamadas, [])


class TestSetConectado(BaseVista):
    def test_sin_sonido_no_pasa_el_argumento(self):
        self.assertTrue(self.vista.set_conectado(True))
        self.marco.set_conectado.assert_called_once_with(True)
        _fn, args, _kwargs = self.llamadas[0]
        self.assertEqual(args, (True,))

    def test_con_sonido_lo_pasa(self):
        self.assertTrue(self.vista.set_conectado(False, "fin_directo"))
        self.marco.set_conectado.assert_called_once_with(False, "fin_directo")

    def test_con_marco_cerrado_no_hace_nada(self):
        self.marco._alive = False
        self.assertFalse(self.vista.set_conectado(True))
        self.assertEqual(self.llamadas, [])

    def test_variante_si_existe_con_marco_cerrado_programa(self):
        self.marco._alive = False
        self.assertTrue(self.vista.set_conectado_si_existe(False))
        self.marco.set_conectado.assert_called_once_with(False)

    def test_variante_si_existe_sin_marco_no_hace_nada(self):
        self.gui_falsa._gui_frame = None
        self.assertFalse(self.vista.set_conectado_si_existe(False))
        self.assertEqual(self.llamadas, [])


class TestTituloYMetadatos(BaseVista):
    def test_set_titulo(self):
        self.assertTrue(self.vista.set_titulo("Título"))
        self.marco.set_titulo_stream.assert_called_once_with("Título")

    def test_set_titulo_con_marco_cerrado_no_hace_nada(self):
        self.marco._alive = False
        self.assertFalse(self.vista.set_titulo("Título"))
        self.assertEqual(self.llamadas, [])

    def test_set_titulo_si_existe_con_marco_cerrado_programa(self):
        self.marco._alive = False
        self.assertTrue(self.vista.set_titulo_si_existe("Título"))
        self.marco.set_titulo_stream.assert_called_once_with("Título")

    def test_set_tipo_video(self):
        self.assertTrue(self.vista.set_tipo_video("live", "dQw4w9WgXcQ"))
        self.marco.set_tipo_video.assert_called_once_with("live", "dQw4w9WgXcQ")

    def test_set_tipo_video_si_existe_con_marco_cerrado_programa(self):
        self.marco._alive = False
        self.assertTrue(self.vista.set_tipo_video_si_existe("live", "dQw4w9WgXcQ"))
        self.marco.set_tipo_video.assert_called_once_with("live", "dQw4w9WgXcQ")

    def test_set_metadatos(self):
        meta = {"canal": "Canal"}
        self.assertTrue(self.vista.set_metadatos(meta))
        self.marco.set_metadatos.assert_called_once_with(meta)

    def test_set_metadatos_si_existe_con_marco_cerrado_programa(self):
        self.marco._alive = False
        meta = {"canal": "Canal"}
        self.assertTrue(self.vista.set_metadatos_si_existe(meta))
        self.marco.set_metadatos.assert_called_once_with(meta)

    def test_registrar_historial(self):
        self.assertTrue(self.vista.registrar_historial(
            "youtube", "vid", "https://url", "Título", "Canal", True))
        self.marco.registrar_historial.assert_called_once_with(
            "youtube", "vid", "https://url", "Título", "Canal", True)

    def test_registrar_historial_si_existe_con_marco_cerrado_programa(self):
        self.marco._alive = False
        self.assertTrue(self.vista.registrar_historial_si_existe(
            "tiktok", "pepe", "https://url", "Título", "", True))
        self.marco.registrar_historial.assert_called_once_with(
            "tiktok", "pepe", "https://url", "Título", "", True)

    def test_sin_marco_no_hace_nada(self):
        self.gui_falsa._gui_frame = None
        self.assertFalse(self.vista.set_titulo("Título"))
        self.assertFalse(self.vista.set_tipo_video("live", "vid"))
        self.assertFalse(self.vista.set_metadatos({}))
        self.assertFalse(self.vista.registrar_historial(
            "youtube", "v", "u", "t", "c", False))
        self.assertEqual(self.llamadas, [])


class TestDirectoYTikTok(BaseVista):
    def test_set_espectadores(self):
        self.assertTrue(self.vista.set_espectadores(42))
        self.marco.set_espectadores.assert_called_once_with(42)

    def test_set_espectadores_con_marco_cerrado_no_hace_nada(self):
        self.marco._alive = False
        self.assertFalse(self.vista.set_espectadores(42))
        self.assertEqual(self.llamadas, [])

    def test_set_inicio_directo(self):
        self.assertTrue(self.vista.set_inicio_directo("12:00"))
        self.marco.set_inicio_directo.assert_called_once_with("12:00")

    def test_configurar_tiktok(self):
        self.assertTrue(self.vista.configurar_tiktok("pepe", "http://flujo"))
        self.marco.configurar_tiktok.assert_called_once_with("pepe", "http://flujo")

    def test_configurar_tiktok_sin_marco_no_hace_nada(self):
        self.gui_falsa._gui_frame = None
        self.assertFalse(self.vista.configurar_tiktok("pepe", "http://flujo"))
        self.assertEqual(self.llamadas, [])


class TestAnunciarYFallo(BaseVista):
    def test_anunciar(self):
        self.assertTrue(self.vista.anunciar("Hola"))
        self.gui_falsa.anunciar.assert_called_once_with("Hola")

    def test_anunciar_con_marco_cerrado_no_hace_nada(self):
        self.marco._alive = False
        self.assertFalse(self.vista.anunciar("Hola"))
        self.gui_falsa.anunciar.assert_not_called()

    def test_fallo_video_delega_en_main(self):
        meta = {"fallo": "No se pudo conectar"}
        with mock.patch.object(main, "_anunciar_fallo_video") as anunciar_fallo:
            self.assertTrue(self.vista.fallo_video(meta))
        anunciar_fallo.assert_called_once_with(meta, wx.CallAfter)

    def test_fallo_video_con_marco_cerrado_igual_delega(self):
        self.marco._alive = False
        with mock.patch.object(main, "_anunciar_fallo_video") as anunciar_fallo:
            self.assertTrue(self.vista.fallo_video({}))
        anunciar_fallo.assert_called_once_with({}, wx.CallAfter)

    def test_fallo_video_sin_marco_no_hace_nada(self):
        self.gui_falsa._gui_frame = None
        with mock.patch.object(main, "_anunciar_fallo_video") as anunciar_fallo:
            self.assertFalse(self.vista.fallo_video({}))
        anunciar_fallo.assert_not_called()


class TestActiva(BaseVista):
    def test_activa_con_marco_vivo(self):
        self.assertTrue(self.vista.activa)

    def test_inactiva_con_marco_cerrado(self):
        self.marco._alive = False
        self.assertFalse(self.vista.activa)

    def test_inactiva_sin_marco(self):
        self.gui_falsa._gui_frame = None
        self.assertFalse(self.vista.activa)


class TestConexionPropia(BaseVista):
    def test_verdadera_si_el_marco_la_marca(self):
        self.marco._conexion_propia = True
        self.assertTrue(self.vista.conexion_propia)

    def test_falsa_si_el_marco_no_la_marca(self):
        self.marco._conexion_propia = False
        self.assertFalse(self.vista.conexion_propia)

    def test_falsa_sin_marco(self):
        self.gui_falsa._gui_frame = None
        self.assertFalse(self.vista.conexion_propia)


class TestEstructuraConexion(unittest.TestCase):
    def test_conexion_no_conoce_la_interfaz(self):
        raiz = Path(__file__).resolve().parent.parent
        texto = (raiz / "ytchat" / "capture" / "conexion.py").read_text(
            encoding="utf-8")
        self.assertNotIn("import wx", texto)
        self.assertNotIn("ytchat.ui", texto)
        self.assertNotIn("_gui_frame", texto)


class TestCableadoVista(unittest.TestCase):
    def test_armar_callbacks_pasa_vista_gui(self):
        with mock.patch.object(main.conexion, "Conexiones") as Conexiones:
            main.armar_callbacks_captura(object(), {}, object(), object())
        _args, kwargs = Conexiones.call_args
        self.assertIsInstance(kwargs["vista"], VistaGui)


if __name__ == "__main__":
    unittest.main()
