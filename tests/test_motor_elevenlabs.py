"""Tests del motor de ElevenLabs: reproduce un WAV real por MCI y lo borra."""

import io
import tempfile
import time
import unittest
import wave
from pathlib import Path

from tests.pseudo_prueba import con_pseudo
from bellbird.core import paths
from bellbird.core.idioma import _
from bellbird.voice import elevenlabs
from bellbird.voice.motor_elevenlabs import MotorElevenLabs
from bellbird.voice.motores import MotorNoDisponible
from tests.rutas_temporales import redirigir_rutas


def _wav_silencio(segundos: float = 0.5, tasa: int = 8000) -> bytes:
    """WAV mono de silencio, válido para MCI `type waveaudio`."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(tasa)
        w.writeframes(b"\x00\x00" * int(tasa * segundos))
    return buffer.getvalue()


class _ClienteFalso:
    def __init__(self, wav: bytes):
        self._wav = wav
        self.llamadas = []

    def voces(self):
        return [("v1", "Voz Uno"), ("v2", "Voz Dos")]

    def sintetizar(self, texto, voice_id, velocidad_pct):
        self.llamadas.append((texto, voice_id, velocidad_pct))
        return self._wav

    def saldo(self):
        return (0, 30000)


class _ClienteQueFalla(_ClienteFalso):
    def voces(self):
        raise elevenlabs.ElevenLabsError(
            "red", "No se pudo conectar con ElevenLabs.")


class TestCreacion(unittest.TestCase):

    def test_sin_clave_no_se_crea(self):
        with self.assertRaises(MotorNoDisponible):
            MotorElevenLabs("")

    def test_si_voces_lanza_no_se_crea(self):
        cliente = _ClienteQueFalla(_wav_silencio())
        with self.assertRaises(MotorNoDisponible):
            MotorElevenLabs("k", cliente=cliente)

    def test_carga_las_voces(self):
        motor = MotorElevenLabs("k", cliente=_ClienteFalso(_wav_silencio()))
        self.assertEqual(motor.motor, "elevenlabs")
        self.assertEqual(motor.voces(), ["Voz Uno", "Voz Dos"])
        self.assertTrue(motor.elegir_voz(1))
        self.assertFalse(motor.elegir_voz(9))
        motor.cerrar()


class TestReproduccion(unittest.TestCase):
    """MCI de verdad, con volumen 0 para no sonar."""

    def test_hablar_reproduce_y_borra_al_terminar(self):
        with tempfile.TemporaryDirectory() as tmp:
            with redirigir_rutas(tmp):
                motor = MotorElevenLabs(
                    "k", cliente=_ClienteFalso(_wav_silencio(0.4)))
                motor.fijar_volumen(0)
                carpeta = paths.audio_temporal()

                self.assertTrue(motor.hablar("hola"))
                self.assertTrue(motor.hablando())

                fin = time.monotonic() + 3.0
                while motor.hablando() and time.monotonic() < fin:
                    time.sleep(0.02)
                self.assertFalse(motor.hablando())
                # Al terminar, el alias se cierra y el archivo se borra.
                self.assertEqual(list(carpeta.iterdir()), [])
                self.assertEqual(motor.caracteres_usados(), 4)
                motor.cerrar()

    def test_parar_a_mitad_borra_el_archivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            with redirigir_rutas(tmp):
                motor = MotorElevenLabs(
                    "k", cliente=_ClienteFalso(_wav_silencio(3.0)))
                motor.fijar_volumen(0)
                carpeta = paths.audio_temporal()

                self.assertTrue(motor.hablar("hola"))
                self.assertEqual(len(list(carpeta.iterdir())), 1)
                motor.parar()
                self.assertFalse(motor.hablando())
                self.assertEqual(list(carpeta.iterdir()), [])
                motor.cerrar()

    def test_cerrar_borra_lo_que_quede(self):
        with tempfile.TemporaryDirectory() as tmp:
            with redirigir_rutas(tmp):
                motor = MotorElevenLabs(
                    "k", cliente=_ClienteFalso(_wav_silencio(3.0)))
                motor.fijar_volumen(0)
                carpeta = paths.audio_temporal()
                self.assertTrue(motor.hablar("hola"))
                motor.cerrar()
                self.assertEqual(list(carpeta.iterdir()), [])

    def test_pasar_la_velocidad_al_cliente(self):
        with tempfile.TemporaryDirectory() as tmp:
            with redirigir_rutas(tmp):
                cliente = _ClienteFalso(_wav_silencio(0.05))
                motor = MotorElevenLabs("k", cliente=cliente)
                motor.fijar_volumen(0)
                motor.fijar_velocidad(100)
                motor.hablar("hola")
                self.assertEqual(cliente.llamadas, [("hola", "v1", 100)])
                motor.cerrar()

    def test_texto_vacio_no_sintetiza(self):
        with tempfile.TemporaryDirectory() as tmp:
            with redirigir_rutas(tmp):
                cliente = _ClienteFalso(_wav_silencio(0.05))
                motor = MotorElevenLabs("k", cliente=cliente)
                self.assertFalse(motor.hablar("   "))
                self.assertEqual(cliente.llamadas, [])
                motor.cerrar()


class TestPseudoTextos(unittest.TestCase):
    """Bajo pseudotraducción, cada frase al usuario sale marcada."""

    def test_errores_salen_marcados(self):
        from bellbird.voice import motor_elevenlabs
        with con_pseudo():
            with self.assertRaises(MotorNoDisponible) as sin_clave:
                MotorElevenLabs("")
            with self.assertRaises(MotorNoDisponible) as sin_voces:
                MotorElevenLabs("k", cliente=_ClienteVacio(_wav_silencio()))
            marcados = [_(motor_elevenlabs._ERROR_SIN_CLAVE),
                        _(motor_elevenlabs._ERROR_SIN_VOCES)]
        for contexto in (sin_clave, sin_voces):
            with self.subTest(mensaje=str(contexto.exception)):
                self.assertTrue(str(contexto.exception).startswith("[¡"),
                                str(contexto.exception))
        for texto in marcados:
            with self.subTest(texto=texto):
                self.assertTrue(texto.startswith("[¡"), texto)


class _ClienteVacio(_ClienteFalso):
    """Sin voces, para el camino de _ERROR_SIN_VOCES."""

    def voces(self):
        return []


if __name__ == "__main__":
    unittest.main()
