"""Pruebas del panel de OBS abierto en la pestaña Grabación, sin OBS."""

import threading
import unittest
from types import SimpleNamespace
from unittest import mock

import wx

from bellbird.obs import consultas_transmision
from bellbird.ui import control_grabacion
from bellbird.ui import gui_grabaciones
from bellbird.ui import gui_transmitir
from bellbird.ui import obs_ventana
from bellbird.ui import operaciones_obs
from tests.test_gui_transmision import GestorFalso, HiloInmediato
from tests.ventanas_prueba import app_de_prueba, destruir


class PrincipalFalsa:

    def __init__(self, grabar=False, preferido="Mic/Aux"):
        self._config = {"grabar_al_transmitir": grabar,
                        "obs_microfono": preferido}
        self._atajos = {
            "abrir_escena": SimpleNamespace(texto="ctrl+shift+e"),
            "abrir_grabacion": SimpleNamespace(texto="ctrl+shift+g"),
        }


class GestorConexion(GestorFalso):

    def __init__(self, conectado=False):
        super().__init__()
        self._conectado = conectado
        self.veces_conectar = 0

    @property
    def conectado(self):
        return self._conectado

    def conectar(self):
        self.veces_conectar += 1
        self._conectado = True


_APP = None


def setUpModule():
    # Mantiene viva la aplicación para las pruebas que comparten el proceso:
    # al terminar este módulo, otras no crean una propia.
    global _APP
    _APP = app_de_prueba()


def _asegurar_obs(probar_conexion, al_anunciar=None, parada=None):
    return probar_conexion()


def _asegurar_sin_conectar(probar_conexion, al_anunciar=None, parada=None):
    return False


class Evento:
    def Skip(self): pass


class TestPanelObsEnGrabacion(unittest.TestCase):

    def setUp(self):
        self.app = app_de_prueba()
        self.anuncios = []

        def anunciar(texto, categoria=""):
            self.anuncios.append(texto)

        self.parches = [
            mock.patch.object(threading, "Thread", HiloInmediato),
            mock.patch.object(obs_ventana.wx, "CallAfter",
                              lambda funcion, *args: funcion(*args)),
            mock.patch.object(obs_ventana.obs_lanzador, "asegurar_obs",
                              _asegurar_sin_conectar),
            mock.patch.object(obs_ventana, "anunciar", anunciar),
            mock.patch.object(operaciones_obs, "anunciar", anunciar),
            mock.patch.object(operaciones_obs.sound_player, "reproducir"),
            mock.patch.object(control_grabacion, "anunciar", anunciar),
            mock.patch.object(control_grabacion.sound_player, "reproducir"),
            mock.patch.object(gui_grabaciones.grabaciones, "existentes",
                              return_value=[]),
        ]
        for parche in self.parches:
            parche.start()
        self.addCleanup(self._frenar)
        self.principal = PrincipalFalsa()
        self.gestor = GestorFalso()
        self.dialogo = self._crear()
        self.anuncios.clear()

    def _frenar(self):
        for parche in reversed(self.parches):
            parche.stop()

    def _crear(self, gestor=None, principal=None,
               pestana=obs_ventana.PESTANA_GRABACION):
        dialogo = obs_ventana.VentanaObs(
            None, principal or self.principal,
            gestor=self.gestor if gestor is None else gestor,
            pestana=pestana)
        self.addCleanup(destruir, dialogo)
        return dialogo

    def _pulsar(self, boton):
        boton.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_BUTTON.typeId, boton.GetId()))

    def _marcar(self, casilla, valor):
        casilla.SetValue(valor)
        casilla.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_CHECKBOX.typeId, casilla.GetId()))

    def _nombres(self, ventana):
        nombres = []
        for hijo in ventana.GetChildren():
            if isinstance(hijo, (wx.TextCtrl, wx.Button, wx.CheckBox,
                                 wx.ListBox)) and hijo.IsShown():
                nombres.append(hijo.GetName())
            nombres.extend(self._nombres(hijo))
        return nombres

    def test_titulo_y_orden_de_tab_de_grabacion(self):
        self.assertEqual(self.dialogo.GetTitle(), "Panel de OBS")
        self.assertEqual(self._nombres(self.dialogo._pagina_grabacion), [
            "Iniciar grabación", "Grabar también al transmitir",
            "Grabaciones y clips"])

    def test_la_pestana_no_tiene_campo_de_estado_ni_actualizar(self):
        pagina = self.dialogo._pagina_grabacion
        self.assertFalse(hasattr(pagina, "txt_estado"))
        self.assertFalse(hasattr(pagina, "btn_actualizar"))

    def test_general_reune_escena_microfono_y_grabacion(self):
        texto = self.dialogo._pagina_general.texto()
        self.assertIn("Escena actual: Principal", texto)
        self.assertIn("Micrófono Mic/Aux: activado", texto)
        self.assertIn("Grabación: detenida", texto)

    def test_volver_a_grabacion_relee_la_lista(self):
        entrada = {"ruta": "C:/Videos/clips/clip.mp4", "fecha": 1000,
                   "tamano": 2 * 1024 * 1024, "tipo": "clip"}
        evento = wx.BookCtrlEvent(
            wx.EVT_NOTEBOOK_PAGE_CHANGED.typeId, self.dialogo.nb.GetId())
        evento.SetSelection(obs_ventana.PESTANA_GRABACION)
        with mock.patch.object(gui_grabaciones.grabaciones, "existentes",
                               return_value=[entrada]):
            self.dialogo.nb.GetEventHandler().ProcessEvent(evento)
        lista = self.dialogo._pagina_grabacion.lista._lista
        self.assertEqual(lista.GetCount(), 1)
        self.assertIn("Clip, clip.mp4", lista.GetString(0))

    def test_abrir_con_pestana_elige_grabacion(self):
        self.assertEqual(self.dialogo.nb.GetSelection(),
                         obs_ventana.PESTANA_GRABACION)

    def test_pausar_aparece_solo_mientras_se_graba(self):
        self.dialogo._pagina_grabacion._grabacion.fijar(True, False)
        nombres = self._nombres(self.dialogo._pagina_grabacion)
        self.assertIn("Detener grabación", nombres)
        self.assertIn("Pausar grabación", nombres)

    def test_al_abrir_enfoca_iniciar_sin_anunciar_el_estado(self):
        self.anuncios.clear()
        dialogo = self._crear()
        self.assertEqual(self.anuncios, [])
        self.assertIs(dialogo.FindFocus(),
                      dialogo._pagina_grabacion._grabacion.boton)

    def test_iniciar_llama_a_alternar_grabacion_con_ruta_y_refresca(self):
        with mock.patch.object(
                self.gestor, "alternar_grabacion_con_ruta",
                wraps=self.gestor.alternar_grabacion_con_ruta) as alternar, \
                mock.patch.object(
                    consultas_transmision, "leer_estado",
                    wraps=consultas_transmision.leer_estado) as leer:
            self._pulsar(self.dialogo._pagina_grabacion._grabacion.boton)
        alternar.assert_called_once_with()
        self.assertEqual(leer.call_count, 2)
        self.assertIn("Grabación: en curso, 00:01:02",
                      self.dialogo._pagina_general.texto())

    def test_los_botones_suenan_y_anuncian_como_el_panel(self):
        self._pulsar(self.dialogo._pagina_grabacion._grabacion.boton)
        control_grabacion.sound_player.reproducir.assert_called_with(
            "grabacion_iniciada")
        self.assertIn("Grabación iniciada", self.anuncios)
        control_grabacion.sound_player.reproducir.reset_mock()
        self._pulsar(self.dialogo._pagina_grabacion._grabacion.pausar)
        control_grabacion.sound_player.reproducir.assert_called_with(
            "grabacion_en_pausa")
        self.assertIn("Grabación en pausa", self.anuncios)

    def test_la_casilla_llama_a_alternar_grabar_al_transmitir(self):
        with mock.patch.object(
                gui_transmitir, "alternar_grabar_al_transmitir") as alternar:
            self._marcar(self.dialogo._pagina_grabacion.chk_grabar, True)
        alternar.assert_called_once_with(self.principal)

    def test_la_casilla_arranca_con_la_preferencia(self):
        dialogo = self._crear(principal=PrincipalFalsa(grabar=True))
        self.assertTrue(dialogo._pagina_grabacion.chk_grabar.GetValue())

    def test_si_no_estaba_conectado_conecta_una_vez(self):
        gestor = GestorConexion(conectado=False)
        with mock.patch.object(obs_ventana.obs_lanzador, "asegurar_obs",
                               return_value=False) as asegurar:
            dialogo = self._crear(gestor=gestor)
        asegurar.assert_called_once()
        self.assertEqual(gestor.veces_conectar, 1)
        self.assertTrue(gestor.conectado)
        self.assertTrue(dialogo._pagina_general.texto())

    def test_si_obs_no_responde_lo_dice_en_el_estado(self):
        gestor = GestorFalso(fallo=True)
        with mock.patch.object(obs_ventana.obs_lanzador, "asegurar_obs",
                               _asegurar_obs):
            dialogo = self._crear(gestor=gestor)
        self.assertIn("OBS no está disponible",
                      dialogo._pagina_general.texto())
        self.assertFalse(dialogo._operaciones.en_vuelo)

    def test_el_atajo_configurado_de_abrir_grabacion_ya_no_cambia_de_pestana(self):
        self.dialogo.nb.SetSelection(obs_ventana.PESTANA_ESCENA)
        evento = mock.Mock()
        evento.GetKeyCode.return_value = ord("G")
        evento.ControlDown.return_value = True
        evento.AltDown.return_value = False
        evento.ShiftDown.return_value = True
        self.dialogo._al_tecla(evento)
        self.assertEqual(self.dialogo.nb.GetSelection(),
                         obs_ventana.PESTANA_ESCENA)
        evento.Skip.assert_called_once_with()

    def test_el_atajo_configurado_de_abrir_escena_ya_no_cambia_de_pestana(self):
        self.dialogo.nb.SetSelection(obs_ventana.PESTANA_GRABACION)
        evento = mock.Mock()
        evento.GetKeyCode.return_value = ord("E")
        evento.ControlDown.return_value = True
        evento.AltDown.return_value = False
        evento.ShiftDown.return_value = True
        self.dialogo._al_tecla(evento)
        self.assertEqual(self.dialogo.nb.GetSelection(),
                         obs_ventana.PESTANA_GRABACION)
        evento.Skip.assert_called_once_with()

    def test_ctrl_mas_tab_deja_que_el_cuaderno_cambie_de_pestana(self):
        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_TAB
        evento.ControlDown.return_value = True
        evento.AltDown.return_value = False
        evento.ShiftDown.return_value = False
        self.dialogo._al_tecla(evento)
        evento.Skip.assert_called_once_with()

    def test_cerrar_con_gestor_propio_lo_cierra(self):
        with mock.patch.object(obs_ventana, "GestorPanelObs",
                               return_value=self.gestor):
            dialogo = obs_ventana.VentanaObs(None, self.principal)
        self.addCleanup(destruir, dialogo)
        dialogo.EndModal = mock.Mock()
        dialogo._cerrar(Evento())
        self.assertIn(("cerrar",), self.gestor.llamadas)
        dialogo.EndModal.assert_called_once_with(wx.ID_CANCEL)

    def test_cerrar_con_gestor_dado_no_lo_cierra(self):
        self.dialogo.EndModal = mock.Mock()
        self.dialogo._cerrar(Evento())
        self.assertNotIn(("cerrar",), self.gestor.llamadas)
        self.dialogo.EndModal.assert_called_once_with(wx.ID_CANCEL)


if __name__ == "__main__":
    unittest.main()
