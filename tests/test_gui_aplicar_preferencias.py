"""Pruebas de las preferencias aplicadas en caliente, sin ventanas."""

import unittest
from unittest import mock

from tests.pseudo_prueba import con_pseudo
from bellbird.ui import gui_aplicar_preferencias
from bellbird.voice import motores


def _frame(configuracion):
    frame = mock.Mock()
    frame._config = dict(configuracion)
    frame._conectado = False
    frame._voz_idx = 0
    return frame


class TestAplicarEnCaliente(unittest.TestCase):

    def test_aplica_y_anuncia(self):
        frame = _frame({"motor": "sapi", "voz": "Voz A",
                        "atajos_raw": {}})
        frame._worker.motor_activo.return_value = "sapi"
        with mock.patch("bellbird.ui.gui.anunciar") as anunciar:
            gui_aplicar_preferencias.aplicar_en_caliente(frame)
        anunciar.assert_called_once_with("Preferencias aplicadas")

    def test_motor_distinto_anuncia_el_nombre(self):
        frame = _frame({"motor": "onecore", "voz": "Voz B",
                        "atajos_raw": {}})
        frame._worker.motor_activo.return_value = "sapi"
        frame.voz_submenu.GetMenuItems.return_value = []
        with mock.patch.object(motores, "listar_voces",
                               return_value=["Voz A", "Voz B"]), \
                mock.patch("bellbird.ui.gui.anunciar") as anunciar:
            gui_aplicar_preferencias.aplicar_en_caliente(frame)
        frame._worker.cambiar_motor.assert_called_once_with(
            "onecore", "Voz B")
        anunciar.assert_any_call("Motor de voz: Windows OneCore")


class TestPseudoTextos(unittest.TestCase):
    """Bajo pseudotraducción, cada frase al usuario sale marcada."""

    def test_anuncios_salen_marcados(self):
        frame = _frame({"motor": "onecore", "voz": "Voz B",
                        "atajos_raw": {}})
        frame._worker.motor_activo.return_value = "sapi"
        frame.voz_submenu.GetMenuItems.return_value = []
        with con_pseudo():
            with mock.patch.object(motores, "listar_voces",
                                   return_value=["Voz A", "Voz B"]), \
                    mock.patch("bellbird.ui.gui.anunciar") as anunciar:
                gui_aplicar_preferencias.aplicar_en_caliente(frame)
        self.assertTrue(anunciar.called)
        for llamada in anunciar.call_args_list:
            with self.subTest(texto=llamada.args[0]):
                self.assertTrue(llamada.args[0].startswith("[¡"),
                                llamada.args[0])


if __name__ == "__main__":
    unittest.main()
