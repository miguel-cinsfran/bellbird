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

    def test_pagina_descargas_tras_musica_con_seis_controles(self):
        dialogo = self._dialogo()
        textos = [dialogo.nb.GetPageText(i)
                  for i in range(dialogo.nb.GetPageCount())]
        self.assertEqual(textos[textos.index("Música") + 1], "Descargas")
        pagina = dialogo.pagina_descargas
        self.assertEqual(
            [pagina.dir_descargas.GetName(),
             pagina.chk_descargas_numerar.GetLabel(),
             pagina.chk_descargas_carpeta_lista.GetLabel(),
             pagina.cho_descargas_plantilla.GetName(),
             pagina.sp_descargas_simultaneas.GetName(),
             pagina.sp_descargas_limite.GetName()],
            ["Carpeta de descargas", "&Numerar archivos de listas",
             "Carpeta propia para cada &lista", "Nombre de los archivos",
             "Descargas simultáneas", "Límite de velocidad en MB/s"])
        self.assertEqual(pagina.cho_descargas_plantilla.GetCount(), 4)
        self.assertEqual(pagina.sp_descargas_simultaneas.GetMin(), 1)
        self.assertEqual(pagina.sp_descargas_simultaneas.GetMax(), 5)
        self.assertEqual(pagina.sp_descargas_limite.GetMax(), 1000)

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
                mock.patch.object(gui_preferencias, "anunciar"), \
                mock.patch.object(dialogo, "EndModal"):
            dialogo._on_guardar(None)
        escrita = guardar_desc.call_args.args[0]
        self.assertEqual((escrita["carpeta"], escrita["enumerar"],
                          escrita["carpeta_lista"], escrita["plantilla"],
                          escrita["simultaneas"], escrita["limite"]),
                         ("/nueva", True, True, "canal_titulo", 5, 10))


if __name__ == "__main__":
    unittest.main()
