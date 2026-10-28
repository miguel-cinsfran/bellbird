"""Pruebas de las consultas a OBS de la ventana de transmisión."""

import unittest
from unittest import mock

from ytchat.obs import consultas_transmision


def _gestor():
    gestor = mock.Mock()
    gestor.escenas.return_value = ("Principal", "Juego")
    gestor.escena_al_aire.return_value = "Juego"
    gestor.fuentes.return_value = ("Cámara", "Chat YTChat")
    gestor.instantanea.return_value = mock.sentinel.snap
    gestor.transformacion.return_value = mock.sentinel.transformacion
    gestor.estado_transmision.return_value = mock.sentinel.transmision
    gestor.estado_grabacion.return_value = mock.sentinel.grabacion
    gestor.perfil_actual.return_value = mock.sentinel.perfil
    gestor.ventanas.return_value = (mock.sentinel.opciones,
                                    mock.sentinel.actual)
    gestor.descripcion_escena.return_value = mock.sentinel.descripcion
    gestor.usar_ventana.return_value = mock.sentinel.frase
    return gestor


class TestCargarInicial(unittest.TestCase):

    def test_usa_la_escena_al_aire_si_esta_entre_las_escenas(self):
        datos = consultas_transmision.cargar_inicial(_gestor())
        self.assertEqual(datos.escena, "Juego")

    def test_usa_la_primera_si_la_del_aire_ya_no_esta(self):
        gestor = _gestor()
        gestor.escena_al_aire.return_value = "Vieja"
        datos = consultas_transmision.cargar_inicial(gestor)
        self.assertEqual(datos.escena, "Principal")

    def test_elige_la_fuente_del_chat(self):
        datos = consultas_transmision.cargar_inicial(_gestor())
        self.assertEqual(datos.fuente, "Chat YTChat")

    def test_cada_campo_viene_de_su_llamada(self):
        datos = consultas_transmision.cargar_inicial(_gestor())
        self.assertEqual(datos.escenas, ("Principal", "Juego"))
        self.assertEqual(datos.al_aire, "Juego")
        self.assertEqual(datos.fuentes, ("Cámara", "Chat YTChat"))
        self.assertIs(datos.snap, mock.sentinel.snap)
        self.assertIs(datos.transformacion, mock.sentinel.transformacion)
        self.assertIs(datos.transmision, mock.sentinel.transmision)
        self.assertIs(datos.grabacion, mock.sentinel.grabacion)
        self.assertIs(datos.perfil, mock.sentinel.perfil)
        self.assertIs(datos.opciones, mock.sentinel.opciones)
        self.assertIs(datos.actual, mock.sentinel.actual)
        self.assertIs(datos.descripcion, mock.sentinel.descripcion)

    def test_llama_al_gestor_en_el_mismo_orden(self):
        gestor = _gestor()
        consultas_transmision.cargar_inicial(gestor)
        self.assertEqual(
            [llamada[0] for llamada in gestor.mock_calls],
            ["conectar", "escenas", "escena_al_aire", "fuentes",
             "instantanea", "ventanas", "transformacion",
             "estado_transmision", "estado_grabacion", "perfil_actual",
             "descripcion_escena"])


class TestAplicarVentana(unittest.TestCase):

    def test_cada_campo_viene_de_su_llamada(self):
        datos = consultas_transmision.aplicar_ventana(
            _gestor(), "Principal", "Champions:Ventana:juego.exe")
        self.assertIs(datos.frase, mock.sentinel.frase)
        self.assertEqual(datos.fuentes, ("Cámara", "Chat YTChat"))
        self.assertEqual(datos.fuente, "Chat YTChat")
        self.assertIs(datos.snap, mock.sentinel.snap)
        self.assertEqual(datos.al_aire, "Juego")
        self.assertIs(datos.transmision, mock.sentinel.transmision)
        self.assertIs(datos.grabacion, mock.sentinel.grabacion)
        self.assertIs(datos.opciones, mock.sentinel.opciones)
        self.assertIs(datos.actual, mock.sentinel.actual)

    def test_pasa_escena_y_valor_y_llama_en_orden(self):
        gestor = _gestor()
        consultas_transmision.aplicar_ventana(
            gestor, "Principal", "Champions:Ventana:juego.exe")
        gestor.usar_ventana.assert_called_once_with(
            "Principal", "Champions:Ventana:juego.exe")
        gestor.fuentes.assert_called_once_with("Principal")
        gestor.instantanea.assert_called_once_with(
            "Principal", fuente="Chat YTChat")
        self.assertEqual(
            [llamada[0] for llamada in gestor.mock_calls],
            ["usar_ventana", "fuentes", "instantanea", "escena_al_aire",
             "estado_transmision", "estado_grabacion", "ventanas"])


class TestLeerEscena(unittest.TestCase):

    def test_cada_campo_viene_de_su_llamada(self):
        datos = consultas_transmision.leer_escena(_gestor(), "Juego")
        self.assertEqual(datos.fuentes, ("Cámara", "Chat YTChat"))
        self.assertEqual(datos.fuente, "Chat YTChat")
        self.assertIs(datos.snap, mock.sentinel.snap)
        self.assertIs(datos.opciones, mock.sentinel.opciones)
        self.assertIs(datos.actual, mock.sentinel.actual)

    def test_pide_la_escena_dada_y_llama_en_orden(self):
        gestor = _gestor()
        consultas_transmision.leer_escena(gestor, "Juego")
        gestor.fuentes.assert_called_once_with("Juego")
        gestor.instantanea.assert_called_once_with(
            "Juego", fuente="Chat YTChat")
        gestor.ventanas.assert_called_once_with("Juego")
        self.assertEqual(
            [llamada[0] for llamada in gestor.mock_calls],
            ["fuentes", "instantanea", "ventanas"])


if __name__ == "__main__":
    unittest.main()
