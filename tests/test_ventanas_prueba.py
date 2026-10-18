"""Guardiana: ninguna prueba deja ventanas de primer nivel pendientes.

Crea y destruye con `destruir` 60 `PreferenciasDialog` y exige que la
cuenta de objetos USER del proceso no crezca (medido: sin `SafeYield`
cada diálogo dejaba unos 235 ocupados hasta cortar Windows en 10.000).
Abren ventanas: las corre el advisor, no se corren acá.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

try:
    import wx
    from ytchat.ui import gui_preferencias
    from ytchat.voice import motores
    _HAY_WX = True
except Exception:
    _HAY_WX = False

from tests.rutas_temporales import redirigir_rutas
from tests.ventanas_prueba import destruir

_SOLO_WINDOWS = _HAY_WX and sys.platform == "win32"


def _objetos_usuario():
    """Objetos USER del proceso actual (`GetGuiResources`, bandera 1)."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32")
    user32.GetGuiResources.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    user32.GetGuiResources.restype = wintypes.DWORD
    return user32.GetGuiResources(-1, 1)


@unittest.skipUnless(_SOLO_WINDOWS, "solo Windows con wxPython")
class TestVentanasSinFugas(unittest.TestCase):

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)
        self.ruta = Path.cwd()
        self.parche_ruta = redirigir_rutas(self.ruta)
        self.parche_ruta.__enter__()
        self.addCleanup(self.parche_ruta.__exit__, None, None, None)

    def _dialogo(self):
        return gui_preferencias.PreferenciasDialog(None, {})

    def test_sesenta_dialogos_no_acumulan_objetos_de_ventana(self):
        with mock.patch.object(motores, "listar_voces",
                               return_value=["Voz de prueba"]):
            destruir(self._dialogo())
            base = _objetos_usuario()
            for _ in range(59):
                destruir(self._dialogo())
            final = _objetos_usuario()
        self.assertLessEqual(final, base + 300)

    def test_ningun_dialogo_queda_vivo(self):
        with mock.patch.object(motores, "listar_voces",
                               return_value=["Voz de prueba"]):
            for _ in range(60):
                destruir(self._dialogo())
        vivos = [ventana for ventana in wx.GetTopLevelWindows()
                 if isinstance(ventana, gui_preferencias.PreferenciasDialog)]
        self.assertEqual(vivos, [])


if __name__ == "__main__":
    unittest.main()
