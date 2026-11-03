"""Pruebas de cómo se reordenan las capas de una escena de OBS."""

import unittest
from unittest import mock

from bellbird.obs import obs_capas


def elementos():
    return [
        {"sceneItemId": 10, "sourceName": "Fondo", "sceneItemIndex": 0},
        {"sceneItemId": 11, "sourceName": "Medio", "sceneItemIndex": 1},
        {"sceneItemId": 12, "sourceName": "Frente", "sceneItemIndex": 2},
    ]


class IndiceDestinoTest(unittest.TestCase):

    def test_cada_movimiento_desde_cada_posicion(self):
        casos = (
            ("Fondo", "adelante", 1),
            ("Medio", "adelante", 2),
            ("Frente", "adelante", None),
            ("Fondo", "atras", None),
            ("Medio", "atras", 0),
            ("Frente", "atras", 1),
            ("Fondo", "fondo", None),
            ("Medio", "fondo", 0),
            ("Frente", "fondo", 0),
        )
        for fuente, movimiento, esperado in casos:
            with self.subTest(fuente=fuente, movimiento=movimiento):
                self.assertEqual(
                    obs_capas.indice_destino(
                        elementos(), fuente, movimiento),
                    esperado)

    def test_el_destino_nunca_sale_de_los_limites(self):
        for fuente in ("Fondo", "Medio", "Frente"):
            for movimiento in ("adelante", "atras", "fondo"):
                with self.subTest(fuente=fuente, movimiento=movimiento):
                    destino = obs_capas.indice_destino(
                        elementos(), fuente, movimiento)
                    self.assertTrue(
                        destino is None or 0 <= destino < len(elementos()))


class LugarTest(unittest.TestCase):

    def test_cuenta_desde_el_frente(self):
        self.assertEqual(obs_capas.lugar(elementos(), "Frente"), (1, 3))
        self.assertEqual(obs_capas.lugar(elementos(), "Medio"), (2, 3))
        self.assertEqual(obs_capas.lugar(elementos(), "Fondo"), (3, 3))


class MoverTest(unittest.TestCase):

    def test_no_pide_nada_si_ya_esta_en_el_extremo(self):
        for fuente, movimiento in (("Frente", "adelante"),
                                   ("Fondo", "atras"),
                                   ("Fondo", "fondo")):
            with self.subTest(fuente=fuente, movimiento=movimiento):
                pedir = mock.Mock()
                self.assertFalse(obs_capas.mover(
                    pedir, elementos(), "Escena", fuente, movimiento))
                pedir.assert_not_called()

    def test_pide_el_indice_destino_y_devuelve_que_movio(self):
        pedir = mock.Mock()
        self.assertTrue(obs_capas.mover(
            pedir, elementos(), "Escena", "Medio", "adelante"))
        pedir.assert_called_once_with("SetSceneItemIndex", {
            "sceneName": "Escena", "sceneItemId": 11, "sceneItemIndex": 2,
        }, None)


if __name__ == "__main__":
    unittest.main()
