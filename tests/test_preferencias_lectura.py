"""Pruebas de la página Lectura y de su guardado.

Abren ventanas: las corre el advisor en la otra PC, no se corren acá. La
primera mata la mutación que devuelve siempre el mismo formato desde
`PaginaLectura.cambios()`; la segunda comprueba el cableado hasta el
archivo, que guardar escribe en `[lectura] formato_prefijo` lo elegido.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ytchat.core import config
from ytchat.ui import gui, gui_preferencias
from ytchat.ui.preferencias_lectura import PaginaLectura
from ytchat.voice import motores
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.rutas_temporales import redirigir_rutas
from tests.ventanas_prueba import destruir


# Valores literales, no leídos de la página: así protegen el orden en vez
# de repetirlo. Van en el mismo orden que las opciones del control.
FORMATOS_ESPERADOS = (
    "nombre_mensaje",
    "mensaje_nombre",
    "solo_mensaje",
    "solo_nombre",
)


class TestCambiosDeLectura(unittest.TestCase):
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

    def test_cambios_devuelve_el_formato_elegido(self):
        dialogo = self._dialogo()
        pagina = dialogo.pagina_lectura
        self.assertIsInstance(pagina, PaginaLectura)
        self.assertEqual(pagina.rb_formato.GetCount(), 4)
        for indice, esperado in enumerate(FORMATOS_ESPERADOS):
            with self.subTest(formato=esperado):
                dialogo.rb_formato.SetSelection(indice)
                self.assertEqual(pagina.cambios(),
                                 [("lectura", "formato_prefijo", esperado)])

    def test_guardar_escribe_el_formato_elegido(self):
        dialogo = self._dialogo()
        dialogo.rb_formato.SetSelection(1)
        with mock.patch.object(gui_preferencias._snd, "reproducir"), \
                mock.patch.object(gui_preferencias, "anunciar"), \
                mock.patch.object(dialogo, "EndModal"):
            dialogo._on_guardar(None)
        self.assertEqual(dialogo._config.get("formato_prefijo"),
                         "mensaje_nombre")
        parser = config._mk_parser()
        parser.read(self.ruta / "config.ini", encoding="utf-8")
        self.assertEqual(parser.get("lectura", "formato_prefijo"),
                         "mensaje_nombre")

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._dialogo()
            pagina = dialogo.rb_formato.GetParent()
            sin_marcar = textos_sin_marcar(
                pagina, propios=("YouTube", "TikTok"))

        self.assertEqual([], sin_marcar)


if __name__ == "__main__":
    unittest.main()
