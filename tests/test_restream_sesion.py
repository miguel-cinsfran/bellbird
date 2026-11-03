"""Pruebas de la sesión de Restream: tokens, renovación y errores."""

import threading
import time
import unittest
from unittest import mock

from bellbird.restream.sesion import (
    RechazoDeConcesion,
    Sesion,
    SesionVencida,
    SinRed,
    Tokens,
    tokens_de_respuesta,
)


ACCESO = "acceso-secreto"
RENOVACION = "renovacion-secreta"


def _dict(acceso=ACCESO, renovacion=RENOVACION, vence=0.0, permisos=""):
    return Tokens(acceso, renovacion, vence, permisos).a_dict()


def _sesion(vence, ahora, renovar=None, guardar=None):
    return Sesion(
        cargar=lambda: _dict(vence=vence),
        guardar=guardar or (lambda datos: None),
        renovar=renovar or (lambda token: {}),
        reloj=lambda: ahora,
    )


class TestTokenVigente(unittest.TestCase):

    def test_p1_no_renueva_con_mas_de_300_segundos(self):
        renovar = mock.Mock()
        sesion = _sesion(vence=1301.0, ahora=1000.0, renovar=renovar)
        self.assertEqual(sesion.token(), ACCESO)
        renovar.assert_not_called()


class TestRenovacionConcurrente(unittest.TestCase):

    def test_p2_renueva_una_vez_y_guarda_el_par_nuevo(self):
        llamadas = []
        guardados = []

        def renovar(token):
            llamadas.append(token)
            time.sleep(0.05)
            return {"access_token": "nuevo", "refresh_token": "nuevo-r",
                    "expires_in": 3600}

        sesion = _sesion(vence=1100.0, ahora=1000.0, renovar=renovar,
                         guardar=guardados.append)
        barrera = threading.Barrier(2)
        resultados = []

        def pedir():
            barrera.wait()
            resultados.append(sesion.token())

        hilos = [threading.Thread(target=pedir) for _ in range(2)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(5)

        self.assertEqual(llamadas, [RENOVACION])
        self.assertEqual(resultados, ["nuevo", "nuevo"])
        self.assertEqual(guardados[-1]["acceso"], "nuevo")
        self.assertEqual(guardados[-1]["renovacion"], "nuevo-r")


class TestRechazoDeConcesion(unittest.TestCase):

    def test_p3_invalid_grant_borra_la_sesion(self):
        guardados = []

        def renovar(token):
            raise RechazoDeConcesion("invalid_grant")

        sesion = _sesion(vence=1100.0, ahora=1000.0, renovar=renovar,
                         guardar=guardados.append)
        with self.assertRaises(SesionVencida) as contexto:
            sesion.token()

        self.assertEqual(guardados, [None])
        self.assertFalse(sesion.conectada())
        self.assertIn("conectar", str(contexto.exception).lower())


class TestFalloDeRed(unittest.TestCase):

    def test_p4_usa_el_token_si_quedan_mas_de_15_segundos(self):
        def renovar(token):
            raise OSError("sin red")

        sesion = _sesion(vence=1016.0, ahora=1000.0, renovar=renovar)
        self.assertEqual(sesion.token(), ACCESO)
        self.assertTrue(sesion.conectada())

    def test_p4_sin_margen_sale_sin_red(self):
        def renovar(token):
            raise OSError("sin red")

        sesion = _sesion(vence=1015.0, ahora=1000.0, renovar=renovar)
        with self.assertRaises(SinRed):
            sesion.token()
        self.assertTrue(sesion.conectada())


class TestRespuestaDelServidor(unittest.TestCase):

    def test_p5_acepta_los_dos_estilos_y_asume_una_hora(self):
        ahora = 1000.0
        snake = tokens_de_respuesta({
            "access_token": "a", "refresh_token": "r", "scope": "s",
            "accessTokenExpiresEpoch": 5000}, ahora)
        self.assertEqual(
            (snake.acceso, snake.renovacion, snake.vence, snake.permisos),
            ("a", "r", 5000.0, "s"))

        camel = tokens_de_respuesta({
            "accessToken": "b", "refreshToken": "q", "expires_in": 120},
            ahora)
        self.assertEqual((camel.acceso, camel.renovacion, camel.vence),
                         ("b", "q", 1120.0))

        camel_in = tokens_de_respuesta({
            "accessToken": "c", "accessTokenExpiresIn": 60}, ahora)
        self.assertEqual(camel_in.vence, 1060.0)

        sin_vencimiento = tokens_de_respuesta({"accessToken": "d"}, ahora)
        self.assertEqual(sin_vencimiento.vence, ahora + 3600)

    def test_p5_sin_token_de_acceso_falla_sin_mostrar_la_respuesta(self):
        with self.assertRaises(ValueError) as contexto:
            tokens_de_respuesta({"refresh_token": "no-debe-salir"}, 1000.0)
        self.assertNotIn("no-debe-salir", str(contexto.exception))


class TestSecretos(unittest.TestCase):

    def test_p6_repr_y_str_no_muestran_tokens(self):
        tokens = Tokens(ACCESO, RENOVACION, 1000.0, "s")
        for texto in (repr(tokens), str(tokens)):
            self.assertNotIn(ACCESO, texto)
            self.assertNotIn(RENOVACION, texto)

        sesion = Sesion(cargar=lambda: tokens.a_dict(),
                        guardar=lambda datos: None,
                        renovar=lambda token: {}, reloj=lambda: 1000.0)
        for texto in (repr(sesion), str(sesion)):
            self.assertNotIn(ACCESO, texto)
            self.assertNotIn(RENOVACION, texto)

        for error in (SesionVencida(), SinRed(),
                      RechazoDeConcesion("invalid_grant")):
            for texto in (repr(error), str(error)):
                self.assertNotIn(ACCESO, texto)
                self.assertNotIn(RENOVACION, texto)


class TestGuardadoDeTokens(unittest.TestCase):

    def test_desde_dict_descarta_lo_incompleto(self):
        self.assertIsNone(Tokens.desde_dict({"acceso": ACCESO}))
        self.assertIsNone(Tokens.desde_dict({"vence": 1000.0}))
        self.assertIsNone(Tokens.desde_dict(None))

    def test_token_de_renovacion_guardado_y_vacio_sin_sesion(self):
        conectada = _sesion(vence=1301.0, ahora=1000.0)
        self.assertEqual(conectada.token_de_renovacion(), RENOVACION)
        conectada.borrar()
        self.assertEqual(conectada.token_de_renovacion(), "")

        sin_sesion = Sesion(cargar=lambda: None, guardar=lambda datos: None,
                            renovar=lambda token: {}, reloj=lambda: 1000.0)
        self.assertEqual(sin_sesion.token_de_renovacion(), "")


if __name__ == "__main__":
    unittest.main()
