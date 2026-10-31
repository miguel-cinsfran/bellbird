"""Letras de acceso sin repetir dentro de cada página o cuadro.

Abren ventanas. El ayudante vive en `tests/letras_acceso.py`. Si alguna página o
cuadro trae letras repetidas, esa prueba se marca con
`expectedFailure` y el arreglo se decide aparte.
"""

import queue
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import wx

from tests.letras_acceso import (
    ingles, letras_repetidas, repetidas_con_lo_de_fuera)
from tests.test_gui_microfono import FUENTES, PARES
from tests.test_gui_transmision import (
    GestorFalso, HiloInmediato, _asegurar_sin_obs)
from tests.ventanas_prueba import destruir
from bellbird.ai import catalogo
from bellbird.core import config
from bellbird.downloads import descargas, formatos_reales
from bellbird.ui import descargas_listas, elegir_formato, gui, gui_comentarios, gui_descargas, gui_directo_youtube, gui_historial, gui_microfono, gui_transmision, gui_preferencias
from bellbird.ui import preferencias_ia
from bellbird.ui import preferencias_ia_clave
from bellbird.voice import motores
from tests.rutas_temporales import redirigir_rutas


class TestAyudanteLetrasAcceso(unittest.TestCase):
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

    def test_cada_pagina_sin_letras_repetidas_con_lo_de_fuera(self):
        dialogo = self._dialogo()
        for pagina, repetidas in repetidas_con_lo_de_fuera(
                dialogo, dialogo.nb).items():
            with self.subTest(pagina=pagina):
                self.assertEqual(repetidas, {})


class TestLetrasAccesoMicrofono(unittest.TestCase):
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
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_cuadro_sin_letras_repetidas(self):
        dialogo = gui_directo_youtube.DialogoDirectoYoutube(None, titulo="Hola")
        self.addCleanup(destruir, dialogo)
        self.assertEqual(letras_repetidas(dialogo), {})


class TestLetrasAccesoHistorial(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.ruta = Path(self.temporal.name) / "historial.json"
        self.ruta.write_text("[]", encoding="utf-8")

    def test_cada_pagina_sin_letras_repetidas_con_lo_de_fuera(self):
        dialogo = gui_historial.HistorialDialog(None, self.ruta, mock.Mock())
        self.addCleanup(destruir, dialogo)
        for pagina, repetidas in repetidas_con_lo_de_fuera(
                dialogo, dialogo.nb).items():
            with self.subTest(pagina=pagina):
                self.assertEqual(repetidas, {}, gui_historial.__name__)


class TestLetrasAccesoComentarios(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_cuadro_sin_letras_repetidas(self):
        marco = wx.Frame(None)
        self.addCleanup(destruir, marco)
        panel = gui_comentarios.ComentariosPanel(
            marco, queue.Queue(), {"tamanio_fuente_chat": 12})
        self.addCleanup(destruir, panel)
        self.assertEqual(letras_repetidas(panel), {})


def _opciones_formato_ejemplo():
    return [
        formatos_reales.OpcionFormato(
            etiqueta="1080p, MP4, 100 MB", selector="299+140",
            contenedor="mp4", tamano=100000000),
        formatos_reales.OpcionFormato(
            etiqueta="720p, MP4, 50 MB", selector="22+140",
            contenedor="mp4", tamano=50000000),
        formatos_reales.OpcionFormato(
            etiqueta="Solo audio, M4A, 128 kbps, 5 MB", selector="140",
            contenedor="m4a", tamano=5000000),
    ]


class TestLetrasAccesoElegirFormato(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_cuadro_sin_letras_repetidas(self):
        dialogo = elegir_formato.DialogoFormato(
            None, _opciones_formato_ejemplo())
        self.addCleanup(destruir, dialogo)
        self.assertEqual(letras_repetidas(dialogo), {})


class TestLetrasAccesoDescargas(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _dialogo(self):
        cargar = mock.patch.object(descargas_listas.historial_descargas, "cargar",
                                   return_value=[])
        guardar = mock.patch.object(descargas_listas.historial_descargas, "guardar")
        cargar.start()
        guardar.start()
        self.addCleanup(cargar.stop)
        self.addCleanup(guardar.stop)
        dialogo = gui_descargas.GestorDescargasDialog(None)
        self.addCleanup(destruir, dialogo)
        self.addCleanup(setattr, gui_descargas, "_dialogo_activo", None)
        self.addCleanup(descargas.reiniciar_gestor)
        return dialogo

    def test_cada_pestana_sin_letras_repetidas_con_lo_de_fuera(self):
        dialogo = self._dialogo()
        for pagina, repetidas in repetidas_con_lo_de_fuera(
                dialogo, dialogo.pestanas).items():
            with self.subTest(pagina=pagina):
                self.assertEqual(repetidas, {})


class TestLetrasAccesoTransmision(unittest.TestCase):
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


class TestLetrasAccesoPrincipal(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _ventana(self):
        configuracion = {
            "atajos_raw": {}, "filtro_activo": "todos",
            "mostrar_botones_reproductor": False, "mostrar_metadatos": True,
            "mostrar_total_superchats": True, "overlay_activo": False,
            "programados_activo": False,
        }
        stats = SimpleNamespace(leidos=0, superchats=0, descartados=0)
        worker = SimpleNamespace(get_rate=lambda: 0, get_volume=lambda: 100)
        with mock.patch.object(gui.diagnostico, "crear_hilo"):
            frame = gui.YTChatFrame(None, configuracion, queue.Queue(),
                                    stats, worker, threading.Event())
        self.addCleanup(destruir, frame)
        frame.ShowWithoutActivating()
        wx.Yield()
        return frame

    def test_cada_pagina_sin_letras_repetidas_con_lo_de_fuera(self):
        frame = self._ventana()
        for pagina, repetidas in repetidas_con_lo_de_fuera(
                frame, frame.nb).items():
            with self.subTest(pagina=pagina):
                self.assertEqual(repetidas, {})


class TestLetrasAccesoPreferenciasEnIngles(TestLetrasAccesoPreferencias):
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
    # Gemela en inglés: repite las pruebas sin copiarlas.

    @classmethod
    def setUpClass(cls):
        cls._ingles = ingles()
        cls._ingles.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ingles.__exit__(None, None, None)
        del cls._ingles


class TestLetrasAccesoElegirFormatoEnIngles(TestLetrasAccesoElegirFormato):
    # Gemela en inglés: repite la prueba sin copiarla.

    @classmethod
    def setUpClass(cls):
        cls._ingles = ingles()
        cls._ingles.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ingles.__exit__(None, None, None)
        del cls._ingles


class TestLetrasAccesoDescargasEnIngles(TestLetrasAccesoDescargas):
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
    # Gemela en inglés: repite las pruebas sin copiarlas.

    @classmethod
    def setUpClass(cls):
        cls._ingles = ingles()
        cls._ingles.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ingles.__exit__(None, None, None)
        del cls._ingles


class TestLetrasAccesoPrincipalEnIngles(TestLetrasAccesoPrincipal):
    # Gemela en inglés: repite la prueba sin copiarla.

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
