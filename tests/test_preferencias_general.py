"""Pseudotraducción de la página General de Preferencias.

Abre ventanas: la corre el advisor en la otra PC, no se corre acá.
Comprueba que ningún texto visible de la página queda sin pasar por
gettext.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ytchat.core import config
from ytchat.core import idioma
from ytchat.ui import gui, gui_preferencias
from ytchat.voice import motores
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.rutas_temporales import redirigir_rutas
from tests.ventanas_prueba import destruir


class TestGeneralSinTextosSinEnvolver(unittest.TestCase):
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

    def _pagina(self, dialogo):
        return next(dialogo.nb.GetPage(i)
                    for i in range(dialogo.nb.GetPageCount())
                    if dialogo.nb.GetPage(i).GetName() == "PagGeneral")

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._dialogo()
            sin_marcar = textos_sin_marcar(self._pagina(dialogo))

        # Los nombres de los idiomas van en su propio idioma y no se
        # traducen: la excepción sale de `NOMBRES_IDIOMA`, no va a mano.
        esperados = [nombre for _valor, nombre in idioma.idiomas_disponibles()
                     if nombre in idioma.NOMBRES_IDIOMA.values()]
        self.assertEqual(sorted(sin_marcar), sorted(esperados))


if __name__ == "__main__":
    unittest.main()
