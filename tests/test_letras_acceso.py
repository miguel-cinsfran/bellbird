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
    GestorFalso, HiloInmediato, OperacionesFalsas, PrincipalFalsa)
from tests.ventanas_prueba import app_de_prueba, destruir
from guyrapu.ai import catalogo
from guyrapu.core import config
from guyrapu.downloads import descargas, formatos_reales
from guyrapu.obs import disenos_escena
from guyrapu.obs.filtros_microfono import Estado
from guyrapu.ui import descargas_listas, operaciones_obs, elegir_formato, gui, gui_comentarios, gui_descargas, gui_directo_youtube, gui_grabaciones, gui_historial, gui_microfono, gui_transmision, gui_preferencias, control_grabacion, mover_con_flechas
from guyrapu.ui import escena_disenos
from guyrapu.ui import escena_filtros
from guyrapu.ui import escena_captura_ventana
from guyrapu.ui import escena_pagina_audio
from guyrapu.ui import escena_pagina_escena
from guyrapu.ui import escena_pagina_fuentes
from guyrapu.ui import escena_propiedades
from guyrapu.ui import escena_tamano
from guyrapu.ui import obs_ventana
from guyrapu.ui import preferencias_ia
from guyrapu.ui import preferencias_ia_clave
from guyrapu.ui import restream_ventana
from guyrapu.voice import motores
from tests.rutas_temporales import redirigir_rutas


class TestAyudanteLetrasAcceso(unittest.TestCase):
    def setUp(self):
        self.app = app_de_prueba()

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
        self.app = app_de_prueba()
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
        self.app = app_de_prueba()

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
        self.app = app_de_prueba()

    def test_cuadro_sin_letras_repetidas(self):
        dialogo = gui_directo_youtube.DialogoDirectoYoutube(None, titulo="Hola")
        self.addCleanup(destruir, dialogo)
        self.assertEqual(letras_repetidas(dialogo), {})


class TestLetrasAccesoHistorial(unittest.TestCase):
    def setUp(self):
        self.app = app_de_prueba()
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


class TestLetrasAccesoGrabaciones(unittest.TestCase):
    def setUp(self):
        self.app = app_de_prueba()
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.ruta = Path(self.temporal.name) / "grabaciones.json"
        parche = mock.patch.object(gui_grabaciones.grabaciones.paths,
                                   "grabaciones", return_value=self.ruta)
        parche.start()
        self.addCleanup(parche.stop)

    def test_cuadro_sin_letras_repetidas(self):
        padre = wx.Frame(None)
        self.addCleanup(destruir, padre)
        panel = gui_grabaciones.PanelGrabaciones(padre)
        self.addCleanup(destruir, panel)
        self.assertEqual(letras_repetidas(panel), {},
                         gui_grabaciones.__name__)


class TestLetrasAccesoComentarios(unittest.TestCase):
    def setUp(self):
        self.app = app_de_prueba()

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
        self.app = app_de_prueba()

    def test_cuadro_sin_letras_repetidas(self):
        dialogo = elegir_formato.DialogoFormato(
            None, _opciones_formato_ejemplo())
        self.addCleanup(destruir, dialogo)
        self.assertEqual(letras_repetidas(dialogo), {})


class TestLetrasAccesoDescargas(unittest.TestCase):
    def setUp(self):
        self.app = app_de_prueba()

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
        self.app = app_de_prueba()
        self.parches = [
            mock.patch.object(threading, "Thread",
                              HiloInmediato),
            mock.patch.object(gui_transmision.wx, "CallAfter",
                              lambda funcion, *args: funcion(*args)),
            mock.patch.object(gui_transmision, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(operaciones_obs, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(control_grabacion.sound_player, "reproducir"),
        ]
        for parche in self.parches:
            parche.start()
        self.addCleanup(self._frenar_parches)
        self.marco = wx.Frame(None)
        self.addCleanup(destruir, self.marco)
        self.dialogo = gui_transmision.PaginaTransmision(
            self.marco, PrincipalFalsa(), GestorFalso(), OperacionesFalsas())
        self.addCleanup(destruir, self.dialogo)

    def _frenar_parches(self):
        for parche in reversed(self.parches):
            parche.stop()

    def test_cuadro_sin_letras_repetidas(self):
        self.assertEqual(letras_repetidas(self.dialogo), {})

    def test_etiquetas_alternativas_sin_letras_repetidas(self):
        self.dialogo._directo.sincronizar(True)
        self.dialogo._aplicar_visibilidad()
        self.assertEqual(letras_repetidas(self.dialogo), {})
        self.dialogo._directo.sincronizar(True, deteniendo=True)
        self.dialogo._aplicar_visibilidad()
        self.assertEqual(letras_repetidas(self.dialogo), {})


class TestLetrasAccesoPanelObs(unittest.TestCase):
    def setUp(self):
        self.app = app_de_prueba()
        self.parches = [
            mock.patch.object(threading, "Thread", HiloInmediato),
            mock.patch.object(obs_ventana.wx, "CallAfter",
                              lambda funcion, *args: funcion(*args)),
            mock.patch.object(obs_ventana.obs_lanzador, "asegurar_obs",
                              lambda probar_conexion, al_anunciar=None,
                              parada=None: probar_conexion()),
            mock.patch.object(obs_ventana, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(escena_pagina_escena, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(escena_pagina_fuentes, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(escena_captura_ventana, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(gui_microfono, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(mover_con_flechas, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(operaciones_obs, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(operaciones_obs.sound_player, "reproducir"),
            mock.patch.object(control_grabacion, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(control_grabacion.sound_player, "reproducir"),
            mock.patch.object(gui_grabaciones, "anunciar",
                              lambda *args, **kwargs: None),
            mock.patch.object(gui_grabaciones.sound_player, "reproducir"),
            mock.patch.object(gui_grabaciones.grabaciones, "existentes",
                              return_value=[]),
        ]
        for parche in self.parches:
            parche.start()
        self.addCleanup(self._frenar)
        self.principal = SimpleNamespace(
            _config={"grabar_al_transmitir": False,
                     "obs_microfono": "Mic/Aux"})
        self.dialogo = obs_ventana.VentanaObs(
            None, self.principal, gestor=GestorFalso())
        self.addCleanup(destruir, self.dialogo)

    def _frenar(self):
        for parche in reversed(self.parches):
            parche.stop()

    def test_cada_pestana_sin_letras_repetidas_con_ayuda(self):
        for pagina, repetidas in repetidas_con_lo_de_fuera(
                self.dialogo, self.dialogo.nb).items():
            with self.subTest(pagina=pagina):
                self.assertEqual(repetidas, {})

    def test_etiquetas_alternativas_de_grabacion(self):
        grabacion = self.dialogo._pagina_grabacion._grabacion
        for grabando, pausa in ((True, False), (True, True)):
            grabacion.fijar(grabando, pausa)
            for pagina, repetidas in repetidas_con_lo_de_fuera(
                    self.dialogo, self.dialogo.nb).items():
                with self.subTest(pagina=pagina):
                    self.assertEqual(repetidas, {})


class TestLetrasAccesoTamano(unittest.TestCase):
    def setUp(self):
        self.app = app_de_prueba()

    def test_cuadro_sin_letras_repetidas(self):
        dialogo = escena_tamano.TamanoFuenteDialog(None, 29, 69)
        self.addCleanup(destruir, dialogo)
        self.assertEqual(letras_repetidas(dialogo), {})


class TestLetrasAccesoPropiedades(unittest.TestCase):
    def setUp(self):
        self.app = app_de_prueba()

    def test_los_cuadros_nuevos_sin_letras_repetidas(self):
        casos = (
            escena_propiedades.DialogoEleccion(
                None, "Captura de pantalla", "DialogoPantalla",
                "&Pantalla:", (("HP", "hp"),), "", ""),
            escena_propiedades.DialogoJuego(
                None, (("Champions", "champions"),), {}),
            escena_propiedades.DialogoArchivo(None, "imagen", {}),
            escena_propiedades.DialogoArchivo(None, "multimedia", {}),
            escena_propiedades.DialogoTexto(None, {}),
        )
        for dialogo in casos:
            self.addCleanup(destruir, dialogo)
            self.assertEqual(letras_repetidas(dialogo), {})


class TestLetrasAccesoDisenos(unittest.TestCase):
    def setUp(self):
        self.app = app_de_prueba()

    def test_cuadro_sin_letras_repetidas(self):
        fuentes = [
            disenos_escena.Fuente("Juego", "otra", 1600, 900),
            disenos_escena.Fuente("Cámara", "camara", 1280, 720),
            disenos_escena.Fuente("Chat en el vídeo", "chat", 460, 620),
        ]
        dialogo = escena_disenos.DisenoEscenaDialog(None, fuentes, [])
        self.addCleanup(destruir, dialogo)
        self.assertEqual(letras_repetidas(dialogo), {})


class TestLetrasAccesoFiltros(unittest.TestCase):
    def setUp(self):
        self.app = app_de_prueba()

    def test_cuadro_sin_letras_repetidas(self):
        dialogo = escena_filtros.FiltrosMicrofonoDialog(
            None, "Mic/Aux", Estado(True, False, 6))
        self.addCleanup(destruir, dialogo)
        self.assertEqual(letras_repetidas(dialogo), {})


class TestLetrasAccesoRestream(unittest.TestCase):
    class _CuentaFalsa:
        def conectada(self):
            return False

    def setUp(self):
        self.app = app_de_prueba()
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.ruta = Path(self.temporal.name) / "perfiles_restream.json"

    def test_cada_pestana_sin_letras_repetidas_con_lo_de_fuera(self):
        dialogo = restream_ventana.VentanaRestream(
            None, self._CuentaFalsa(), lambda: [], self.ruta)
        self.addCleanup(destruir, dialogo)
        for pagina, repetidas in repetidas_con_lo_de_fuera(
                dialogo, dialogo.nb).items():
            with self.subTest(pagina=pagina):
                self.assertEqual(repetidas, {})


class TestLetrasAccesoPrincipal(unittest.TestCase):
    def setUp(self):
        self.app = app_de_prueba()

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
            frame = gui.VentanaPrincipal(None, configuracion, queue.Queue(),
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


class TestLetrasAccesoGrabacionesEnIngles(TestLetrasAccesoGrabaciones):
    # Gemela en inglés: repite la prueba sin copiarla.

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


class TestLetrasAccesoPanelObsEnIngles(TestLetrasAccesoPanelObs):
    # Gemela en inglés: repite las pruebas sin copiarlas.

    @classmethod
    def setUpClass(cls):
        cls._ingles = ingles()
        cls._ingles.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ingles.__exit__(None, None, None)
        del cls._ingles


class TestLetrasAccesoTamanoEnIngles(TestLetrasAccesoTamano):
    # Gemela en inglés: repite la prueba sin copiarla.

    @classmethod
    def setUpClass(cls):
        cls._ingles = ingles()
        cls._ingles.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ingles.__exit__(None, None, None)
        del cls._ingles


class TestLetrasAccesoDisenosEnIngles(TestLetrasAccesoDisenos):
    # Gemela en inglés: repite la prueba sin copiarla.

    @classmethod
    def setUpClass(cls):
        cls._ingles = ingles()
        cls._ingles.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ingles.__exit__(None, None, None)
        del cls._ingles


class TestLetrasAccesoFiltrosEnIngles(TestLetrasAccesoFiltros):
    # Gemela en inglés: repite la prueba sin copiarla.

    @classmethod
    def setUpClass(cls):
        cls._ingles = ingles()
        cls._ingles.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._ingles.__exit__(None, None, None)
        del cls._ingles


class TestLetrasAccesoRestreamEnIngles(TestLetrasAccesoRestream):
    # Gemela en inglés: repite la prueba sin copiarla.

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
