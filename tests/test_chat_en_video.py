"""Pruebas de cuándo y cómo existe el chat en el vídeo en OBS."""

import unittest
from unittest import mock

from guyrapu.obs import chat_en_video
from guyrapu.obs.fuente_chat import NOMBRE_FUENTE


CHAT = {"inputName": NOMBRE_FUENTE, "inputKind": "browser_source"}
OTRO_NAVEGADOR = {"inputName": "Chat YTChat", "inputKind": "browser_source"}
IMAGEN = {"inputName": NOMBRE_FUENTE, "inputKind": "image_source"}


class GestorFalso:

    def __init__(self, fuentes):
        self._fuentes = fuentes
        self.llamadas = []

    def fuentes(self, escena):
        self.llamadas.append(("fuentes", escena))
        return self._fuentes

    def asegurar_fuente(self, *args):
        self.llamadas.append(("asegurar_fuente",) + args)


class TestTieneFuente(unittest.TestCase):

    def test_la_fuente_del_chat_es_la_del_nombre_y_tipo_conocidos(self):
        self.assertTrue(chat_en_video.tiene_fuente([CHAT]))

    def test_otro_navegador_con_otro_nombre_no_cuenta(self):
        self.assertFalse(chat_en_video.tiene_fuente([OTRO_NAVEGADOR]))

    def test_una_fuente_con_el_mismo_nombre_que_no_es_navegador_no_cuenta(self):
        self.assertFalse(chat_en_video.tiene_fuente([IMAGEN]))

    def test_sin_entradas_no_la_tiene(self):
        self.assertFalse(chat_en_video.tiene_fuente(()))


class TestDecidir(unittest.TestCase):

    def test_enciende_si_obs_tiene_la_fuente_y_el_servicio_esta_apagado(self):
        self.assertEqual(
            chat_en_video.decidir(True, False, True), chat_en_video.ENCENDER)

    def test_apaga_si_obs_no_tiene_la_fuente_y_el_servicio_esta_encendido(self):
        self.assertEqual(
            chat_en_video.decidir(False, True, True), chat_en_video.APAGAR)

    def test_no_hace_nada_si_todo_esta_encendido(self):
        self.assertEqual(
            chat_en_video.decidir(True, True, True), chat_en_video.NADA)

    def test_no_hace_nada_si_todo_esta_apagado(self):
        self.assertEqual(
            chat_en_video.decidir(False, False, True), chat_en_video.NADA)

    def test_sin_obs_conectado_no_enciende(self):
        self.assertEqual(
            chat_en_video.decidir(True, False, False), chat_en_video.NADA)

    def test_sin_obs_conectado_no_apaga(self):
        self.assertEqual(
            chat_en_video.decidir(False, True, False), chat_en_video.NADA)


class TestPuertoDelPanel(unittest.TestCase):

    def test_usa_el_guardado_si_el_servicio_esta_apagado(self):
        with mock.patch.object(chat_en_video.overlay_servidor,
                               "puerto_actual", return_value=None):
            self.assertEqual(
                chat_en_video.puerto_del_panel({"overlay_puerto": 9000}), 9000)

    def test_prefiere_el_del_servicio_encendido(self):
        with mock.patch.object(chat_en_video.overlay_servidor,
                               "puerto_actual", return_value=9001):
            self.assertEqual(
                chat_en_video.puerto_del_panel({"overlay_puerto": 9000}), 9001)

    def test_sin_config_usa_el_de_fabrica(self):
        with mock.patch.object(chat_en_video.overlay_servidor,
                               "puerto_actual", return_value=None):
            self.assertEqual(chat_en_video.puerto_del_panel(), 8730)


class TestAgregarFuente(unittest.TestCase):

    def test_agrega_con_la_direccion_y_el_tamano_del_panel(self):
        gestor = GestorFalso(())
        self.assertTrue(chat_en_video.agregar_fuente(gestor, "Principal", 9000))
        self.assertEqual(
            gestor.llamadas,
            [("fuentes", "Principal"),
             ("asegurar_fuente", "Principal",
              "http://127.0.0.1:9000/chat", 460, 620)])

    def test_si_ya_esta_no_la_repone(self):
        gestor = GestorFalso((NOMBRE_FUENTE,))
        self.assertFalse(chat_en_video.agregar_fuente(gestor, "Principal", 8730))
        self.assertEqual(gestor.llamadas, [("fuentes", "Principal")])


if __name__ == "__main__":
    unittest.main()
