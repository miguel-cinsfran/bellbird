"""Pruebas del registro de restablecimiento de OBS, sin wx."""

import types
import unittest
from unittest import mock

from guyrapu.obs.obs_panel import NOMBRE_FUENTE
from guyrapu.obs.restablecimiento import RegistroRestablecimiento


TRANSFORMACION = {
    "positionX": 40, "positionY": 50, "alignment": 5, "rotation": 12,
    "scaleX": 1.5, "scaleY": 1.4, "boundsType": "OBS_BOUNDS_SCALE_INNER",
    "boundsAlignment": 0, "boundsWidth": 640, "boundsHeight": 360,
    "cropLeft": 1, "cropRight": 2, "cropTop": 3, "cropBottom": 4,
}


def _elemento(nombre, transformacion=TRANSFORMACION):
    return {"sourceName": nombre, "sceneItemId": 2,
            "sceneItemTransform": dict(transformacion)}


def _gestor_con_datos(transformacion=None, elementos=None):
    gestor = mock.Mock()
    gestor.instantanea.return_value = types.SimpleNamespace(
        ancho=460, alto=620, visible=True, bloqueada=False)
    gestor.transformacion.return_value = (
        {"positionX": 32, "positionY": 18, "alignment": 5}
        if transformacion is None else transformacion)
    gestor.fuentes.return_value = ("Cámara", NOMBRE_FUENTE, "Juego")
    if elementos is None:
        elementos = [_elemento("Cámara"), _elemento(NOMBRE_FUENTE)]
    gestor.elementos.return_value = elementos
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
            mock.call.transformar("Principal", TRANSFORMACION,
                                  fuente=NOMBRE_FUENTE),
            mock.call.redimensionar("Principal", 460, 620),
            mock.call.mostrar("Principal", True, fuente=NOMBRE_FUENTE),
            mock.call.fijar("Principal", False, fuente=NOMBRE_FUENTE),
            mock.call.mover_capa("Principal", 1, fuente=NOMBRE_FUENTE),
        ])

    def test_aplicar_restaura_la_transformacion_completa(self):
        gestor = _gestor_con_datos()
        registro = RegistroRestablecimiento()
        registro.guardar(gestor, "Principal", "Cámara")
        gestor.reset_mock()
        registro.aplicar(gestor)
        self.assertEqual(gestor.mock_calls, [
            mock.call.transformar("Principal", TRANSFORMACION, fuente="Cámara"),
            mock.call.mostrar("Principal", True, fuente="Cámara"),
            mock.call.fijar("Principal", False, fuente="Cámara"),
            mock.call.mover_capa("Principal", 2, fuente="Cámara"),
        ])

    def test_aplicar_sin_transformacion_no_posiciona(self):
        gestor = _gestor_con_datos(transformacion={}, elementos=[])
        registro = RegistroRestablecimiento()
        registro.guardar(gestor, "Principal", "Cámara")
        gestor.reset_mock()
        registro.aplicar(gestor)
        self.assertEqual(gestor.mock_calls, [
            mock.call.escalar("Principal", 460, 620, fuente="Cámara"),
            mock.call.mostrar("Principal", True, fuente="Cámara"),
            mock.call.fijar("Principal", False, fuente="Cámara"),
            mock.call.mover_capa("Principal", 2, fuente="Cámara"),
        ])

    def test_aplicar_devuelve_la_fuente_a_su_capa(self):
        gestor = _gestor_con_datos()
        registro = RegistroRestablecimiento()
        registro.guardar(gestor, "Principal", "Cámara")
        gestor.fuentes.return_value = (NOMBRE_FUENTE, "Juego", "Cámara")
        gestor.reset_mock()
        registro.aplicar(gestor)
        gestor.mover_capa.assert_called_once_with(
            "Principal", 2, fuente="Cámara")

    def test_aplicar_restaura_las_capas_de_atras_adelante(self):
        gestor = _gestor_con_datos()
        registro = RegistroRestablecimiento()
        registro.guardar(gestor, "Principal", "Cámara")
        registro.guardar(gestor, "Principal", NOMBRE_FUENTE)
        gestor.reset_mock()
        registro.aplicar(gestor)
        self.assertEqual(
            [llamada for llamada in gestor.mock_calls
             if llamada[0] == "mover_capa"],
            [mock.call.mover_capa("Principal", 1, fuente=NOMBRE_FUENTE),
             mock.call.mover_capa("Principal", 2, fuente="Cámara")])

    def test_guardar_sin_cuadro_delimitador_omite_las_claves_del_cuadro(self):
        transformacion = dict(TRANSFORMACION, boundsType="OBS_BOUNDS_NONE")
        gestor = _gestor_con_datos(
            elementos=[_elemento("Cámara", transformacion)])
        registro = RegistroRestablecimiento()
        registro.guardar(gestor, "Principal", "Cámara")
        gestor.reset_mock()
        registro.aplicar(gestor)
        escritas = [llamada.args[1] for llamada in gestor.mock_calls
                    if llamada[0] == "transformar"]
        self.assertEqual(len(escritas), 1)
        self.assertEqual(escritas[0]["boundsType"], "OBS_BOUNDS_NONE")
        for clave in ("boundsAlignment", "boundsWidth", "boundsHeight"):
            self.assertNotIn(clave, escritas[0])

    def test_guardar_con_cuadro_de_ancho_cero_omite_las_claves_del_cuadro(self):
        transformacion = dict(TRANSFORMACION, boundsWidth=0)
        gestor = _gestor_con_datos(
            elementos=[_elemento("Cámara", transformacion)])
        registro = RegistroRestablecimiento()
        registro.guardar(gestor, "Principal", "Cámara")
        gestor.reset_mock()
        registro.aplicar(gestor)
        escritas = [llamada.args[1] for llamada in gestor.mock_calls
                    if llamada[0] == "transformar"]
        self.assertEqual(len(escritas), 1)
        for clave in ("boundsAlignment", "boundsWidth", "boundsHeight"):
            self.assertNotIn(clave, escritas[0])


if __name__ == "__main__":
    unittest.main()
