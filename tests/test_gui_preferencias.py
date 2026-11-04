"""Pseudotraducción del diálogo entero de Preferencias.

Abre ventanas. Recorre el diálogo con todas sus páginas y exige que lo único sin
envolver sea la unión de los pendientes que ya declaran las pruebas de
cada página (importados, no copiados) más los propios de este diálogo.
Cualquier texto nuevo sin envolver la pone en rojo.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bellbird.ai import catalogo
from bellbird.core import config
from bellbird.core import idioma
from bellbird.ui import gui, gui_preferencias
from bellbird.ui import preferencias_ia
from bellbird.ui import preferencias_ia_clave
from bellbird.ui import preferencias_transmision
from bellbird.voice import motores
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.rutas_temporales import redirigir_rutas
from tests.test_preferencias_atajos import PENDIENTES_ATAJOS
from tests.test_preferencias_musica import (
    PENDIENTES_OTROS_MODULOS as PENDIENTES_MUSICA)
from tests.test_preferencias_voz import (
    PENDIENTES_OTROS_MODULOS as PENDIENTES_VOZ)
from tests.ventanas_prueba import destruir


# Textos que arma otro módulo y aparecen en el recorrido del diálogo
# entero: no se tocan acá. Las etiquetas de la página Estado ya salen
# marcadas de `bellbird/capture/componentes_estado.py` (etiqueta()).
PENDIENTES_PROPIOS = ()


# El aviso largo de Atajos trae saltos de línea del Wrap: se comparan los
# dos lados con los espacios normalizados.
def _normalizar(texto): return " ".join(texto.split())


class TestDialogoSinTextosSinEnvolver(unittest.TestCase):
    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name)
        (self.ruta / "config.ini").write_text(config._CONFIG_FALLBACK,
                                              encoding="utf-8")
        parche = redirigir_rutas(self.ruta)
        parche.__enter__()
        self.addCleanup(parche.__exit__, None, None, None)
        # Nunca el Administrador de credenciales real.
        sin_clave = mock.patch.object(
            preferencias_ia_clave.claves, "leer", return_value="")
        sin_clave.start()
        self.addCleanup(sin_clave.stop)
        # Catálogo vacío: la lista muestra el aviso de lista vacía.
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

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._dialogo()
            sin_marcar = textos_sin_marcar(dialogo)
        # Los nombres de los idiomas van en su propio idioma y no se
        # traducen: la excepción sale de `NOMBRES_IDIOMA`, no va a mano.
        esperados = (PENDIENTES_ATAJOS + PENDIENTES_MUSICA
                     + PENDIENTES_VOZ + PENDIENTES_PROPIOS
                     + tuple(nombre for _valor, nombre
                             in idioma.idiomas_disponibles()
                             if nombre in idioma.NOMBRES_IDIOMA.values()))

        self.assertEqual(sorted(map(_normalizar, sin_marcar)),
                         sorted(map(_normalizar, esperados)))


class TestPaginaObsClips(unittest.TestCase):
    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()
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

    def _dialogo(self):
        with mock.patch.object(motores, "listar_voces", return_value=[]):
            dialogo = gui_preferencias.PreferenciasDialog(None, {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_lista_de_clips_con_treinta_segundos_de_fabrica(self):
        dialogo = self._dialogo()
        pagina = dialogo.pagina_transmision
        self.assertEqual(
            [pagina.cho_clips.GetString(i) for i in range(3)],
            ["Desactivados", "30 segundos", "60 segundos"])
        self.assertEqual(pagina.cho_clips.GetStringSelection(), "30 segundos")
        self.assertEqual(pagina.cho_clips.GetName(), "Clips")

    def test_la_pagina_obs_no_repite_letras_de_acceso(self):
        from tests.letras_acceso import letras_repetidas

        dialogo = self._dialogo()
        pagina = next(dialogo.nb.GetPage(i)
                      for i in range(dialogo.nb.GetPageCount())
                      if dialogo.nb.GetPageText(i) == "OBS")
        self.assertEqual(letras_repetidas(pagina), {})

    def test_guardar_clips_escribe_los_segundos_elegidos(self):
        dialogo = self._dialogo()
        pagina = dialogo.pagina_transmision
        pagina.cho_clips.SetSelection(2)
        guardados = {}
        pagina.guardar(
            lambda seccion, clave, valor: guardados.__setitem__(
                (seccion, clave), valor), {})
        self.assertEqual(guardados[("transmision", "clips")], "60")

    def test_clip_del_chat_activo_y_un_minuto_de_fabrica(self):
        pagina = self._dialogo().pagina_transmision
        self.assertTrue(pagina.chk_clips_chat.GetValue())
        self.assertEqual(pagina.chk_clips_chat.GetLabel(),
                         "Permitir !clip en el &chat")
        self.assertEqual(pagina.chk_clips_chat.GetName(),
                         "Permitir !clip en el chat")
        self.assertEqual(pagina.sp_clips_chat_espera.GetValue(), 1)
        self.assertEqual(pagina.sp_clips_chat_espera.GetName(),
                         "Espera entre clips del chat")

    def test_guardar_clip_del_chat_escribe_sus_dos_opciones(self):
        pagina = self._dialogo().pagina_transmision
        pagina.chk_clips_chat.SetValue(False)
        pagina.sp_clips_chat_espera.SetValue(15)
        guardados = {}
        pagina.guardar(
            lambda seccion, clave, valor: guardados.__setitem__(
                (seccion, clave), valor), {})
        self.assertEqual(guardados[("transmision", "clips_chat")], "false")
        self.assertEqual(
            guardados[("transmision", "clips_chat_espera")], "15")


class TestPaginaDescargas(unittest.TestCase):
    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()
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

    def test_pagina_descargas_tras_musica_con_nueve_controles(self):
        dialogo = self._dialogo()
        textos = [dialogo.nb.GetPageText(i)
                  for i in range(dialogo.nb.GetPageCount())]
        self.assertEqual(textos[textos.index("Música") + 1], "Descargas")
        pagina = dialogo.pagina_descargas
        self.assertEqual(
            [pagina.dir_descargas.GetName(),
             pagina.chk_descargas_numerar.GetLabel(),
             pagina.chk_descargas_carpeta_lista.GetLabel(),
             pagina.chk_descargas_preguntar.GetLabel(),
             pagina.chk_descargas_anunciar_progreso.GetLabel(),
             pagina.cho_descargas_plantilla.GetName(),
             pagina.sp_descargas_simultaneas.GetName(),
             pagina.sp_descargas_limite.GetName(),
             pagina.cho_descargas_canal.GetName()],
            ["Carpeta de descargas", "&Numerar archivos de listas",
             "Carpeta propia para cada &lista",
             "Pr&eguntar si se abre la carpeta al terminar la cola",
             "Anunciar &progreso de las descargas",
             "Nombre de los archivos",
             "Descargas simultáneas", "Límite de velocidad en MB/s",
             "Canal de actualización de yt-dlp"])
        self.assertEqual(pagina.cho_descargas_canal.GetCount(), 2)
        self.assertEqual(pagina.cho_descargas_canal.GetStringSelection(),
                         "Estable")
        self.assertEqual(pagina.cho_descargas_plantilla.GetCount(), 4)
        self.assertEqual(pagina.sp_descargas_simultaneas.GetMin(), 1)
        self.assertEqual(pagina.sp_descargas_simultaneas.GetMax(), 5)
        self.assertEqual(pagina.sp_descargas_limite.GetMax(), 1000)

    def test_preguntar_al_terminar_carga_y_guarda(self):
        texto = config._CONFIG_FALLBACK.replace(
            "[descargas]\n", "[descargas]\npreguntar_al_terminar = true\n")
        (self.ruta / "config.ini").write_text(texto, encoding="utf-8")
        dialogo = self._dialogo()
        pagina = dialogo.pagina_descargas
        self.assertEqual(pagina.chk_descargas_preguntar.GetName(),
                         "DescargasPreguntarAlTerminar")
        self.assertTrue(pagina.chk_descargas_preguntar.GetValue())
        pagina.chk_descargas_preguntar.SetValue(False)
        pagina.guardar()
        self.assertFalse(
            config.obtener_opciones_descarga()["preguntar_al_terminar"])
        pagina.chk_descargas_preguntar.SetValue(True)
        pagina.guardar()
        self.assertTrue(
            config.obtener_opciones_descarga()["preguntar_al_terminar"])

    def test_anunciar_progreso_carga_desmarcada_y_guarda(self):
        dialogo = self._dialogo()
        pagina = dialogo.pagina_descargas
        self.assertEqual(pagina.chk_descargas_anunciar_progreso.GetName(),
                         "DescargasAnunciarProgreso")
        self.assertFalse(pagina.chk_descargas_anunciar_progreso.GetValue())
        pagina.chk_descargas_anunciar_progreso.SetValue(True)
        pagina.guardar()
        self.assertTrue(
            config.obtener_opciones_descarga()["anunciar_progreso"])
        self.assertIn("anunciar_progreso = true",
                      (self.ruta / "config.ini").read_text(encoding="utf-8"))
        otro = self._dialogo()
        self.assertTrue(
            otro.pagina_descargas.chk_descargas_anunciar_progreso.GetValue())

    def test_guardar_descargas_no_pierde_formato_ni_resolucion(self):
        dialogo = self._dialogo()
        pagina = dialogo.pagina_descargas
        with mock.patch.object(config, "obtener_opciones_descarga",
                               return_value={"formato": "mp4", "bitrate": 192,
                                             "resolucion": 720, "carpeta": "/vieja",
                                             "enumerar": False, "simultaneas": 2,
                                             "limite": 0, "carpeta_lista": False,
                                             "plantilla": "titulo_id"}), \
                mock.patch.object(config, "guardar_opciones_descarga") as guardar:
            pagina.dir_descargas.SetPath("/nueva")
            pagina.chk_descargas_numerar.SetValue(True)
            pagina.chk_descargas_carpeta_lista.SetValue(True)
            pagina.cho_descargas_plantilla.SetSelection(2)
            pagina.sp_descargas_simultaneas.SetValue(5)
            pagina.sp_descargas_limite.SetValue(10)
            pagina.guardar()
        escrita = guardar.call_args.args[0]
        self.assertEqual((escrita["formato"], escrita["resolucion"]), ("mp4", 720))
        self.assertEqual((escrita["carpeta"], escrita["enumerar"],
                          escrita["carpeta_lista"], escrita["plantilla"],
                          escrita["simultaneas"], escrita["limite"]),
                         ("/nueva", True, True, "canal_titulo", 5, 10))

    def test_on_guardar_llama_a_guardar_descargas_con_lo_elegido(self):
        dialogo = self._dialogo()
        pagina = dialogo.pagina_descargas
        pagina.dir_descargas.SetPath("/nueva")
        pagina.chk_descargas_numerar.SetValue(True)
        pagina.chk_descargas_carpeta_lista.SetValue(True)
        pagina.cho_descargas_plantilla.SetSelection(2)
        pagina.sp_descargas_simultaneas.SetValue(5)
        pagina.sp_descargas_limite.SetValue(10)
        with mock.patch.object(gui_preferencias.cfg, "guardar_opciones",
                               return_value=True), \
                mock.patch.object(gui_preferencias.cfg,
                                  "guardar_opciones_descarga") as guardar_desc, \
                mock.patch.object(gui_preferencias._snd, "reproducir"), \
                mock.patch.object(preferencias_transmision, "anunciar"), \
                mock.patch.object(dialogo, "EndModal"):
            dialogo._on_guardar(None)
        escrita = guardar_desc.call_args.args[0]
        self.assertEqual((escrita["carpeta"], escrita["enumerar"],
                          escrita["carpeta_lista"], escrita["plantilla"],
                          escrita["simultaneas"], escrita["limite"]),
                         ("/nueva", True, True, "canal_titulo", 5, 10))


    def test_canal_ytdlp_abre_en_diario_y_guarda_estable(self):
        texto = config._CONFIG_FALLBACK.replace(
            "[descargas]\n", "[descargas]\ncanal_ytdlp = diario\n")
        (self.ruta / "config.ini").write_text(texto, encoding="utf-8")
        dialogo = self._dialogo()
        pagina = dialogo.pagina_descargas
        self.assertEqual(pagina.cho_descargas_canal.GetStringSelection(),
                         "Diario")
        pagina.cho_descargas_canal.SetSelection(0)
        pagina.guardar()
        self.assertEqual(
            config.obtener_opciones_descarga()["canal_ytdlp"], "estable")


if __name__ == "__main__":
    unittest.main()
