"""Pruebas de la paleta compartida y de su uso en las ventanas.

Crean diálogos de verdad: abren ventanas.
"""

import pathlib
import re
import unittest
from unittest import mock

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False

from bellbird.ui import paleta
from bellbird.ui import tema
from bellbird.ui.tema import _T
from tests.ventanas_prueba import destruir


def _relacion(color_a, color_b) -> float:
    """Contraste WCAG entre dos wx.Colour, como en `overlay_datos`."""
    def luminancia(color):
        valores = [v / 255 for v in (color.Red(), color.Green(), color.Blue())]
        lineales = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
                    for v in valores]
        return 0.2126 * lineales[0] + 0.7152 * lineales[1] + 0.0722 * lineales[2]
    una, otra = luminancia(color_a), luminancia(color_b)
    return (max(una, otra) + 0.05) / (min(una, otra) + 0.05)


class TestColores(unittest.TestCase):
    def test_valores_nuevos(self):
        self.assertEqual((_T.field.Red(), _T.field.Green(), _T.field.Blue()),
                         (255, 255, 255))
        self.assertEqual((_T.accent.Red(), _T.accent.Green(), _T.accent.Blue()),
                         (0x33, 0x70, 0x4A))
        self.assertEqual((_T.primary.Red(), _T.primary.Green(), _T.primary.Blue()),
                         (0x33, 0x70, 0x4A))
        self.assertEqual((_T.primary_t.Red(), _T.primary_t.Green(),
                          _T.primary_t.Blue()), (255, 255, 255))

    def test_contraste_de_cada_par(self):
        for texto in (_T.text, _T.dim, _T.accent, _T.red):
            for fondo in (_T.bg, _T.surface, _T.field):
                with self.subTest(texto=texto, fondo=fondo):
                    self.assertGreaterEqual(_relacion(texto, fondo), 4.5)
        self.assertGreaterEqual(_relacion(_T.primary_t, _T.primary), 4.5)
        self.assertGreaterEqual(_relacion(_T.btn_t, _T.btn), 4.5)

    def test_boton_principal_usa_primary(self):
        control = mock.Mock()
        with mock.patch.object(tema, "ALTO_CONTRASTE", False):
            tema.boton_principal(control)
        control.SetBackgroundColour.assert_called_once_with(_T.primary)
        control.SetForegroundColour.assert_called_once_with(_T.primary_t)

    def test_boton_principal_respeta_alto_contraste(self):
        control = mock.Mock()
        with mock.patch.object(tema, "ALTO_CONTRASTE", True):
            tema.boton_principal(control)
        control.SetBackgroundColour.assert_not_called()
        control.SetForegroundColour.assert_not_called()


def _hilo_directo(target, nombre, **kwargs):
    args = kwargs.get("args", ())
    target(*args)
    hilo = mock.Mock()
    hilo.start.return_value = None
    return hilo


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPintarVentana(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _dialogo(self):
        dialogo = wx.Dialog(None, title="Prueba", name="DialogoPrueba")
        self.panel = wx.Panel(dialogo, name="Panel")
        self.campo = wx.TextCtrl(self.panel, value="x", name="Campo")
        self.lista = wx.ListBox(self.panel, choices=["a"], name="Lista")
        self.boton = wx.Button(self.panel, label="&Ir", name="Ir")
        self.casilla = wx.CheckBox(self.panel, label="&Marcar",
                                   name="Marcar")
        self.mapa = wx.StaticBitmap(self.panel, bitmap=wx.NullBitmap,
                                    name="Mapa")
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_pinta_cada_clase_con_su_color(self):
        dialogo = self._dialogo()
        fondo_mapa_antes = self.mapa.GetBackgroundColour()
        paleta.pintar_ventana(dialogo)
        self.assertEqual(dialogo.GetBackgroundColour(), _T.bg)
        self.assertEqual(self.panel.GetBackgroundColour(), _T.bg)
        self.assertEqual(self.panel.GetForegroundColour(), _T.text)
        self.assertEqual(self.campo.GetBackgroundColour(), _T.field)
        self.assertEqual(self.campo.GetForegroundColour(), _T.text)
        self.assertEqual(self.lista.GetBackgroundColour(), _T.field)
        self.assertEqual(self.lista.GetForegroundColour(), _T.text)
        self.assertEqual(self.boton.GetBackgroundColour(), _T.btn)
        self.assertEqual(self.boton.GetForegroundColour(), _T.btn_t)
        self.assertEqual(self.casilla.GetForegroundColour(), _T.text)
        self.assertEqual(self.mapa.GetBackgroundColour(),
                         fondo_mapa_antes)

    def test_con_alto_contraste_no_cambia_nada(self):
        dialogo = self._dialogo()
        antes = (dialogo.GetBackgroundColour(),
                 self.panel.GetBackgroundColour(),
                 self.campo.GetBackgroundColour(),
                 self.boton.GetBackgroundColour(),
                 self.casilla.GetForegroundColour())
        with mock.patch.object(paleta.tema, "ALTO_CONTRASTE", True):
            paleta.pintar_ventana(dialogo)
        despues = (dialogo.GetBackgroundColour(),
                   self.panel.GetBackgroundColour(),
                   self.campo.GetBackgroundColour(),
                   self.boton.GetBackgroundColour(),
                   self.casilla.GetForegroundColour())
        self.assertEqual(antes, despues)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestFondoActualizacion(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_fondo_es_el_de_la_principal(self):
        from bellbird.ui import gui_actualizacion as actualizacion
        dialogo = actualizacion.DialogoActualizacion(None, "Algo")
        self.addCleanup(destruir, dialogo)
        dialogo.Show()
        self.assertEqual(dialogo.GetBackgroundColour(), _T.bg)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestFondoElegirDestino(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_fondo_es_el_de_la_principal(self):
        from bellbird.ui import gui_elegir_destino as elegir
        dialogo = elegir.DialogoElegirDestino(None, destino="YouTube",
                                             usuario="")
        self.addCleanup(destruir, dialogo)
        self.assertEqual(dialogo.GetBackgroundColour(), _T.bg)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestFondoDirectoYoutube(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_fondo_es_el_de_la_principal(self):
        from bellbird.ui import gui_directo_youtube as directo
        dialogo = directo.DialogoDirectoYoutube(None)
        self.addCleanup(destruir, dialogo)
        self.assertEqual(dialogo.GetBackgroundColour(), _T.bg)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestFondoAgregarCaptura(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)
        from bellbird.ui import ia_agregar_captura as agregar
        parche_hilo = mock.patch.object(
            agregar.diagnostico, "crear_hilo", side_effect=_hilo_directo)
        parche_hilo.start()
        self.addCleanup(parche_hilo.stop)
        parche_llamada = mock.patch.object(
            agregar.wx, "CallAfter",
            side_effect=lambda funcion, *args, **kwargs: funcion(*args,
                                                                 **kwargs))
        parche_llamada.start()
        self.addCleanup(parche_llamada.stop)

    def test_fondo_es_el_de_la_principal(self):
        from bellbird.ui import ia_agregar_captura as agregar
        with mock.patch.object(agregar.obs_captura_ia, "opciones",
                               return_value=[]):
            dialogo = agregar.DialogoAgregarCaptura(None, mock.Mock())
        self.addCleanup(destruir, dialogo)
        self.assertEqual(dialogo.GetBackgroundColour(), _T.bg)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestFondoVentanaIA(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_mensaje_fondo_es_el_de_la_principal(self):
        from bellbird.ui import ia_ventana as ventana
        dialogo = ventana.DialogoMensaje(None, "hola")
        self.addCleanup(destruir, dialogo)
        self.assertEqual(dialogo.GetBackgroundColour(), _T.bg)

    def test_ventana_fondo_es_el_de_la_principal(self):
        from bellbird.ui import ia_ventana as ventana
        dialogo = ventana.VentanaIA(None)
        self.addCleanup(destruir, dialogo)
        self.assertEqual(dialogo.GetBackgroundColour(), _T.bg)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestFondoPreferencias(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _dialogo(self):
        from bellbird.ui import gui_preferencias as preferencias
        from bellbird.voice import motores
        with mock.patch.object(motores, "listar_voces",
                               return_value=["Voz de prueba"]):
            dialogo = preferencias.PreferenciasDialog(None, {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_fondo_es_el_de_la_principal(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo.GetBackgroundColour(), _T.bg)

    def test_casilla_con_texto_y_categorias_en_superficie(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo.chk_total_sc.GetForegroundColour(),
                         _T.text)
        self.assertEqual(dialogo.lista_categorias.GetBackgroundColour(),
                         _T.surface)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPintarVentanaPapeles(unittest.TestCase):
    """Lo pintado a mano con papel propio no lo pisa la paleta."""

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _dialogo(self):
        from bellbird.ui.tema import _pintar
        dialogo = wx.Dialog(None, title="Prueba", name="DialogoPapeles")
        self.panel = wx.Panel(dialogo, name="Panel")
        self.campo = wx.TextCtrl(self.panel, value="x", name="Campo")
        self.nota = wx.StaticText(self.panel, label="nota", name="Nota")
        _pintar(self.nota, fg=_T.dim)
        self.boton = wx.Button(self.panel, label="&Ir", name="Ir")
        _pintar(self.boton, _T.btn, _T.btn_t)
        self.boton.SetDefault()
        caja = wx.StaticBox(self.panel, label="Grupo", name="Grupo")
        self.titulo_grupo = caja
        self.hijo = wx.StaticText(caja, label="hijo", name="Hijo")
        self.fuente_hijo = self.hijo.GetFont()
        self.deslizador = wx.Slider(self.panel, name="Deslizador")
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_campo_sin_color_sale_con_field(self):
        dialogo = self._dialogo()
        paleta.pintar_ventana(dialogo)
        self.assertEqual(self.campo.GetBackgroundColour(), _T.field)
        self.assertEqual(self.campo.GetForegroundColour(), _T.text)

    def test_nota_en_dim_sigue_en_dim(self):
        dialogo = self._dialogo()
        paleta.pintar_ventana(dialogo)
        self.assertEqual(self.nota.GetForegroundColour(), _T.dim)

    def test_boton_por_defecto_sale_con_primary(self):
        dialogo = self._dialogo()
        paleta.pintar_ventana(dialogo)
        self.assertEqual(self.boton.GetBackgroundColour(), _T.primary)
        self.assertEqual(self.boton.GetForegroundColour(), _T.primary_t)

    def test_grupo_con_acento_y_sus_hijos_con_su_fuente(self):
        dialogo = self._dialogo()
        paleta.pintar_ventana(dialogo)
        self.assertEqual(self.titulo_grupo.GetForegroundColour(), _T.accent)
        self.assertTrue(self.titulo_grupo.GetFont().GetWeight() == wx.FONTWEIGHT_BOLD)
        self.assertEqual(self.hijo.GetFont(), self.fuente_hijo)

    def test_deslizador_con_fondo_del_padre(self):
        dialogo = self._dialogo()
        paleta.pintar_ventana(dialogo)
        self.assertEqual(self.deslizador.GetBackgroundColour(),
                         self.panel.GetBackgroundColour())

    def test_grupo_en_panel_pintado_sale_en_acento(self):
        from bellbird.ui.tema import _pintar
        dialogo = wx.Dialog(None, title="Prueba", name="DialogoGrupo")
        self.addCleanup(destruir, dialogo)
        panel = wx.Panel(dialogo, name="Panel")
        _pintar(panel, _T.bg, _T.text)
        caja = wx.StaticBox(panel, label="Grupo", name="Grupo")
        hijo = wx.StaticText(caja, label="hijo", name="Hijo")
        fuente_hijo = hijo.GetFont()
        paleta.pintar_ventana(dialogo)
        self.assertEqual(caja.GetForegroundColour(), _T.accent)
        self.assertTrue(caja.GetFont().GetWeight() == wx.FONTWEIGHT_BOLD)
        self.assertEqual(hijo.GetFont(), fuente_hijo)


class TestVentanasPintadas(unittest.TestCase):
    """Cada ventana sale pintada por el único camino: `pintar_ventana`."""

    _VENTANAS = (
        "bellbird/ui/gui.py",
        "bellbird/ui/gui_transmision.py",
        "bellbird/ui/gui_preferencias.py",
        "bellbird/ui/gui_descargas.py",
        "bellbird/ui/gui_microfono.py",
        "bellbird/ui/musica_editor_lista.py",
        "bellbird/ui/musica_ventana.py",
        "bellbird/ui/gui_historial.py",
        "bellbird/ui/elegir_formato.py",
        "bellbird/ui/gui_redactar.py",
        "bellbird/ui/musica_dialogo_enlace.py",
    )

    def _texto(self, relativo):
        raiz = pathlib.Path(__file__).resolve().parents[1]
        return (raiz / relativo).read_text(encoding="utf-8")

    def test_ventanas_llaman_a_pintar_ventana(self):
        for relativo in self._VENTANAS:
            with self.subTest(ventana=relativo):
                texto = self._texto(relativo)
                self.assertIn("pintar_ventana", texto)
                self.assertTrue(
                    re.search(r"pintar_ventana\s*\(\s*self\s*\)", texto))

    def test_transmitir_en_directo_es_secundario(self):
        texto = self._texto("bellbird/ui/boton_directo.py")
        self.assertIn("_T.btn", texto)
        self.assertNotIn("_T.primary", texto)

    def test_buscar_de_descargas_es_principal(self):
        texto = self._texto("bellbird/ui/descargas_buscador.py")
        self.assertIn("boton_principal", texto)


if __name__ == "__main__":
    unittest.main()
