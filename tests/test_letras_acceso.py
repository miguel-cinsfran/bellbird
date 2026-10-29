"""Letras de acceso sin repetir dentro de cada página o cuadro.

Abren ventanas: van solo en la otra PC, no se corren en esta.
El ayudante vive en `tests/letras_acceso.py`. Si alguna página o
cuadro trae letras repetidas, esa prueba se marca con
`expectedFailure` y el advisor decide el arreglo.
"""

import queue
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import wx

from tests.letras_acceso import ingles, letras_repetidas
from tests.test_gui_microfono import FUENTES, PARES
from tests.test_gui_transmision import (
    GestorFalso, HiloInmediato, _asegurar_sin_obs)
from tests.ventanas_prueba import destruir
from ytchat.ai import catalogo
from ytchat.core import config
from ytchat.ui import gui_comentarios, gui_directo_youtube, gui_historial, gui_microfono, gui_transmision, gui_preferencias
from ytchat.ui import preferencias_ia
from ytchat.ui import preferencias_ia_clave
from ytchat.voice import motores
from tests.rutas_temporales import redirigir_rutas


class TestAyudanteLetrasAcceso(unittest.TestCase):
    # Con ventana: las corre el advisor en la otra PC. No correr aquí.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _panel(self):
        marco = wx.Frame(None)
        self.addCleanup(destruir, marco)
        return wx.Panel(marco)

    def test_misma_letra_da_esa_letra_con_sus_dos_rotulos(self):
        panel = self._panel()
        wx.StaticText(panel, label="&Abrir")
        wx.Button(panel, label="&Aplicar")
        wx.StaticText(panel, label="&Cerrar")
        self.assertEqual(letras_repetidas(panel),
                         {"a": ["&Abrir", "&Aplicar"]})

    def test_doble_ampersand_no_cuenta(self):
        panel = self._panel()
        wx.StaticText(panel, label="Guardar && salir")
        wx.StaticText(panel, label="Entrar && salir")
        self.assertEqual(letras_repetidas(panel), {})

    def test_control_en_cuaderno_no_choca_con_uno_de_afuera(self):
        panel = self._panel()
        wx.StaticText(panel, label="&Abrir")
        libro = wx.Notebook(panel)
        pagina = wx.Panel(libro)
        libro.AddPage(pagina, "Ficha")
        wx.StaticText(pagina, label="&Aplicar")
        self.assertEqual(letras_repetidas(panel), {})


class TestLetrasAccesoPreferencias(unittest.TestCase):
    # Con ventana: las corre el advisor en la otra PC. No correr aquí.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name)
        (self.ruta / "config.ini").write_text(config._CONFIG_FALLBACK,
                                              encoding="utf-8")
        parche = redirigir_rutas(self.ruta)
        parche.__enter__()
        self.addCleanup(parche.__exit__, None, None, None)
        sin_clave = mock.patch.object(
            preferencias_ia_clave.claves, "leer", return_value="")
        sin_clave.start()
        self.addCleanup(sin_clave.stop)
        catalogo_vacio = mock.patch.object(
            preferencias_ia.catalogo, "cargar",
            return_value={"version": catalogo.VERSION, "fecha": None,
                          "proveedores": {}})
        catalogo_vacio.start()
        self.addCleanup(catalogo_vacio.stop)

    def _dialogo(self, configuracion=None):
        with mock.patch.object(motores, "listar_voces", return_value=[]):
            dialogo = gui_preferencias.PreferenciasDialog(
                None, configuracion or {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_cada_pagina_sin_letras_repetidas(self):
        dialogo = self._dialogo()
        for pagina in dialogo._paginas():
            if pagina.GetName() == "PagProgramados":
                continue
            with self.subTest(pagina=pagina.GetName()):
                self.assertEqual(letras_repetidas(pagina), {})

    def test_pagina_programados_sin_letras_repetidas(self):
        dialogo = self._dialogo()
        pagina = next(p for p in dialogo._paginas()
                      if p.GetName() == "PagProgramados")
        self.assertEqual(letras_repetidas(pagina), {})


class TestLetrasAccesoMicrofono(unittest.TestCase):
    # Con ventana: las corre el advisor en la otra PC. No correr aquí.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_cuadro_sin_letras_repetidas(self):
        padre = wx.Frame(None)
        self.addCleanup(destruir, padre)
        padre._config = {"obs_microfono": "Mic/Aux"}
        dialogo = gui_microfono.MicrofonoObsDialog(
            padre, FUENTES, "Mic/Aux", PARES, "{usb}")
        self.addCleanup(destruir, dialogo)
        self.assertEqual(letras_repetidas(dialogo), {})


class TestLetrasAccesoDirectoYoutube(unittest.TestCase):
    # Con ventana: las corre el advisor en la otra PC. No correr aquí.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_cuadro_sin_letras_repetidas(self):
        dialogo = gui_directo_youtube.DialogoDirectoYoutube(None, titulo="Hola")
        self.addCleanup(destruir, dialogo)
        self.assertEqual(letras_repetidas(dialogo), {})


class TestLetrasAccesoHistorial(unittest.TestCase):
    # Con ventana: las corre el advisor en la otra PC. No correr aquí.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.ruta = Path(self.temporal.name) / "historial.json"
        self.ruta.write_text("[]", encoding="utf-8")

    def test_gui_historial_sin_letras_repetidas(self):
        dialogo = gui_historial.HistorialDialog(None, self.ruta, mock.Mock())
        self.addCleanup(destruir, dialogo)
        self.assertEqual(letras_repetidas(dialogo), {}, gui_historial.__name__)


class TestLetrasAccesoComentarios(unittest.TestCase):
    # Con ventana: las corre el advisor en la otra PC. No correr aquí.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_cuadro_sin_letras_repetidas(self):
        marco = wx.Frame(None)
        self.addCleanup(destruir, marco)
        panel = gui_comentarios.ComentariosPanel(
            marco, queue.Queue(), {"tamanio_fuente_chat": 12})
        self.addCleanup(destruir, panel)
        self.assertEqual(letras_repetidas(panel), {})


class TestLetrasAccesoTransmision(unittest.TestCase):
    # Con ventana: las corre el advisor en la otra PC. No correr aquí.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)
        self.parches = [
            mock.patch.object(gui_transmision.threading, "Thread",
                              HiloInmediato),
            mock.patch.object(gui_transmision.wx, "CallAfter",
                              lambda funcion, *args: funcion(*args)),
            mock.patch.object(gui_transmision, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(gui_transmision.sound_player, "reproducir"),
        ]
        for parche in self.parches:
            parche.start()
        self.addCleanup(self._frenar_parches)
        self.dialogo = gui_transmision.TransmisionDialog(
            None, GestorFalso(), asegurar=_asegurar_sin_obs)
        self.addCleanup(destruir, self.dialogo)

    def _frenar_parches(self):
        for parche in reversed(self.parches):
            parche.stop()

    def test_cuadro_sin_letras_repetidas(self):
        self.assertEqual(letras_repetidas(self.dialogo), {})


class TestLetrasAccesoPreferenciasEnIngles(TestLetrasAccesoPreferencias):
    # Con ventana: las corre el advisor en la otra PC. No correr aquí.
    # Gemela en inglés: repite las pruebas sin copiarlas.

    @classmethod
    def setUpClass(cls):
        cls._ingles = ingles()
        cls._ingles.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ingles.__exit__(None, None, None)
        del cls._ingles


class TestLetrasAccesoMicrofonoEnIngles(TestLetrasAccesoMicrofono):
    # Con ventana: las corre el advisor en la otra PC. No correr aquí.
    # Gemela en inglés: repite las pruebas sin copiarlas.

    @classmethod
    def setUpClass(cls):
        cls._ingles = ingles()
        cls._ingles.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ingles.__exit__(None, None, None)
        del cls._ingles


class TestLetrasAccesoDirectoYoutubeEnIngles(TestLetrasAccesoDirectoYoutube):
    # Con ventana: las corre el advisor en la otra PC. No correr aquí.
    # Gemela en inglés: repite las pruebas sin copiarlas.

    @classmethod
    def setUpClass(cls):
        cls._ingles = ingles()
        cls._ingles.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ingles.__exit__(None, None, None)
        del cls._ingles


class TestLetrasAccesoHistorialEnIngles(TestLetrasAccesoHistorial):
    # Con ventana: las corre el advisor en la otra PC. No correr aquí.
    # Gemela en inglés: repite las pruebas sin copiarlas.

    @classmethod
    def setUpClass(cls):
        cls._ingles = ingles()
        cls._ingles.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ingles.__exit__(None, None, None)
        del cls._ingles


class TestLetrasAccesoComentariosEnIngles(TestLetrasAccesoComentarios):
    # Con ventana: las corre el advisor en la otra PC. No correr aquí.
    # Gemela en inglés: repite las pruebas sin copiarlas.

    @classmethod
    def setUpClass(cls):
        cls._ingles = ingles()
        cls._ingles.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ingles.__exit__(None, None, None)
        del cls._ingles


class TestLetrasAccesoTransmisionEnIngles(TestLetrasAccesoTransmision):
    # Con ventana: las corre el advisor en la otra PC. No correr aquí.
    # Gemela en inglés: repite las pruebas sin copiarlas.

    @classmethod
    def setUpClass(cls):
        cls._ingles = ingles()
        cls._ingles.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ingles.__exit__(None, None, None)
        del cls._ingles


if __name__ == "__main__":
    unittest.main()
