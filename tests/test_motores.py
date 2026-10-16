"""Tests del envoltorio de Prism (motores.MotorPrism)."""

import time
import unittest

from prism import PrismError
from prism.common import PrismAlreadyPausedError, PrismNotPausedError

from ytchat.voice import escala_voz
from ytchat.voice.motores import MotorNoDisponible, MotorPrism, listar_voces


class _BackendFalso:
    VOCES = ["Voz A", "Voz B"]

    def __init__(self):
        self.speaks = []
        self.rate = 0.5
        self.volume = 1.0
        self.pitch = 0.5
        self.voz = 0
        self._pausas = 0
        self._speaking = False

    def speak(self, texto, interrupt=False):
        self.speaks.append((texto, interrupt))
        self._speaking = True

    @property
    def speaking(self):
        return self._speaking

    def stop(self):
        self._speaking = False

    def pause(self):
        if self._pausas:
            raise PrismAlreadyPausedError(0, "ya en pausa")
        self._pausas += 1

    def resume(self):
        if not self._pausas:
            raise PrismNotPausedError(0, "no estaba en pausa")
        self._pausas = 0

    def refresh_voices(self):
        pass

    @property
    def voices_count(self):
        return len(self.VOCES)

    def get_voice_name(self, i):
        return self.VOCES[i]

    @property
    def voice(self):
        return self.voz

    @voice.setter
    def voice(self, i):
        self.voz = i


class _ContextoFalso:
    def __init__(self, backend=None, error=None):
        self._backend = backend
        self._error = error

    def create(self, backend_id):
        if self._error is not None:
            raise self._error
        return self._backend


class TestMotorPrismConContextoFalso(unittest.TestCase):

    def _motor(self, backend=None, error=None):
        return MotorPrism("sapi", lambda: _ContextoFalso(backend, error))

    def test_motor_desconocido(self):
        with self.assertRaises(MotorNoDisponible):
            MotorPrism("inexistente", lambda: _ContextoFalso(_BackendFalso()))

    def test_create_que_falla(self):
        with self.assertRaises(MotorNoDisponible):
            self._motor(error=PrismError(0, "falla de prueba"))

    def test_hablar_vacio_no_llama_a_speak(self):
        backend = _BackendFalso()
        motor = self._motor(backend=backend)
        self.assertFalse(motor.hablar(""))
        self.assertEqual(backend.speaks, [])

    def test_pausar_dos_veces_no_lanza(self):
        backend = _BackendFalso()
        motor = self._motor(backend=backend)
        motor.pausar()
        motor.pausar()   # el backend lanza PrismAlreadyPausedError; se ignora
        self.assertEqual(backend._pausas, 1)

    def test_tras_cerrar_todo_es_noop(self):
        backend = _BackendFalso()
        motor = self._motor(backend=backend)
        motor.cerrar()
        self.assertFalse(motor.hablar("hola"))
        self.assertFalse(motor.hablando())
        self.assertFalse(motor.elegir_voz(0))
        self.assertEqual(backend.speaks, [])
        motor.parar()
        motor.fijar_velocidad(80)
        self.assertEqual(backend.rate, 0.5)

    def test_fijar_velocidad_usa_la_escala(self):
        backend = _BackendFalso()
        motor = self._motor(backend=backend)
        motor.fijar_velocidad(65)
        self.assertEqual(backend.rate,
                         escala_voz.velocidad_a_prism("sapi", 65))

    def test_voces_y_elegir_voz(self):
        backend = _BackendFalso()
        motor = self._motor(backend=backend)
        self.assertEqual(motor.voces(), ["Voz A", "Voz B"])
        self.assertTrue(motor.elegir_voz(1))
        self.assertEqual(backend.voz, 1)
        self.assertFalse(motor.elegir_voz(9))


class TestMotorPrismReal(unittest.TestCase):

    def _crear(self, motor):
        try:
            return MotorPrism(motor)
        except MotorNoDisponible as exc:
            self.skipTest(f"El motor {motor} no está disponible: {exc}")

    def test_sapi_real(self):
        motor = self._crear("sapi")
        try:
            motor.fijar_volumen(0)
            self.assertGreaterEqual(len(motor.voces()), 1)
            self.assertTrue(motor.hablar(
                "Prueba de voz con volumen cero, una frase larga para que "
                "el motor tenga tiempo de ponerse a hablar."))
            limite = time.monotonic() + 1.0
            while not motor.hablando() and time.monotonic() < limite:
                time.sleep(0.01)
            self.assertTrue(motor.hablando())
            motor.parar()
            self.assertFalse(motor.hablando())
            for pct in range(0, 101, 5):
                motor.fijar_velocidad(pct)
                leido = round((motor._backend.rate - 0.5) * 20)
                self.assertEqual(leido, pct // 5 - 10, pct)
        finally:
            motor.cerrar()

    def test_onecore_real(self):
        motor = self._crear("onecore")
        try:
            motor.fijar_volumen(0)
            self.assertGreaterEqual(len(motor.voces()), 1)
            self.assertTrue(motor.hablar(
                "Prueba de voz con volumen cero en OneCore."))
            motor.parar()
            self.assertFalse(motor.hablando())
            for pct in range(0, 101, 5):
                motor.fijar_velocidad(pct)
                self.assertAlmostEqual(motor._backend.rate, pct / 100, places=5)
        finally:
            motor.cerrar()

    def test_listar_voces_real(self):
        motor = self._crear("sapi")
        propias = motor.voces()
        motor.cerrar()
        self.assertEqual(listar_voces("sapi"), propias)

    def test_listar_voces_inexistente(self):
        self.assertEqual(listar_voces("inexistente"), [])


if __name__ == "__main__":
    unittest.main()
