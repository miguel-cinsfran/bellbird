"""Pseudotraducción de la página Inteligencia artificial de Preferencias.

Abre ventanas: la corre el advisor en la otra PC, no se corre acá.
Construye el diálogo de Preferencias con la pseudotraducción y exige que
la página no deje ningún texto visible sin envolver.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ytchat.ai import catalogo
from ytchat.ui import gui, gui_preferencias
from ytchat.ui import preferencias_ia
from ytchat.ui import preferencias_ia_clave
from ytchat.voice import motores
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.rutas_temporales import redirigir_rutas
from tests.ventanas_prueba import destruir


# Textos que arma otro módulo y aparecen en la parte recorrida: no se
# tocan acá. Los nombres salen de `ytchat/ai/proveedores.py`.
PENDIENTES_OTROS_MODULOS = (
    "Google Gemini",
    "OpenAI",
    "Anthropic",
    "OpenRouter",
    "OpenCode Go",
    "Command Code",
    "Otro compatible con OpenAI",
)


class TestPseudoIA(unittest.TestCase):
    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        parche = redirigir_rutas(Path(self.tmp.name))
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

    def _dialogo(self):
        with mock.patch.object(motores, "listar_voces",
                               return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(None, {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._dialogo()
            pagina = next(p for p in dialogo._paginas()
                          if p.GetName() == "PagIA")
            sin_marcar = textos_sin_marcar(
                pagina, propios=PENDIENTES_OTROS_MODULOS)

        self.assertEqual([], sin_marcar)

    def test_restaurar_marca_la_instruccion(self):
        with con_pseudo():
            dialogo = self._dialogo()
            dialogo.pagina_ia._on_ia_restaurar(mock.Mock())
            valor = dialogo.pagina_ia.txt_ia_pregunta.GetValue()
        self.assertTrue(valor.startswith("[¡"), valor)


if __name__ == "__main__":
    unittest.main()
