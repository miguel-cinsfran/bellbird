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


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestDialogoActualizacion(unittest.TestCase):

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _dialogo(self, titulo="Actualizar algo"):
        dialogo = actualizacion.DialogoActualizacion(None, titulo)
        self.addCleanup(self._destruir, dialogo)
        return dialogo

    @staticmethod
    def _destruir(dialogo):
        try:
            dialogo.Destroy()
        except Exception:
            pass

    def test_nombres_accesibles_y_cerrar(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo.GetName(), "DialogoActualizacion")
        self.assertEqual(dialogo.txt_estado.GetName(), "Estado")
        self.assertEqual(dialogo.gauge.GetName(), "Progreso")
        self.assertEqual(dialogo.txt_notas.GetName(), "Novedades")
        self.assertEqual(dialogo.btn_cerrar.GetLabel(), "&Cerrar")
        self.assertEqual(dialogo.btn_cerrar.GetId(), wx.ID_CANCEL)

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


if __name__ == "__main__":
    unittest.main()
