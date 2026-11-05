"""Pruebas de `sonido_memoria`, la frontera nativa con `PlaySoundW`.

Suenan WAV en silencio de verdad: si `PlaySoundW` con `SND_MEMORY` y
`SND_ASYNC` no funciona en esta PC, tienen que fallar. Abren audio, no
ventanas.
"""

import io
import sys
import unittest
import wave
from unittest import mock

from guyrapu.voice import sonido_memoria, sound_player


def _wav_silencio(duracion=0.05):
    salida = io.BytesIO()
    with wave.open(salida, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(b"\0\0\0\0" * int(44100 * duracion))
    return salida.getvalue()


@unittest.skipUnless(sys.platform == "win32", "PlaySoundW es de Windows")
class TestSonidoMemoria(unittest.TestCase):

    def setUp(self):
        self.wav = _wav_silencio()
        self.addCleanup(sonido_memoria.detener)

    def test_suena_en_silencio_sin_bucle_y_detener_suelta_la_referencia(self):
        with mock.patch.object(sound_player, "puede_sonar", return_value=True):
            self.assertTrue(sonido_memoria.reproducir(self.wav))
        self.assertIsNotNone(sonido_memoria._sonando)
        sonido_memoria.detener()
        self.assertIsNone(sonido_memoria._sonando)

    def test_suena_en_silencio_en_bucle_y_detener_corta(self):
        with mock.patch.object(sound_player, "puede_sonar", return_value=True):
            self.assertTrue(sonido_memoria.reproducir(self.wav, bucle=True))
        self.assertIsNotNone(sonido_memoria._sonando)
        sonido_memoria.detener()
        self.assertIsNone(sonido_memoria._sonando)

    def test_con_los_sonidos_apagados_no_llama_a_playsound(self):
        falso = mock.Mock()
        falso.PlaySoundW.return_value = True
        with mock.patch.object(sound_player, "puede_sonar",
                               return_value=False), \
                mock.patch.object(sonido_memoria, "_winmm", falso):
            self.assertFalse(sonido_memoria.reproducir(self.wav))
        falso.PlaySoundW.assert_not_called()
        self.assertIsNone(sonido_memoria._sonando)


if __name__ == "__main__":
    unittest.main()
