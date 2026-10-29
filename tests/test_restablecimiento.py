"""Pruebas del registro de restablecimiento de OBS, sin wx."""

import types
import unittest
from unittest import mock

from bellbird.obs.obs_panel import NOMBRE_FUENTE
from bellbird.obs.restablecimiento import RegistroRestablecimiento


def _gestor_con_datos(transformacion=None):
    gestor = mock.Mock()
    gestor.instantanea.return_value = types.SimpleNamespace(
        ancho=460, alto=620, visible=True, bloqueada=False)
    gestor.transformacion.return_value = (
        {"positionX": 32, "positionY": 18, "alignment": 5}
        if transformacion is None else transformacion)
    return gestor


class TestRegistroRestablecimiento(unittest.TestCase):

    def test_guardar_ignora_fuente_vacia(self):
        gestor = _gestor_con_datos()
        RegistroRestablecimiento().guardar(gestor, "Principal", "")
        self.assertEqual(gestor.mock_calls, [])

    def test_guardar_ignora_pareja_repetida(self):
        gestor = _gestor_con_datos()
        registro = RegistroRestablecimiento()
        registro.guardar(gestor, "Principal", "Cámara")
        gestor.reset_mock()
        registro.guardar(gestor, "Principal", "Cámara")
        self.assertEqual(gestor.mock_calls, [])

    def test_aplicar_redimensiona_el_panel_del_chat(self):
        gestor = _gestor_con_datos()
        registro = RegistroRestablecimiento()
        registro.guardar(gestor, "Principal", NOMBRE_FUENTE)
        gestor.reset_mock()
        registro.aplicar(gestor)
        self.assertEqual(gestor.mock_calls, [
            mock.call.posicionar("Principal", 32, 18, 5, fuente=NOMBRE_FUENTE),
            mock.call.redimensionar("Principal", 460, 620),
            mock.call.mostrar("Principal", True, fuente=NOMBRE_FUENTE),
            mock.call.fijar("Principal", False, fuente=NOMBRE_FUENTE),
        ])

    def test_aplicar_escala_otra_fuente(self):
        gestor = _gestor_con_datos()
        registro = RegistroRestablecimiento()
        registro.guardar(gestor, "Principal", "Cámara")
        gestor.reset_mock()
        registro.aplicar(gestor)
        self.assertEqual(gestor.mock_calls, [
            mock.call.posicionar("Principal", 32, 18, 5, fuente="Cámara"),
            mock.call.escalar("Principal", 460, 620, fuente="Cámara"),
            mock.call.mostrar("Principal", True, fuente="Cámara"),
            mock.call.fijar("Principal", False, fuente="Cámara"),
        ])

    def test_aplicar_sin_transformacion_no_posiciona(self):
        gestor = _gestor_con_datos(transformacion={})
        registro = RegistroRestablecimiento()
        registro.guardar(gestor, "Principal", "Cámara")
        gestor.reset_mock()
        registro.aplicar(gestor)
        self.assertEqual(gestor.mock_calls, [
            mock.call.escalar("Principal", 460, 620, fuente="Cámara"),
            mock.call.mostrar("Principal", True, fuente="Cámara"),
            mock.call.fijar("Principal", False, fuente="Cámara"),
        ])


if __name__ == "__main__":
    unittest.main()
