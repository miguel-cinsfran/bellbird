"""Pruebas de la ventana genérica de actualización.

Crea diálogos reales sin llamar a `Show()` ni a `ShowModal()`, así que no
abre nada en pantalla y se corre en esta máquina.
"""

import unittest
from unittest import mock

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False

from ytchat.ui import gui_actualizacion as actualizacion
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import destruir


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestDialogoActualizacion(unittest.TestCase):

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _dialogo(self, titulo="Actualizar algo"):
        dialogo = actualizacion.DialogoActualizacion(None, titulo)
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_nombres_accesibles_y_cerrar(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo.GetName(), "DialogoActualizacion")
        self.assertEqual(dialogo.txt_estado.GetName(), "Estado")
        self.assertEqual(dialogo.gauge.GetName(), "Progreso")
        self.assertEqual(dialogo.txt_notas.GetName(), "Novedades")
        self.assertEqual(dialogo.btn_cerrar.GetLabel(), "&Cerrar")
        self.assertEqual(dialogo.btn_cerrar.GetId(), wx.ID_CANCEL)

    def test_estado_en_una_linea_con_ancho_minimo(self):
        dialogo = self._dialogo()
        self.assertGreaterEqual(dialogo.GetSize().width, 380)
        self.assertGreaterEqual(
            dialogo.txt_estado.GetMinSize().width, 380)
        estilo = dialogo.txt_estado.GetWindowStyleFlag()
        self.assertTrue(estilo & wx.TE_NO_VSCROLL)

    def test_orden_de_tab(self):
        dialogo = self._dialogo()
        self.assertEqual(
            list(dialogo.GetChildren()),
            [dialogo.txt_estado, dialogo.gauge, dialogo.txt_notas,
             dialogo.btn_accion, dialogo.btn_cerrar])

    def test_estado_escribe_y_anuncia(self):
        dialogo = self._dialogo()
        with mock.patch.object(actualizacion, "anunciar") as anunciar:
            dialogo.estado("Buscando la última versión.")
        self.assertEqual(dialogo.txt_estado.GetValue(),
                         "Buscando la última versión.")
        anunciar.assert_called_once_with("Buscando la última versión.")

    def test_progreso_por_valor_y_por_pulso(self):
        dialogo = self._dialogo()
        dialogo.progreso(40)
        self.assertEqual(dialogo.gauge.GetValue(), 40)
        with mock.patch.object(dialogo.gauge, "Pulse") as pulso:
            dialogo.progreso(None)
        pulso.assert_called_once_with()

    def test_notas_muestra_y_oculta(self):
        dialogo = self._dialogo()
        self.assertFalse(dialogo.txt_notas.IsShown())
        dialogo.notas("Novedades de la versión")
        self.assertTrue(dialogo.txt_notas.IsShown())
        self.assertEqual(dialogo.txt_notas.GetValue(),
                         "Novedades de la versión")
        dialogo.notas("")
        self.assertFalse(dialogo.txt_notas.IsShown())
        self.assertEqual(dialogo.txt_notas.GetValue(), "")

    def test_ofrecer_accion_muestra_y_su_manejador_ejecuta(self):
        dialogo = self._dialogo()
        self.assertFalse(dialogo.btn_accion.IsShown())
        llamada = mock.Mock()
        dialogo.ofrecer_accion("&Reintentar", llamada)
        self.assertTrue(dialogo.btn_accion.IsShown())
        self.assertEqual(dialogo.btn_accion.GetLabel(), "&Reintentar")
        evento = wx.CommandEvent(wx.wxEVT_BUTTON,
                                 dialogo.btn_accion.GetId())
        dialogo.btn_accion.GetEventHandler().ProcessEvent(evento)
        llamada.assert_called_once_with()
        dialogo.quitar_accion()
        self.assertFalse(dialogo.btn_accion.IsShown())

    def test_cerrar_marca_cerrado_y_cancelado(self):
        dialogo = self._dialogo()
        self.assertFalse(dialogo.cerrado)
        self.assertFalse(dialogo.cancelado.is_set())
        dialogo._al_cerrar(mock.Mock())
        self.assertTrue(dialogo.cerrado)
        self.assertTrue(dialogo.cancelado.is_set())

    def test_en_hilo_principal_no_ejecuta_despues_del_cierre(self):
        dialogo = self._dialogo()
        with mock.patch.object(actualizacion.wx, "CallAfter",
                               side_effect=lambda fn: fn()):
            llamada = mock.Mock()
            dialogo.en_hilo_principal(llamada, "a", "b")
            llamada.assert_called_once_with("a", "b")
            dialogo._al_cerrar(mock.Mock())
            llamada.reset_mock()
            dialogo.en_hilo_principal(llamada)
            llamada.assert_not_called()

    def test_la_ventana_no_conoce_ytdlp(self):
        with open(actualizacion.__file__, encoding="utf-8") as archivo:
            fuente = archivo.read()
        self.assertNotIn("ytdlp", fuente)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoVentanaPropia(unittest.TestCase):
    # Pseudotraducción de los textos propios: la corre el advisor.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        titulo = "Título de ejemplo"
        with con_pseudo():
            dialogo = actualizacion.DialogoActualizacion(None, titulo)
            self.addCleanup(destruir, dialogo)
            sin_marcar = textos_sin_marcar(dialogo, propios=(titulo,))
        self.assertEqual([], sin_marcar)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestReajuste(unittest.TestCase):
    """Reajuste a su contenido: abren ventanas, las corre el advisor."""

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _dialogo(self, titulo="Actualizar algo"):
        dialogo = actualizacion.DialogoActualizacion(None, titulo)
        self.addCleanup(destruir, dialogo)
        return dialogo

    def _visibles_con_alto_y_dentro(self, dialogo):
        area = dialogo.GetClientSize()
        for control in (dialogo.txt_estado, dialogo.gauge,
                        dialogo.txt_notas, dialogo.btn_accion,
                        dialogo.btn_cerrar):
            with self.subTest(control=control.GetName() or control.GetLabel()):
                if not control.IsShown():
                    continue
                self.assertGreater(control.GetSize().GetHeight(), 0)
                pos = control.GetPosition()
                tam = control.GetSize()
                self.assertGreaterEqual(pos.x, 0)
                self.assertGreaterEqual(pos.y, 0)
                self.assertLessEqual(pos.x + tam.width, area.width)
                self.assertLessEqual(pos.y + tam.height, area.height)

    def _orden_tab(self, dialogo):
        self.assertEqual(
            list(dialogo.GetChildren()),
            [dialogo.txt_estado, dialogo.gauge, dialogo.txt_notas,
             dialogo.btn_accion, dialogo.btn_cerrar])

    def test_notas_y_accion_reajustan_y_caben(self):
        dialogo = self._dialogo()
        dialogo.notas("Una novedad larga. " * 20)
        dialogo.ofrecer_accion("&Descargar e instalar", lambda: None)
        dialogo.Layout()
        self._visibles_con_alto_y_dentro(dialogo)
        self._orden_tab(dialogo)

    def test_quitar_accion_y_mas_tarde_reajustan_y_caben(self):
        dialogo = self._dialogo()
        dialogo.notas("Una novedad larga. " * 20)
        dialogo.ofrecer_accion("&Descargar e instalar", lambda: None)
        dialogo.quitar_accion()
        dialogo.etiqueta_cerrar("&Más tarde")
        dialogo.Layout()
        self._visibles_con_alto_y_dentro(dialogo)
        self._orden_tab(dialogo)

    def test_botones_en_una_misma_fila_y_redimensionable(self):
        dialogo = self._dialogo()
        dialogo.notas("Una novedad larga. " * 20)
        dialogo.ofrecer_accion("&Descargar e instalar", lambda: None)
        dialogo.Layout()
        self.assertTrue(dialogo.GetWindowStyleFlag() & wx.RESIZE_BORDER)
        self.assertEqual(dialogo.btn_accion.GetPosition().y,
                         dialogo.btn_cerrar.GetPosition().y)
        self.assertLess(dialogo.btn_accion.GetPosition().x,
                        dialogo.btn_cerrar.GetPosition().x)


if __name__ == "__main__":
    unittest.main()
