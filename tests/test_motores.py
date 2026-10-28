"""Tests del envoltorio de Prism (motores.MotorPrism)."""

import time
import unittest
from unittest import mock

from prism import PrismError
from prism.common import PrismAlreadyPausedError, PrismNotPausedError

from tests.pseudo_prueba import con_pseudo
from ytchat.core.idioma import _
from ytchat.voice import escala_voz
from ytchat.voice.motores import (
    NOMBRES, MotorNoDisponible, MotorPrism, crear_motor, listar_voces,
)


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

    def test_hablar_no_interrumpe(self):
        # La purga y el corte de frase los maneja el worker con parar(); Prism
        # no debe interrumpir por su cuenta al encolar.
        backend = _BackendFalso()
        motor = self._motor(backend=backend)
        self.assertTrue(motor.hablar("hola"))
        self.assertEqual(backend.speaks, [("hola", False)])

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


class TestPseudoTextos(unittest.TestCase):
    """Bajo pseudotraducción, cada frase al usuario sale marcada."""

    def test_errores_salen_marcados(self):
        with con_pseudo():
            with self.assertRaises(MotorNoDisponible) as desconocido:
                MotorPrism("inexistente", lambda: _ContextoFalso(_BackendFalso()))
            with self.assertRaises(MotorNoDisponible) as sin_prism:
                with mock.patch.dict("sys.modules", {"prism": None}):
                    MotorPrism("sapi", lambda: _ContextoFalso(_BackendFalso()))
            with self.assertRaises(MotorNoDisponible) as sin_motor:
                MotorPrism("sapi", lambda: _ContextoFalso(
                    _BackendFalso(), PrismError(0, "falla de prueba")))
        for contexto in (desconocido, sin_prism, sin_motor):
            with self.subTest(mensaje=str(contexto.exception)):
                self.assertTrue(str(contexto.exception).startswith("[¡"),
                                str(contexto.exception))

    def test_nombres_salen_marcados(self):
        with con_pseudo():
            marcados = [_(NOMBRES[motor]) for motor in
                        ("sapi", "onecore", "elevenlabs")]
        for texto in marcados:
            with self.subTest(texto=texto):
                self.assertTrue(texto.startswith("[¡"), texto)


class TestCrearMotor(unittest.TestCase):

    def test_sapi_devuelve_motor_prism(self):
        with mock.patch("ytchat.voice.motores.MotorPrism") as prism:
            crear_motor("sapi")
        prism.assert_called_once_with("sapi")

    def test_elevenlabs_sin_clave_da_no_disponible(self):
        with mock.patch("ytchat.youtube.credenciales.cargar",
                        return_value={"elevenlabs_clave": ""}):
            with self.assertRaises(MotorNoDisponible):
                crear_motor("elevenlabs")

    def test_elevenlabs_usa_la_clave_recibida(self):
        with mock.patch("ytchat.voice.motor_elevenlabs.MotorElevenLabs") as motor:
            crear_motor("elevenlabs", clave_elevenlabs="mi-clave")
        motor.assert_called_once_with("mi-clave")

    def test_elevenlabs_lee_la_clave_de_credenciales(self):
        with mock.patch("ytchat.youtube.credenciales.cargar",
                        return_value={"elevenlabs_clave": "guardada"}), \
             mock.patch("ytchat.voice.motor_elevenlabs.MotorElevenLabs") as motor:
            crear_motor("elevenlabs")
        motor.assert_called_once_with("guardada")


class TestListarVocesElevenlabs(unittest.TestCase):

    def test_sin_clave_es_vacio(self):
        with mock.patch("ytchat.youtube.credenciales.cargar",
                        return_value={"elevenlabs_clave": ""}):
            self.assertEqual(listar_voces("elevenlabs"), [])

    def test_devuelve_los_nombres_y_cierra_el_motor(self):
        motor = mock.Mock()
        motor.voces.return_value = ["Voz A", "Voz B"]
        with mock.patch("ytchat.voice.motores.crear_motor",
                        return_value=motor):
            self.assertEqual(listar_voces("elevenlabs"), ["Voz A", "Voz B"])
        motor.cerrar.assert_called_once()


if __name__ == "__main__":
    unittest.main()
