"""Pseudotraducción de la página Voces de Preferencias.

Abre ventanas: la corre el advisor en la otra PC, no se corre acá.
Construye el diálogo de Preferencias con la pseudotraducción y exige que
la página no deje ningún texto visible sin envolver.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ytchat.ui import gui, gui_preferencias
from ytchat.voice import motores
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.rutas_temporales import redirigir_rutas
from tests.ventanas_prueba import destruir


# Textos que arma otro módulo y aparecen en la parte recorrida: no se
# tocan acá. Los nombres de los motores salen de `ytchat/voice/motores.py`
# (NOMBRES). La lista de voces se finge vacía, así los combinados muestran
# el aviso propio, ya envuelto.
PENDIENTES_OTROS_MODULOS = (
    "Windows SAPI 5",
    "Windows OneCore",
    "ElevenLabs, en la nube",
)


class TestPseudoVoz(unittest.TestCase):
    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        parche = redirigir_rutas(Path(self.tmp.name))
        parche.__enter__()
        self.addCleanup(parche.__exit__, None, None, None)

    def _dialogo(self):
        with mock.patch.object(motores, "listar_voces", return_value=[]):
            dialogo = gui_preferencias.PreferenciasDialog(None, {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._dialogo()
            pagina = next(p for p in dialogo._paginas()
                          if p.GetName() == "PagVoz")
            sin_marcar = textos_sin_marcar(pagina)

        self.assertEqual(sorted(sin_marcar),
                         sorted(PENDIENTES_OTROS_MODULOS))


if __name__ == "__main__":
    unittest.main()
