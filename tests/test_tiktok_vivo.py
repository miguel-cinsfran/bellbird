"""Tests de tiktok_vivo sin red: consultar falso y usuarios puros."""

import sys
import threading
import types
import unittest
from unittest import mock

from ytchat.capture import tiktok_vivo
from ytchat.capture.tiktok_vivo import (
    ResultadoEspera, esperar_en_vivo, esta_en_vivo, url_directo,
    usuario_tiktok)


class RelojFalso:
    def __init__(self):
        self.ahora = 0.0
        self.siestecitas = []

    def reloj(self):
        return self.ahora

    def dormir(self, segundos):
        self.siestecitas.append(segundos)
        self.ahora += segundos


def _modulo_tiktok_que_falla(error):
    modulo = types.ModuleType("TikTokLive")

    class ClienteFalso:
        def __init__(self, unique_id=None):
            pass

        async def is_live(self):
            raise error

    modulo.TikTokLiveClient = ClienteFalso
    return modulo


class EsperarEnVivoTest(unittest.TestCase):
    def test_llega_a_true(self):
        reloj = RelojFalso()
        respuestas = [False, False, True]
        llamadas = []

        def consultar(usuario):
            llamadas.append(usuario)
            return respuestas.pop(0)

        resultado = esperar_en_vivo(
            "szeiryugaming", cada=5.0, limite=90.0, consultar=consultar,
            dormir=reloj.dormir, reloj=reloj.reloj)
        self.assertTrue(resultado.en_vivo)
        self.assertFalse(resultado.cuenta_sin_directos)
        self.assertTrue(resultado)
        self.assertEqual(llamadas, ["szeiryugaming"] * 3)
        self.assertEqual(reloj.siestecitas, [5.0, 5.0])

    def test_se_agota(self):
        reloj = RelojFalso()
        llamadas = []

        def consultar(usuario):
            llamadas.append(usuario)
            return False

        resultado = esperar_en_vivo(
            "szeiryugaming", cada=5.0, limite=12.0, consultar=consultar,
            dormir=reloj.dormir, reloj=reloj.reloj)
        self.assertFalse(resultado.en_vivo)
        self.assertFalse(resultado.cuenta_sin_directos)
        self.assertFalse(resultado)
        self.assertTrue(llamadas)
        self.assertGreaterEqual(reloj.ahora, 12.0)

    def test_la_parada_corta(self):
        reloj = RelojFalso()
        parada = threading.Event()

        def consultar(usuario):
            return False

        def dormir(segundos):
            parada.set()
            reloj.dormir(segundos)

        resultado = esperar_en_vivo(
            "szeiryugaming", parada=parada, cada=5.0, limite=90.0,
            consultar=consultar, dormir=dormir, reloj=reloj.reloj)
        self.assertFalse(resultado.en_vivo)
        self.assertFalse(resultado)

    def test_nunca_mas_seguido_que_cada(self):
        reloj = RelojFalso()
        tiempos = []

        def consultar(usuario):
            tiempos.append(reloj.ahora)
            return False

        esperar_en_vivo("szeiryugaming", cada=5.0, limite=11.0,
                        consultar=consultar, dormir=reloj.dormir,
                        reloj=reloj.reloj)
        for primera, segunda in zip(tiempos, tiempos[1:]):
            self.assertGreaterEqual(segunda - primera, 5.0)

    def test_valueerror_sigue_esperando_hasta_verlo(self):
        reloj = RelojFalso()
        respuestas = [ValueError("sin directos"), ValueError("sin directos"),
                      True]

        def consultar(usuario):
            respuesta = respuestas.pop(0)
            if isinstance(respuesta, Exception):
                raise respuesta
            return respuesta

        resultado = esperar_en_vivo(
            "szeiryugaming", cada=5.0, limite=90.0, consultar=consultar,
            dormir=reloj.dormir, reloj=reloj.reloj)
        self.assertTrue(resultado.en_vivo)
        self.assertFalse(resultado.cuenta_sin_directos)

    def test_todo_valueerror_marca_cuenta_sin_directos(self):
        reloj = RelojFalso()

        def consultar(usuario):
            raise ValueError("sin directos")

        resultado = esperar_en_vivo(
            "szeiryugaming", cada=5.0, limite=12.0, consultar=consultar,
            dormir=reloj.dormir, reloj=reloj.reloj)
        self.assertFalse(resultado.en_vivo)
        self.assertTrue(resultado.cuenta_sin_directos)
        self.assertIsInstance(resultado, ResultadoEspera)

    def test_mecla_de_valueerror_y_falso_no_marca_cuenta(self):
        reloj = RelojFalso()
        respuestas = [ValueError("sin directos"), False]

        def consultar(usuario):
            respuesta = respuestas.pop(0) if respuestas else False
            if isinstance(respuesta, Exception):
                raise respuesta
            return respuesta

        resultado = esperar_en_vivo(
            "szeiryugaming", cada=5.0, limite=12.0, consultar=consultar,
            dormir=reloj.dormir, reloj=reloj.reloj)
        self.assertFalse(resultado.en_vivo)
        self.assertFalse(resultado.cuenta_sin_directos)


class UsuarioTiktokTest(unittest.TestCase):
    def test_casos(self):
        casos = {"@szeiryugaming": "szeiryugaming",
                 "szeiryugaming": "szeiryugaming",
                 "https://www.tiktok.com/@szeiryugaming": "szeiryugaming",
                 "https://www.tiktok.com/@szeiryugaming/live": "szeiryugaming",
                 "http://m.tiktok.com/@szeiryugaming": "szeiryugaming",
                 "": "",
                 "@": "",
                 "con espacios no": "",
                 "https://ejemplo.com/@alguien": ""}
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(usuario_tiktok(texto), esperado)

    def test_url_directo(self):
        self.assertEqual(url_directo("szeiryugaming"),
                         "https://www.tiktok.com/@szeiryugaming/live")


class EstaEnVivoTest(unittest.TestCase):
    def test_usuario_inexistente_da_valueerror(self):
        error = type("UserNotFoundError", (Exception,), {})("no está")
        modulo = _modulo_tiktok_que_falla(error)
        with mock.patch.dict(sys.modules, {"TikTokLive": modulo}):
            with self.assertRaisesRegex(
                    ValueError, "TikTok no tiene directos de la cuenta"):
                esta_en_vivo("nadie000")

    def test_error_de_red_da_false(self):
        modulo = _modulo_tiktok_que_falla(RuntimeError("red caída"))
        with mock.patch.dict(sys.modules, {"TikTokLive": modulo}):
            self.assertFalse(esta_en_vivo("alguien"))


if __name__ == "__main__":
    unittest.main()
