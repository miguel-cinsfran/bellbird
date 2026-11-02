"""Pruebas de la lógica del botón del directo del panel de transmisión."""

from types import SimpleNamespace
from unittest import mock
import unittest

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False

from bellbird.obs import transmision_directa
from bellbird.ui import directo_panel
from tests.ventanas_prueba import destruir


class OperacionesInmediatas:

    def __init__(self):
        self.cerrando = False
        self.en_vuelo = False

    def en_hilo(self, funcion, al_terminar=None):
        resultado = funcion()
        if al_terminar is not None:
            al_terminar(resultado)


def _preparacion(revision=mock.sentinel.revision):
    return SimpleNamespace(ya_transmitiendo=False, revision=revision)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestDirectoPanel(unittest.TestCase):

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)
        self.ventana = wx.Dialog(None, name="DialogoPruebaDirecto")
        self.addCleanup(destruir, self.ventana)
        self.boton = wx.Button(self.ventana, label="Botón")
        self.addCleanup(destruir, self.boton)
        self.gestor = mock.Mock()
        self.supervisar = mock.Mock(return_value=False)
        self.guardar_usuario = mock.Mock()
        self.guardar_destino = mock.Mock()
        self.al_cambiar = mock.Mock()
        self.datos = ("YouTube", "")
        self.panel = directo_panel.DirectoPanel(
            self.ventana, self.boton, OperacionesInmediatas(), self.gestor,
            self.supervisar, self.guardar_usuario, self.guardar_destino,
            "", mock.Mock(return_value=False), self._datos, self.al_cambiar)

    def _datos(self):
        return self.datos

    def _pulsar(self):
        self.panel._al_pulsar(mock.Mock())

    def test_etiqueta_inicial(self):
        self.assertEqual(self.boton.GetLabel(), "Transm&itir en directo")
        self.assertEqual(self.boton.GetName(), "Transmitir en directo")

    def test_youtube_inicia_con_revision_y_sin_confirmar(self):
        revision = mock.sentinel.revision
        with mock.patch.object(transmision_directa, "preparar",
                               return_value=_preparacion(revision)), \
                mock.patch.object(directo_panel,
                                  "confirmar_transmision") as confirmar:
            self._pulsar()
        confirmar.assert_not_called()
        self.supervisar.assert_any_call(
            "iniciar", "YouTube", "", revision=revision)
        self.assertEqual(self.boton.GetLabel(), "&Finalizar directo")

    def test_tiktok_pasa_por_confirmar_transmision(self):
        self.datos = ("TikTok", "usuario")
        with mock.patch.object(transmision_directa, "preparar",
                               return_value=_preparacion()), \
                mock.patch.object(directo_panel, "confirmar_transmision",
                                  return_value=True) as confirmar:
            self._pulsar()
        confirmar.assert_called_once_with(
            self.ventana, mock.sentinel.revision)
        self.supervisar.assert_any_call("iniciar", "TikTok", "usuario")

    def test_tiktok_cancelar_no_inicia(self):
        self.datos = ("TikTok", "usuario")
        with mock.patch.object(transmision_directa, "preparar",
                               return_value=_preparacion()), \
                mock.patch.object(directo_panel, "confirmar_transmision",
                                  return_value=False), \
                mock.patch.object(directo_panel, "anunciar") as anunciar:
            self._pulsar()
        self.assertNotIn(mock.call("iniciar", mock.ANY, mock.ANY),
                         self.supervisar.call_args_list)
        self.assertEqual(anunciar.call_args.args[0], "No se transmitió.")

    def test_si_obs_ya_transmite_pasa_a_finalizar(self):
        with mock.patch.object(
                transmision_directa, "preparar",
                return_value=SimpleNamespace(ya_transmitiendo=True,
                                             revision=None)), \
                mock.patch.object(directo_panel, "anunciar") as anunciar:
            self._pulsar()
        self.assertEqual(self.boton.GetLabel(), "&Finalizar directo")
        self.assertIn(
            "OBS ya está transmitiendo. Con este mismo botón puedes "
            "finalizar el directo.", [llamada.args[0]
                                      for llamada in anunciar.call_args_list])

    def test_finalizar_con_respuesta_negativa_no_detiene(self):
        self.panel.sincronizar(True)
        with mock.patch.object(directo_panel, "confirmar_finalizar",
                               return_value=False) as confirmar, \
                mock.patch.object(directo_panel, "anunciar") as anunciar:
            self.panel._finalizar()
        confirmar.assert_called_once_with(self.ventana)
        self.supervisar.assert_not_called()
        anunciar.assert_called_once_with("Sigues transmitiendo.")

    def test_finalizar_detiene_y_dice_deteniendo(self):
        self.panel.sincronizar(True)
        self.supervisar.side_effect = lambda accion: accion == "activo"
        with mock.patch.object(directo_panel, "confirmar_finalizar",
                               return_value=True), \
                mock.patch.object(self.panel._temporizador, "Start") as armar:
            self.panel._finalizar()
        self.supervisar.assert_any_call("detener")
        self.assertEqual(self.boton.GetLabel(), "Finalizando el directo")
        armar.assert_called_once_with(2000)

    def test_temporizador_devuelve_el_boton_al_estado_normal(self):
        self.panel.sincronizar(True)
        self.panel._deteniendo = True
        self.panel._actualizar_boton()
        self.supervisar.side_effect = lambda accion: False
        with mock.patch.object(self.panel._temporizador, "Stop") as parar:
            self.panel._al_temporizador(mock.Mock())
        parar.assert_called_once_with()
        self.assertEqual(self.boton.GetLabel(), "Transm&itir en directo")
        self.al_cambiar.assert_called()

    def test_pulsar_mientras_se_detiene_solo_avisa(self):
        self.panel.sincronizar(True)
        self.panel._deteniendo = True
        with mock.patch.object(directo_panel, "anunciar") as anunciar, \
                mock.patch.object(directo_panel,
                                  "confirmar_finalizar") as confirmar:
            self._pulsar()
        confirmar.assert_not_called()
        anunciar.assert_called_once_with(
            "Deteniendo la transmisión. Esperando a que OBS confirme.")

    def test_cerrar_detiene_el_temporizador(self):
        with mock.patch.object(self.panel._temporizador, "Stop") as parar:
            self.panel.cerrar()
        parar.assert_called_once_with()


class TestPrepararCerrarGestor(unittest.TestCase):

    def _gestor(self):
        gestor = mock.Mock()
        gestor.estado_transmision.return_value = {"outputActive": False}
        gestor.perfil_actual.return_value = "YouTube"
        gestor.preparar_destino.return_value = {}
        gestor.revisar.return_value = mock.sentinel.revision
        return gestor

    def test_cerrar_false_no_cierra_el_gestor(self):
        gestor = self._gestor()
        preparacion = transmision_directa.preparar(
            gestor, "YouTube", lambda *a, **k: False, lambda frase: None,
            cerrar=False)
        gestor.cerrar.assert_not_called()
        self.assertIs(preparacion.revision, mock.sentinel.revision)

    def test_cerrar_por_defecto_sigue_cerrando(self):
        gestor = self._gestor()
        transmision_directa.preparar(
            gestor, "YouTube", lambda *a, **k: False, lambda frase: None)
        gestor.cerrar.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
