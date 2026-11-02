"""Pruebas de los tonos de la guía, armados en memoria.

Sin wx ni winmm: cada función devuelve un WAV completo que se abre con
`wave` de la biblioteca estándar.
"""

import io
import unittest
import wave

import numpy as np

from bellbird.camera import tono_guia


def _muestras(datos):
    with wave.open(io.BytesIO(datos), "rb") as wav:
        canales = wav.getnchannels()
        ancho = wav.getsampwidth()
        frecuencia = wav.getframerate()
        cuadros = wav.readframes(wav.getnframes())
    enteros = np.frombuffer(cuadros, dtype="<i2")
    return canales, ancho, frecuencia, enteros.reshape(-1, canales)


class TestPitido(unittest.TestCase):

    def test_es_un_wav_estereo_de_60_ms(self):
        canales, ancho, frecuencia, muestras = _muestras(
            tono_guia.pitido(0.0, 440.0, "normal"))
        self.assertEqual(canales, 2)
        self.assertEqual(ancho, 2)
        self.assertEqual(frecuencia, 44100)
        self.assertAlmostEqual(len(muestras) / frecuencia, 0.06, delta=0.002)

    def test_el_paneo_izquierdo_calla_el_canal_derecho(self):
        _, _, _, muestras = _muestras(tono_guia.pitido(-1.0, 440.0, "normal"))
        self.assertGreater(int(np.abs(muestras[:, 0]).max()), 1000)
        self.assertEqual(int(np.abs(muestras[:, 1]).max()), 0)

    def test_el_paneo_derecho_calla_el_canal_izquierdo(self):
        _, _, _, muestras = _muestras(tono_guia.pitido(1.0, 440.0, "normal"))
        self.assertGreater(int(np.abs(muestras[:, 1]).max()), 1000)
        self.assertEqual(int(np.abs(muestras[:, 0]).max()), 0)

    def test_un_timbre_desconocido_suena_como_el_normal(self):
        self.assertEqual(tono_guia.pitido(0.2, 440.0, "raro"),
                         tono_guia.pitido(0.2, 440.0, "normal"))


class TestTonoCentro(unittest.TestCase):

    def test_empieza_y_termina_en_cero(self):
        _, _, _, muestras = _muestras(tono_guia.tono_centro("normal"))
        self.assertEqual(muestras[0].tolist(), [0, 0])
        self.assertEqual(muestras[-1].tolist(), [0, 0])

    def test_dura_medio_segundo_y_suena_centrado(self):
        _, _, frecuencia, muestras = _muestras(
            tono_guia.tono_centro("normal"))
        self.assertAlmostEqual(len(muestras) / frecuencia, 0.5, delta=0.002)
        self.assertAlmostEqual(int(muestras[:, 0].max()),
                               int(muestras[:, 1].max()), delta=2)


class TestMuestra(unittest.TestCase):

    def test_los_tres_timbres_dan_muestras_distintas(self):
        datos = {timbre: tono_guia.muestra(timbre)
                 for timbre in tono_guia.TIMBRES}
        self.assertEqual(len(set(datos.values())), len(tono_guia.TIMBRES))

    def test_la_lista_de_timbres_es_la_esperada(self):
        self.assertEqual(tono_guia.TIMBRES, ("normal", "calido", "8bits"))

    def test_ningun_timbre_pasa_del_pico_de_los_wav_de_hoy(self):
        pico_hoy = int(round(0.6 * 32767))
        for timbre in tono_guia.TIMBRES:
            with self.subTest(timbre=timbre):
                for datos in (tono_guia.pitido(0.0, 440.0, timbre),
                              tono_guia.tono_centro(timbre),
                              tono_guia.muestra(timbre)):
                    _, _, _, muestras = _muestras(datos)
                    self.assertLessEqual(int(np.abs(muestras).max()),
                                         pico_hoy)


if __name__ == "__main__":
    unittest.main()
