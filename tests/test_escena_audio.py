"""Pestaña Audio de la ventana Escena: la prueba del micrófono.

Abre ventanas: se corre en la PC de pruebas, no en la del dueño.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

import wx

from bellbird.obs import nivel_microfono
from bellbird.ui import escena_pagina_audio
from tests.ventanas_prueba import destruir

TEXTO_INICIO = "Prueba del micrófono iniciada. Habla como en un directo."
TEXTO_SILENCIADO = ("El micrófono está silenciado en OBS. Desmarca "
                    "Silenciar micrófono y vuelve a probar.")


class OperacionesFalsas:
    def en_hilo(self, funcion, al_terminar=None):
        resultado = funcion()
        if al_terminar is not None:
            al_terminar(resultado)


class TestPaginaAudioPrueba(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)
        self.marco = wx.Frame(None)
        self.addCleanup(destruir, self.marco)
        self.principal = SimpleNamespace(_config={"obs_microfono": "Mic/Aux"})
        self.gestor = object()

        parche_preparar = mock.patch.object(
            escena_pagina_audio.prueba_microfono, "preparar",
            return_value=("Mic/Aux", False, "Micrófono USB"))
        parche_clase = mock.patch.object(
            escena_pagina_audio.prueba_microfono, "PruebaMicrofono")
        parche_anunciar = mock.patch.object(escena_pagina_audio, "anunciar")
        parche_sonido = mock.patch.object(
            escena_pagina_audio.sound_player, "reproducir")
        parche_callafter = mock.patch.object(
            escena_pagina_audio.wx, "CallAfter",
            side_effect=lambda funcion, *args, **kwargs:
            funcion(*args, **kwargs))
        self.preparar = parche_preparar.start()
        self.clase = parche_clase.start()
        self.anunciar = parche_anunciar.start()
        self.reproducir = parche_sonido.start()
        parche_callafter.start()
        for parche in (parche_preparar, parche_clase, parche_anunciar,
                       parche_sonido, parche_callafter):
            self.addCleanup(parche.stop)

        self.pagina = escena_pagina_audio.PaginaAudio(
            self.marco, self.principal, self.gestor, OperacionesFalsas())

    def _pulsar(self):
        evento = wx.CommandEvent(wx.EVT_BUTTON.typeId,
                                 self.pagina.btn_probar.GetId())
        self.pagina.btn_probar.GetEventHandler().ProcessEvent(evento)

    def _iniciar(self):
        self._pulsar()
        self.anunciar.reset_mock()
        return self.clase.return_value

    def test_el_boton_inicia_y_cambia_su_rotulo_y_nombre(self):
        self._pulsar()
        self.preparar.assert_called_once_with(self.gestor, "Mic/Aux")
        self.clase.assert_called_once()
        self.clase.return_value.iniciar.assert_called_once_with()
        self.assertEqual(self.pagina.btn_probar.GetLabel(), "&Detener prueba")
        self.assertEqual(self.pagina.btn_probar.GetName(), "Detener prueba")
        self.anunciar.assert_any_call(TEXTO_INICIO)

    def test_un_tramo_reproduce_su_sonido_y_anuncia_sin_interrumpir(self):
        instancia = self._iniciar()
        al_tramo = self.clase.call_args.args[1]
        al_tramo(nivel_microfono.Nivel(nivel_microfono.BIEN, -3.0))
        self.reproducir.assert_called_once_with("microfono_bien")
        self.anunciar.assert_called_once_with("Nivel bien.", False)
        instancia.detener.assert_not_called()

    def test_pulsar_otra_vez_detiene_la_prueba(self):
        instancia = self._iniciar()
        self._pulsar()
        instancia.detener.assert_called_once_with()
        self.clase.assert_called_once()

    def test_al_terminar_vuelve_el_rotulo_y_lo_anuncia(self):
        self._iniciar()
        al_terminar = self.clase.call_args.args[2]
        al_terminar("detenida")
        self.assertEqual(self.pagina.btn_probar.GetLabel(), "&Probar micrófono")
        self.assertEqual(self.pagina.btn_probar.GetName(), "Probar micrófono")
        self.anunciar.assert_called_once_with("Prueba del micrófono detenida.")

    def test_un_fallo_anuncia_que_no_se_pudo_medir(self):
        self._iniciar()
        al_terminar = self.clase.call_args.args[2]
        al_terminar("fallo")
        self.anunciar.assert_called_once_with(
            "No se pudo medir el micrófono en OBS. Prueba detenida.")

    def test_al_destruir_detiene_y_un_tramo_posterior_no_toca_controles(self):
        instancia = self._iniciar()
        al_tramo = self.clase.call_args.args[1]
        self.anunciar.reset_mock()
        self.reproducir.reset_mock()
        destruir(self.pagina)
        instancia.detener.assert_called_once_with()
        al_tramo(nivel_microfono.Nivel(nivel_microfono.BIEN, -3.0))
        self.reproducir.assert_not_called()
        self.anunciar.assert_not_called()

    def test_terminar_deja_empezar_otra_prueba(self):
        primera = mock.Mock()
        segunda = mock.Mock()
        self.clase.side_effect = [primera, segunda]
        self._pulsar()
        al_terminar = self.clase.call_args.args[2]
        al_terminar("detenida")
        self.assertEqual(self.pagina.btn_probar.GetLabel(), "&Probar micrófono")
        self._pulsar()
        primera.detener.assert_not_called()
        self.assertEqual(self.clase.call_count, 2)
        segunda.iniciar.assert_called_once_with()
        self.assertEqual(self.pagina.btn_probar.GetLabel(), "&Detener prueba")

    def test_silenciado_no_inicia_y_dice_por_que(self):
        self.preparar.return_value = ("Mic/Aux", True, "Micrófono USB")
        self._pulsar()
        self.clase.assert_not_called()
        self.anunciar.assert_called_once_with(TEXTO_SILENCIADO)
        self.assertEqual(self.pagina.btn_probar.GetLabel(), "&Probar micrófono")

    def test_sin_microfono_anuncia_el_aviso_de_obs(self):
        self.preparar.return_value = ("", False, "")
        self._pulsar()
        self.clase.assert_not_called()
        self.anunciar.assert_called_once_with(
            "OBS no tiene ningún micrófono. Elige uno en Preferencias, "
            "categoría Transmisión, Micrófono de OBS.")


if __name__ == "__main__":
    unittest.main()
