"""Pruebas de la página Cola de lectura del diálogo de Preferencias.

Abren ventanas: las corre el advisor en la otra PC, no se corren acá.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ytchat.core import config
from ytchat.ui import gui, gui_preferencias
from ytchat.voice import motores
from tests.rutas_temporales import redirigir_rutas
from tests.ventanas_prueba import destruir


class TestUmbralEnSizer(unittest.TestCase):
    """El contador va en el sizer de la página, con los mismos márgenes
    que el tamaño máximo de la cola.

    Abren ventanas: las corre el advisor en la otra PC, no se corren acá.
    """

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

    def _dialogo(self, configuracion=None):
        with mock.patch.object(motores, "listar_voces",
                               return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(
                None, configuracion or {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def _pagina_cola(self, dialogo):
        return next(p for p in dialogo._paginas()
                    if p.GetName() == "PagCola")

    def test_contador_esta_en_el_sizer_de_la_pagina(self):
        dialogo = self._dialogo()
        pagina = self._pagina_cola(dialogo)
        self.assertIs(dialogo.sp_umbral_nombre.GetContainingSizer(),
                      pagina.GetSizer())

    def test_contador_con_los_mismos_margenes_que_tamanio_maximo(self):
        dialogo = self._dialogo()
        pagina = self._pagina_cola(dialogo)
        items = {it.GetWindow(): it for it in pagina.GetSizer().GetChildren()}
        for control in (dialogo.sp_cola_maxima, dialogo.sp_umbral_nombre):
            with self.subTest(control=control.GetName()):
                item = items[control]
                self.assertEqual(item.GetBorder(), 10)
                self.assertTrue(item.GetFlag() & gui.wx.BOTTOM)


if __name__ == "__main__":
    unittest.main()
