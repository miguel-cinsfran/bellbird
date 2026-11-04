"""Pruebas del cuadro de diseños de escena, sin conectar con OBS."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import wx

from bellbird.core import idioma
from bellbird.obs import disenos_escena, disenos_fabrica, disenos_guardados
from bellbird.obs.fuente_chat import NOMBRE_FUENTE
from bellbird.ui import escena_disenos
from tests.rutas_temporales import redirigir_rutas
from tests.ventanas_prueba import destruir


def _fuentes():
    return [
        disenos_escena.Fuente("Juego", "otra", 1600, 900),
        disenos_escena.Fuente("Cámara", "camara", 1280, 720),
        disenos_escena.Fuente(NOMBRE_FUENTE, "chat", 460, 620),
    ]


class DisenoEscenaDialogTest(unittest.TestCase):

    def setUp(self):
        idioma.instalar("es")
        self.addCleanup(idioma._reiniciar)
        self.app = wx.App.Get() or wx.App(False)
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        parche = redirigir_rutas(Path(self.temporal.name))
        parche.__enter__()
        self.addCleanup(parche.__exit__, None, None, None)
        self.anuncios = []
        aviso = mock.patch.object(
            escena_disenos, "anunciar",
            lambda texto, *args, **kwargs: self.anuncios.append(texto))
        aviso.start()
        self.addCleanup(aviso.stop)

    def _dialogo(self, guardados=None):
        dialogo = escena_disenos.DisenoEscenaDialog(
            None, _fuentes(), guardados or [])
        self.addCleanup(destruir, dialogo)
        return dialogo

    def _elegir(self, dialogo, indice):
        dialogo.cho_diseno.SetSelection(indice)
        evento = wx.CommandEvent(
            wx.EVT_CHOICE.typeId, dialogo.cho_diseno.GetId())
        dialogo.cho_diseno.GetEventHandler().ProcessEvent(evento)
        wx.SafeYield()

    def _cambiar_chat(self, dialogo, indice):
        dialogo.cho_chat.SetSelection(indice)
        evento = wx.CommandEvent(wx.EVT_CHOICE.typeId, dialogo.cho_chat.GetId())
        dialogo.cho_chat.GetEventHandler().ProcessEvent(evento)
        wx.SafeYield()

    def test_elegir_cada_clase_muestra_solo_sus_controles(self):
        dialogo = self._dialogo()
        self._elegir(dialogo, 0)
        self.assertTrue(dialogo.cho_principal.IsShown())
        self.assertTrue(dialogo.cho_ajuste_principal.IsShown())
        self.assertTrue(dialogo.cho_secundaria.IsShown())
        self.assertTrue(dialogo.cho_ajuste_secundaria.IsShown())
        self.assertFalse(dialogo.cho_izquierda.IsShown())
        self.assertFalse(dialogo.cho_derecha.IsShown())
        self.assertTrue(dialogo.cho_esquina.IsShown())
        self.assertTrue(dialogo.cho_tamano.IsShown())
        self.assertFalse(dialogo.cho_reparto.IsShown())

        self._elegir(dialogo, 2)
        self.assertTrue(dialogo.cho_principal.IsShown())
        self.assertFalse(dialogo.cho_secundaria.IsShown())
        self.assertFalse(dialogo.cho_izquierda.IsShown())
        self.assertFalse(dialogo.cho_derecha.IsShown())
        self.assertFalse(dialogo.cho_esquina.IsShown())
        self.assertFalse(dialogo.cho_tamano.IsShown())
        self.assertFalse(dialogo.cho_reparto.IsShown())

        self._elegir(dialogo, 4)
        self.assertFalse(dialogo.cho_principal.IsShown())
        self.assertFalse(dialogo.cho_secundaria.IsShown())
        self.assertTrue(dialogo.cho_izquierda.IsShown())
        self.assertTrue(dialogo.cho_derecha.IsShown())
        self.assertFalse(dialogo.cho_esquina.IsShown())
        self.assertFalse(dialogo.cho_tamano.IsShown())
        self.assertTrue(dialogo.cho_reparto.IsShown())

    def test_el_chat_encima_muestra_su_esquina(self):
        dialogo = self._dialogo()
        self._elegir(dialogo, 2)
        self.assertFalse(dialogo.cho_esquina_chat.IsShown())
        self._cambiar_chat(dialogo, 1)
        self.assertTrue(dialogo.cho_esquina_chat.IsShown())

    def test_al_elegir_completa_los_lugares_con_las_fuentes(self):
        dialogo = self._dialogo()
        self._elegir(dialogo, 0)
        self.assertEqual(dialogo.cho_principal.GetStringSelection(), "Juego")
        self.assertEqual(dialogo.cho_secundaria.GetStringSelection(), "Cámara")
        self.assertNotIn(NOMBRE_FUENTE, dialogo.cho_principal.GetStrings())

    def test_los_controles_ajustan_el_diseno(self):
        dialogo = self._dialogo()
        self._elegir(dialogo, 0)
        dialogo.cho_principal.SetStringSelection("Cámara")
        dialogo.cho_secundaria.SetStringSelection("Juego")
        dialogo.cho_ajuste_principal.SetSelection(2)
        dialogo.cho_ajuste_secundaria.SetSelection(1)
        dialogo.cho_esquina.SetSelection(0)
        dialogo.cho_tamano.SetSelection(2)
        dialogo.cho_chat.SetSelection(1)
        dialogo.cho_esquina_chat.SetSelection(1)
        diseno = dialogo._diseno_actual()
        self.assertEqual((diseno.principal, diseno.secundaria),
                         ("Cámara", "Juego"))
        self.assertEqual(diseno.modos,
                         {"Cámara": "llenar", "Juego": "ajustar"})
        self.assertEqual((diseno.esquina, diseno.tamano),
                         ("superior-izquierda", "grande"))
        self.assertEqual((diseno.chat, diseno.esquina_chat),
                         ("superpuesto", "superior-derecha"))
        self._elegir(dialogo, 4)
        dialogo.cho_reparto.SetSelection(1)
        self.assertEqual(dialogo._diseno_actual().proporcion, "dos_tercios")

    def test_aceptar_devuelve_el_nombre_y_el_diseno_completo(self):
        dialogo = self._dialogo()
        self._elegir(dialogo, 0)
        dialogo.EndModal = mock.Mock()
        dialogo._al_aplicar(None)
        nombre, diseno = dialogo.diseno_elegido()
        self.assertEqual(nombre, disenos_fabrica.FABRICA[0].nombre)
        self.assertEqual((diseno.principal, diseno.secundaria),
                         ("Juego", "Cámara"))
        dialogo.EndModal.assert_called_once_with(wx.ID_OK)

    def test_aceptar_con_una_fuente_repetida_no_cierra_y_enfoca_la_segunda(self):
        dialogo = self._dialogo()
        self._elegir(dialogo, 4)
        dialogo.cho_izquierda.SetStringSelection("Juego")
        dialogo.cho_derecha.SetStringSelection("Juego")
        dialogo.EndModal = mock.Mock()
        with mock.patch.object(dialogo.cho_derecha, "SetFocus") as foco:
            dialogo._al_aplicar(None)
        dialogo.EndModal.assert_not_called()
        foco.assert_called_once_with()
        self.assertIn("Juego está en dos lugares. Elige otra.", self.anuncios)
        self.assertIsNone(dialogo.diseno_elegido())

    def test_guardar_y_eliminar_un_diseno_guardado(self):
        dialogo = self._dialogo()
        self._elegir(dialogo, 0)
        with mock.patch.object(escena_disenos, "_pedir_nombre",
                               return_value="Mi diseño"):
            dialogo._al_guardar(None)
        cargados = disenos_guardados.cargar()
        self.assertEqual([nombre for nombre, _diseno in cargados],
                         ["Mi diseño"])
        self.assertEqual(dialogo.cho_diseno.GetStringSelection(), "Mi diseño")
        self.assertIn("Diseño guardado: Mi diseño", self.anuncios)
        dialogo._al_eliminar(None)
        self.assertEqual(disenos_guardados.cargar(), [])
        self.assertEqual(dialogo.cho_diseno.GetStringSelection(),
                         disenos_fabrica.FABRICA[0].nombre)
        self.assertIn("Diseño eliminado: Mi diseño", self.anuncios)

    def test_un_nombre_de_fabrica_no_se_guarda(self):
        dialogo = self._dialogo()
        self._elegir(dialogo, 0)
        with mock.patch.object(
                escena_disenos, "_pedir_nombre",
                return_value=disenos_fabrica.FABRICA[2].nombre):
            dialogo._al_guardar(None)
        self.assertEqual(disenos_guardados.cargar(), [])
        self.assertIn("Ese nombre es de un diseño de fábrica. Elige otro.",
                      self.anuncios)

    def test_los_disenos_de_fabrica_no_se_eliminan(self):
        dialogo = self._dialogo()
        self._elegir(dialogo, 0)
        dialogo._al_eliminar(None)
        self.assertIn("Los diseños de fábrica no se eliminan.", self.anuncios)

    def test_nombres_accesibles(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo.cho_diseno.GetName(), "Diseño")
        self.assertEqual(dialogo.cho_principal.GetName(), "Fuente principal")
        self.assertEqual(dialogo.cho_secundaria.GetName(),
                         "Fuente en la esquina")
        self.assertEqual(dialogo.cho_izquierda.GetName(),
                         "Fuente a la izquierda")
        self.assertEqual(dialogo.cho_derecha.GetName(), "Fuente a la derecha")
        self.assertEqual(dialogo.cho_ajuste_principal.GetName(),
                         "Ajuste de la fuente principal")
        self.assertEqual(dialogo.cho_ajuste_secundaria.GetName(),
                         "Ajuste de la fuente en la esquina")
        self.assertEqual(dialogo.cho_ajuste_izquierda.GetName(),
                         "Ajuste de la fuente a la izquierda")
        self.assertEqual(dialogo.cho_ajuste_derecha.GetName(),
                         "Ajuste de la fuente a la derecha")
        self.assertEqual(dialogo.cho_esquina.GetName(), "Esquina")
        self.assertEqual(dialogo.cho_tamano.GetName(), "Tamaño")
        self.assertEqual(dialogo.cho_reparto.GetName(), "Reparto")
        self.assertEqual(dialogo.cho_chat.GetName(), "Chat")
        self.assertEqual(dialogo.cho_esquina_chat.GetName(), "Esquina del chat")
        self.assertEqual(dialogo.btn_aplicar.GetName(), "Aceptar")
        self.assertEqual(dialogo.btn_guardar.GetName(), "Guardar como…")
        self.assertEqual(dialogo.btn_eliminar.GetName(), "Eliminar")
        self.assertEqual(dialogo.btn_cancelar.GetName(), "Cancelar")


if __name__ == "__main__":
    unittest.main()
