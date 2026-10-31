"""Etiquetas de campo con dos puntos en todas las páginas de Preferencias.

Abren ventanas. El ayudante vive en `tests/etiquetas_campo.py`.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import wx

from tests.etiquetas_campo import etiquetas_sin_dos_puntos
from tests.ventanas_prueba import destruir
from bellbird.ai import catalogo
from bellbird.core import config
from bellbird.ui import gui_preferencias
from bellbird.ui import preferencias_ia
from bellbird.ui import preferencias_ia_clave
from bellbird.voice import motores
from tests.rutas_temporales import redirigir_rutas


class TestAyudanteEtiquetasCampo(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_una_con_dos_puntos_pasa_y_otra_sin_ellos_falla(self):
        marco = wx.Frame(None)
        self.addCleanup(destruir, marco)
        panel = wx.Panel(marco)
        wx.StaticText(panel, label="&Nombre:")
        wx.TextCtrl(panel)
        wx.StaticText(panel, label="&Edad")
        wx.TextCtrl(panel)
        self.assertEqual(etiquetas_sin_dos_puntos(panel), ["&Edad"])


class TestEtiquetasCampoPreferencias(unittest.TestCase):
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

    def test_todas_las_paginas_sin_etiquetas_sin_dos_puntos(self):
        dialogo = self._dialogo()
        for pagina in dialogo._paginas():
            with self.subTest(pagina=pagina.GetName()):
                self.assertEqual(etiquetas_sin_dos_puntos(pagina), [])


if __name__ == "__main__":
    unittest.main()
