"""Pruebas de las consultas a OBS de la ventana de transmisión."""

import unittest
from unittest import mock

from bellbird.obs import consultas_transmision
from bellbird.obs import obs_disposicion


def _gestor():
    gestor = mock.Mock()
    gestor.escenas.return_value = ("Principal", "Juego")
    gestor.escena_al_aire.return_value = "Juego"
    gestor.fuentes.return_value = ("Cámara", "Chat en el vídeo")
    gestor.instantanea.return_value = mock.sentinel.snap
    gestor.transformacion.return_value = mock.sentinel.transformacion
    gestor.estado_transmision.return_value = mock.sentinel.transmision
    gestor.estado_grabacion.return_value = mock.sentinel.grabacion
    gestor.perfil_actual.return_value = "YouTube"
    gestor.entradas_audio.return_value = (
        ("Mic/Aux", "wasapi_input_capture"),)
    gestor.microfono_especial.return_value = ""
    gestor.revisar.return_value = mock.Mock(problemas=("Un problema.",))
    gestor.silenciada.return_value = False
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

    def test_cada_campo_viene_de_su_llamada(self):
        datos = consultas_transmision.cargar_inicial(_gestor())
        self.assertEqual(datos.escenas, ("Principal", "Juego"))
        self.assertEqual(datos.al_aire, "Juego")
        self.assertEqual(datos.fuentes, ("Cámara", "Chat en el vídeo"))
        self.assertIs(datos.transmision, mock.sentinel.transmision)
        self.assertIs(datos.grabacion, mock.sentinel.grabacion)
        self.assertEqual(datos.perfil, "YouTube")
        self.assertEqual(datos.problemas, ("Un problema.",))
        self.assertEqual(datos.microfono, "Mic/Aux")
        self.assertFalse(datos.silenciado)

    def test_llama_al_gestor_en_el_mismo_orden(self):
        gestor = _gestor()
        consultas_transmision.cargar_inicial(gestor)
        self.assertEqual(
            [llamada[0] for llamada in gestor.mock_calls],
            ["conectar", "escenas", "escena_al_aire", "fuentes",
             "estado_transmision", "estado_grabacion", "perfil_actual",
             "entradas_audio", "microfono_especial", "revisar", "silenciada"])

    def test_sin_destino_elegido_los_problemas_quedan_vacios(self):
        gestor = _gestor()
        gestor.perfil_actual.return_value = "N5000-Grabacion"
        datos = consultas_transmision.cargar_inicial(gestor)
        self.assertEqual(datos.problemas, ())
        gestor.revisar.assert_not_called()

    def test_usa_el_microfono_preferido_y_su_silencio(self):
        gestor = _gestor()
        gestor.entradas_audio.return_value = (
            ("Mic/Aux", "wasapi_input_capture"),
            ("Micrófono USB", "wasapi_input_capture"))
        gestor.silenciada.return_value = True
        datos = consultas_transmision.cargar_inicial(
            gestor, preferido="Micrófono USB")
        self.assertEqual(datos.microfono, "Micrófono USB")
        self.assertTrue(datos.silenciado)
        gestor.silenciada.assert_called_once_with("Micrófono USB")

    def test_sin_microfono_no_pregunta_silencio(self):
        gestor = _gestor()
        gestor.entradas_audio.return_value = ()
        datos = consultas_transmision.cargar_inicial(gestor)
        self.assertEqual(datos.microfono, "")
        self.assertFalse(datos.silenciado)
        gestor.silenciada.assert_not_called()


class TestLeerEstado(unittest.TestCase):

    def test_cada_campo_viene_de_su_llamada(self):
        datos = consultas_transmision.leer_estado(
            _gestor(), "YouTube", preferido="Mic/Aux")
        self.assertEqual(datos.escena, "Juego")
        self.assertIs(datos.transmision, mock.sentinel.transmision)
        self.assertIs(datos.grabacion, mock.sentinel.grabacion)
        self.assertEqual(datos.perfil, "YouTube")
        self.assertEqual(datos.problemas, ("Un problema.",))
        self.assertEqual(datos.microfono, "Mic/Aux")
        self.assertFalse(datos.silenciado)

    def test_sin_destino_no_revisa(self):
        gestor = _gestor()
        datos = consultas_transmision.leer_estado(gestor, "", preferido="")
        self.assertEqual(datos.problemas, ())
        gestor.revisar.assert_not_called()

    def test_llama_al_gestor_en_el_mismo_orden(self):
        gestor = _gestor()
        consultas_transmision.leer_estado(gestor, "TikTok")
        self.assertEqual(
            [llamada[0] for llamada in gestor.mock_calls],
            ["escena_al_aire", "estado_transmision", "estado_grabacion",
             "perfil_actual", "entradas_audio", "microfono_especial",
             "revisar", "silenciada"])


class TestAplicarVentana(unittest.TestCase):

    def test_cada_campo_viene_de_su_llamada(self):
        datos = consultas_transmision.aplicar_ventana(
            _gestor(), "Principal", "Champions:Ventana:juego.exe")
        self.assertIs(datos.frase, mock.sentinel.frase)
        self.assertEqual(datos.fuentes, ("Cámara", "Chat en el vídeo"))
        self.assertEqual(datos.fuente, "Chat en el vídeo")
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
            "Principal", fuente="Chat en el vídeo")
        self.assertEqual(
            [llamada[0] for llamada in gestor.mock_calls],
            ["usar_ventana", "fuentes", "instantanea", "escena_al_aire",
             "estado_transmision", "estado_grabacion", "ventanas"])


class TestDescripcionDeFuente(unittest.TestCase):

    def _snap(self):
        return obs_disposicion.SnapshotPanel(
            conectado=True, escena="Principal", ancho=460, alto=620,
            lienzo_ancho=1600, lienzo_alto=900)

    def test_sin_fuente_devuelve_solo_la_escena(self):
        texto = consultas_transmision.descripcion_de_fuente(
            "Escena: Principal. No tiene fuentes.", "", self._snap())
        self.assertEqual(texto, "Escena: Principal. No tiene fuentes.")
        self.assertNotIn("OBS: conectado", texto)

    def test_con_fuente_deja_fuera_conexion_escena_y_transparencia(self):
        texto = consultas_transmision.descripcion_de_fuente(
            "Escena: Principal.", "Chat en el vídeo", self._snap())
        self.assertIn("Fuente: Chat en el vídeo", texto)
        self.assertNotIn("OBS: conectado", texto)
        self.assertNotIn("\nEscena:", texto)
        self.assertNotIn("El fondo del panel es transparente", texto)


class TestLeerEscena(unittest.TestCase):

    def test_cada_campo_viene_de_su_llamada(self):
        datos = consultas_transmision.leer_escena(_gestor(), "Juego")
        self.assertEqual(datos.fuentes, ("Cámara", "Chat en el vídeo"))
        self.assertEqual(datos.fuente, "Chat en el vídeo")
        self.assertIs(datos.snap, mock.sentinel.snap)
        self.assertIs(datos.opciones, mock.sentinel.opciones)
        self.assertIs(datos.actual, mock.sentinel.actual)
        self.assertIs(datos.descripcion, mock.sentinel.descripcion)

    def test_pide_la_escena_dada_y_llama_en_orden(self):
        gestor = _gestor()
        consultas_transmision.leer_escena(gestor, "Juego")
        gestor.fuentes.assert_called_once_with("Juego")
        gestor.instantanea.assert_called_once_with(
            "Juego", fuente="Chat en el vídeo")
        gestor.ventanas.assert_called_once_with("Juego")
        gestor.descripcion_escena.assert_called_once_with("Juego")
        self.assertEqual(
            [llamada[0] for llamada in gestor.mock_calls],
            ["fuentes", "instantanea", "ventanas", "descripcion_escena"])


if __name__ == "__main__":
    unittest.main()
