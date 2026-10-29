import unittest
from unittest import mock

from ytchat.ui import gui

TEXTO_SIN_SENAL = ("El micrófono no recibe sonido. Revisa cuál está elegido "
                   "en Windows o en OBS.")


class HiloInmediato:
    def __init__(self, funcion):
        self.funcion = funcion

    def start(self):
        self.funcion()


class AccionMicrofonoObsTest(unittest.TestCase):
    def _ejecutar(self, marcada_antes=False):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._config = {"obs_microfono": "Audio USB"}
        frame.mi_obs_micro = mock.Mock()
        frame.mi_obs_micro.IsChecked.return_value = marcada_antes
        avisos = []
        with mock.patch.object(
                gui.obs_entradas_audio, "microfono_por_atajo") as por_atajo, \
                mock.patch.object(
                    gui.diagnostico, "crear_hilo",
                    side_effect=lambda funcion, nombre: HiloInmediato(funcion)) as crear, \
                mock.patch.object(
                    gui.wx, "CallAfter",
                    side_effect=lambda funcion, *args: funcion(*args)), \
                mock.patch.object(
                    gui._snd, "reproducir",
                    side_effect=lambda nombre: avisos.append(("sonido", nombre))), \
                mock.patch.object(
                    gui, "anunciar",
                    side_effect=lambda texto, *args: avisos.append(("anuncio", texto))):
            frame._on_obs_micro(None)
            avisar = por_atajo.call_args.args[1]
            avisar("Micrófono activado", "")
            avisar(TEXTO_SIN_SENAL, "microfono_sin_senal")
        return frame, por_atajo, crear, avisos

    def test_llama_al_atajo_con_el_microfono_guardado(self):
        _, por_atajo, crear, _ = self._ejecutar()
        por_atajo.assert_called_once()
        self.assertEqual(por_atajo.call_args.args[0], "Audio USB")
        self.assertTrue(callable(por_atajo.call_args.args[1]))
        self.assertTrue(callable(por_atajo.call_args.args[2]))
        crear.assert_called_once()

    def test_avisa_sin_sonido_y_luego_con_el_sonido_antes_de_la_frase(self):
        _, _, _, avisos = self._ejecutar()
        self.assertEqual(avisos, [
            ("anuncio", "Micrófono activado"),
            ("sonido", "microfono_sin_senal"),
            ("anuncio", TEXTO_SIN_SENAL),
        ])

    def test_al_estado_verdadero_deja_la_casilla_marcada(self):
        frame, por_atajo, _, _ = self._ejecutar()
        al_estado = por_atajo.call_args.args[2]
        with mock.patch.object(
                gui.wx, "CallAfter",
                side_effect=lambda funcion, *args: funcion(*args)):
            al_estado(True)
        frame.mi_obs_micro.Check.assert_called_once_with(True)

    def test_al_estado_falso_deja_la_casilla_sin_marcar(self):
        frame, por_atajo, _, _ = self._ejecutar(marcada_antes=True)
        al_estado = por_atajo.call_args.args[2]
        with mock.patch.object(
                gui.wx, "CallAfter",
                side_effect=lambda funcion, *args: funcion(*args)):
            al_estado(False)
        frame.mi_obs_micro.Check.assert_called_once_with(False)

    def test_al_estado_nada_devuelve_la_marca_a_como_estaba(self):
        frame, por_atajo, _, _ = self._ejecutar(marcada_antes=True)
        al_estado = por_atajo.call_args.args[2]
        with mock.patch.object(
                gui.wx, "CallAfter",
                side_effect=lambda funcion, *args: funcion(*args)):
            al_estado(None)
        frame.mi_obs_micro.Check.assert_called_once_with(True)


if __name__ == "__main__":
    unittest.main()
