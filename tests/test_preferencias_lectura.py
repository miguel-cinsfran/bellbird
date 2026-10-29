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

from bellbird.core import config
from bellbird.ui import gui, gui_preferencias
from bellbird.ui.preferencias_lectura import PaginaLectura
from bellbird.voice import motores
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


AVISOS_ESPERADOS = (
    ("cho_aviso_entradas", "tiktok_aviso_entradas", "Entradas al directo"),
    ("cho_aviso_me_gusta", "tiktok_aviso_me_gusta", "Me gusta"),
    ("cho_aviso_seguidores", "tiktok_aviso_seguidores", "Seguidores nuevos"),
    ("cho_aviso_compartidos", "tiktok_aviso_compartidos", "Directo compartido"),
    ("cho_aviso_cofres", "tiktok_aviso_cofres", "Cofres"),
)


class TestAvisosTiktok(unittest.TestCase):
    """Los cinco avisos de TikTok: lista con nombre accesible y valor.

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

    def test_las_cinco_listas_tienen_su_nombre_y_su_valor(self):
        dialogo = self._dialogo({"tiktok_aviso_entradas": "ocultar",
                                 "tiktok_aviso_cofres": "mostrar"})
        esperados = {"cho_aviso_entradas": ("Entradas al directo", "ocultar"),
                     "cho_aviso_me_gusta": ("Me gusta", "mostrar"),
                     "cho_aviso_seguidores": ("Seguidores nuevos", "leer"),
                     "cho_aviso_compartidos": ("Directo compartido", "leer"),
                     "cho_aviso_cofres": ("Cofres", "mostrar")}
        for atributo, en_memoria, nombre in AVISOS_ESPERADOS:
            with self.subTest(atributo=atributo):
                control = getattr(dialogo, atributo)
                self.assertEqual(control.GetName(), nombre)
                self.assertEqual(control.GetValue(), esperados[atributo][1])

    def test_guardar_escribe_la_clave_del_ini(self):
        dialogo = self._dialogo()
        dialogo.cho_aviso_cofres.SetValue("ocultar")
        with mock.patch.object(gui_preferencias._snd, "reproducir"), \
                mock.patch.object(gui_preferencias, "anunciar"), \
                mock.patch.object(dialogo, "EndModal"):
            dialogo._on_guardar(None)
        self.assertEqual(dialogo._config.get("tiktok_aviso_cofres"), "ocultar")
        parser = config._mk_parser()
        parser.read(self.ruta / "config.ini", encoding="utf-8")
        self.assertEqual(parser.get("tiktok", "aviso_cofres"), "ocultar")


class TestAvisosEnGrupo(unittest.TestCase):
    """Los cinco avisos de TikTok van en un recuadro con su título.

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

    def _caja_de_avisos(self, dialogo):
        pagina = next(p for p in dialogo._paginas()
                      if p.GetName() == "PagLectura")
        pendientes = [pagina]
        while pendientes:
            actual = pendientes.pop()
            if (isinstance(actual, gui.wx.StaticBox)
                    and actual.GetLabel() == "Avisos de TikTok"):
                return actual
            pendientes.extend(actual.GetChildren())
        self.fail("sin recuadro de Avisos de TikTok")

    def test_los_cinco_combinados_tienen_como_padre_la_caja(self):
        dialogo = self._dialogo()
        caja = self._caja_de_avisos(dialogo)
        for atributo, _en_memoria, _nombre in AVISOS_ESPERADOS:
            with self.subTest(atributo=atributo):
                self.assertIs(getattr(dialogo, atributo).GetParent(), caja)

    def test_la_caja_ordena_en_dos_columnas(self):
        dialogo = self._dialogo()
        caja = self._caja_de_avisos(dialogo)
        pagina = next(p for p in dialogo._paginas()
                      if p.GetName() == "PagLectura")
        cajas = [it.GetSizer() for it in pagina.GetSizer().GetChildren()
                 if isinstance(it.GetSizer(), gui.wx.StaticBoxSizer)]
        box = next(b for b in cajas if b.GetStaticBox() is caja)
        grillas = [it.GetSizer() for it in box.GetChildren()
                   if isinstance(it.GetSizer(), gui.wx.FlexGridSizer)]
        self.assertEqual(len(grillas), 1)
        self.assertEqual(grillas[0].GetCols(), 2)


if __name__ == "__main__":
    unittest.main()
