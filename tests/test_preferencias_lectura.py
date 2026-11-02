"""Pruebas de la página Lectura y de su guardado.

Abren ventanas. La
primera mata la mutación que devuelve siempre el mismo formato desde
`PaginaLectura.cambios()`; la segunda comprueba el cableado hasta el
archivo, que guardar escribe en `[lectura] formato_prefijo` lo elegido.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bellbird.core import avisos_tiktok
from bellbird.core import config
from bellbird.ui import gui, gui_preferencias
from bellbird.ui import preferencias_transmision
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
                mock.patch.object(preferencias_transmision, "anunciar"), \
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


class TestDisenoFormato(unittest.TestCase):
    """El grupo de formato lleva su título en el recuadro, sin etiqueta suelta.

    Abren ventanas.
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

    def test_el_grupo_lleva_el_titulo_y_no_hay_etiqueta_suelta(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo.rb_formato.GetLabel(),
                         "Qué leer de cada mensaje")
        textos = []
        pendientes = [dialogo.rb_formato.GetParent()]
        while pendientes:
            actual = pendientes.pop()
            if isinstance(actual, gui.wx.StaticText):
                textos.append(actual.GetLabel())
            pendientes.extend(actual.GetChildren())
        self.assertNotIn("Qué leer de cada mensaje:", textos)


EVENTOS_ESPERADOS = (
    ("cho_evento_superchat", "evento_superchat", "&Super Chats y regalos:",
     "Super Chats y regalos"),
    ("cho_evento_miembro", "evento_miembro", "&Membresías:", "Membresías"),
    ("cho_evento_entrada", "evento_entrada", "&Entradas al directo:",
     "Entradas al directo"),
    ("cho_evento_me_gusta", "evento_me_gusta", "Me g&usta:", "Me gusta"),
    ("cho_evento_seguir", "evento_seguir", "Seguidores nue&vos:",
     "Seguidores nuevos"),
    ("cho_evento_compartir", "evento_compartir", "&Directo compartido:",
     "Directo compartido"),
    ("cho_evento_cofre", "evento_cofre", "Co&fres:", "Cofres"),
)


def _letras_acceso(ventana):
    letras = []
    pendientes = [ventana]
    while pendientes:
        actual = pendientes.pop(0)
        if isinstance(actual, (gui.wx.StaticText, gui.wx.Button,
                               gui.wx.CheckBox, gui.wx.RadioButton)):
            etiqueta = actual.GetLabel()
            if "&" in etiqueta:
                letras.append(etiqueta.split("&", 1)[1][:1].lower())
        pendientes.extend(actual.GetChildren())
    return letras


class TestEventosDelDirecto(unittest.TestCase):
    """Una lista por evento con los cuatro modos y su nombre accesible.

    Abren ventanas.
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

    def test_las_siete_listas_tienen_su_nombre_y_su_valor(self):
        dialogo = self._dialogo({"evento_superchat": "ocultar",
                                 "evento_cofre": "secundaria"})
        esperados = {"evento_superchat": "ocultar",
                     "evento_miembro": "principal",
                     "evento_entrada": "mostrar",
                     "evento_me_gusta": "mostrar",
                     "evento_seguir": "principal",
                     "evento_compartir": "principal",
                     "evento_cofre": "secundaria"}
        for atributo, en_memoria, _etiqueta, nombre in EVENTOS_ESPERADOS:
            with self.subTest(atributo=atributo):
                control = getattr(dialogo, atributo)
                self.assertEqual(control.GetName(), nombre)
                self.assertEqual(control.GetValue(), esperados[en_memoria])

    def test_cada_lista_ofrece_los_cuatro_modos_en_orden(self):
        dialogo = self._dialogo()
        rotulos = [rotulo for _modo, rotulo in
                   avisos_tiktok.MODOS_EVENTO]
        for atributo, _en_memoria, _etiqueta, _nombre in EVENTOS_ESPERADOS:
            with self.subTest(atributo=atributo):
                control = getattr(dialogo, atributo)
                self.assertEqual(
                    [control.GetString(i) for i in range(control.GetCount())],
                    rotulos)

    def test_las_etiquetas_van_en_el_orden_pedido(self):
        dialogo = self._dialogo()
        pagina = next(p for p in dialogo._paginas()
                      if p.GetName() == "PagLectura")
        caja = self._caja_de_eventos(pagina)
        etiquetas = [h.GetLabel() for h in caja.GetChildren()
                     if isinstance(h, gui.wx.StaticText)]
        self.assertEqual(etiquetas,
                         [etiqueta for _a, _m, etiqueta, _n
                          in EVENTOS_ESPERADOS])

    def test_guardar_escribe_la_seccion_eventos(self):
        dialogo = self._dialogo()
        dialogo.cho_evento_superchat.SetValue("ocultar")
        dialogo.cho_evento_cofre.SetValue("secundaria")
        with mock.patch.object(gui_preferencias._snd, "reproducir"),                 mock.patch.object(preferencias_transmision, "anunciar"),                 mock.patch.object(dialogo, "EndModal"):
            dialogo._on_guardar(None)
        self.assertEqual(dialogo._config.get("evento_superchat"), "ocultar")
        self.assertEqual(dialogo._config.get("evento_cofre"), "secundaria")
        parser = config._mk_parser()
        parser.read(self.ruta / "config.ini", encoding="utf-8")
        self.assertEqual(parser.get("eventos", "superchat"), "ocultar")
        self.assertEqual(parser.get("eventos", "cofre"), "secundaria")

    def test_no_quedan_las_listas_viejas_de_tiktok(self):
        dialogo = self._dialogo()
        for viejo in ("cho_aviso_entradas", "cho_aviso_me_gusta",
                      "cho_aviso_seguidores", "cho_aviso_compartidos",
                      "cho_aviso_cofres"):
            with self.subTest(viejo=viejo):
                self.assertFalse(hasattr(dialogo, viejo))

    def _caja_de_eventos(self, pagina):
        pendientes = [pagina]
        while pendientes:
            actual = pendientes.pop(0)
            if (isinstance(actual, gui.wx.StaticBox)
                    and actual.GetLabel() == "Eventos del directo"):
                return actual
            pendientes.extend(actual.GetChildren())
        self.fail("sin recuadro de Eventos del directo")

    def test_los_eventos_van_en_un_grupo_de_dos_columnas(self):
        dialogo = self._dialogo()
        caja = self._caja_de_eventos(
            next(p for p in dialogo._paginas()
                 if p.GetName() == "PagLectura"))
        pagina = next(p for p in dialogo._paginas()
                      if p.GetName() == "PagLectura")
        cajas = [it.GetSizer() for it in pagina.GetSizer().GetChildren()
                 if isinstance(it.GetSizer(), gui.wx.StaticBoxSizer)]
        box = next(b for b in cajas if b.GetStaticBox() is caja)
        grillas = [it.GetSizer() for it in box.GetChildren()
                   if isinstance(it.GetSizer(), gui.wx.FlexGridSizer)]
        self.assertEqual(len(grillas), 1)
        self.assertEqual(grillas[0].GetCols(), 2)
        for _atributo, _en_memoria, _etiqueta, _nombre in EVENTOS_ESPERADOS:
            with self.subTest(atributo=_atributo):
                self.assertIs(getattr(dialogo, _atributo).GetParent(), caja)

    def test_los_mnemonicos_de_lectura_no_se_repiten(self):
        dialogo = self._dialogo()
        pagina = next(p for p in dialogo._paginas()
                      if p.GetName() == "PagLectura")
        letras = _letras_acceso(pagina)
        self.assertEqual(len(letras), len(set(letras)), letras)


if __name__ == "__main__":
    unittest.main()
