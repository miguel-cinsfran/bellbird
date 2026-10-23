"""Pruebas de los bordes de sonido de la música (bordes.py)."""

import array
import math
import subprocess
import tempfile
import unittest
from pathlib import Path

import imageio_ffmpeg

from ytchat.music.bordes import (
    VENTANA_MS,
    TASA,
    medir_bordes,
    silencio_final_ms,
    silencio_inicial_ms,
)

MUESTRAS_POR_VENTANA = TASA * VENTANA_MS // 1000


def _pcm(muestras):
    """Bytes PCM s16le mono a partir de una lista de muestras."""
    return array.array("h", muestras).tobytes()


def _silencio(ventanas, muestras_extra=0):
    total = MUESTRAS_POR_VENTANA * ventanas + muestras_extra
    return [0] * total


def _tono(ventanas, amplitud=10000, frecuencia=440.0):
    total = MUESTRAS_POR_VENTANA * ventanas
    return [
        int(amplitud * math.sin(2.0 * math.pi * frecuencia * i / TASA))
        for i in range(total)
    ]


def _wav_de_prueba(ruta, ffmpeg):
    """2 s de silencio, 30 s de tono y 3 s de silencio.

    El tono supera los 20 s y los 30 s a propósito: así la prueba distingue
    leer el principio con `-t` de leer el final con `-sseof`.
    """
    expresion = r"0.5*sin(2*PI*440*t)*gte(t\,2)*lt(t\,32)"
    argumentos = [
        ffmpeg, "-hide_banner", "-nostats", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"aevalsrc={expresion}:s={TASA}:d=35",
        "-ac", "1", "-ar", str(TASA), "-c:a", "pcm_s16le", ruta,
    ]
    resultado = subprocess.run(
        argumentos,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        timeout=30,
    )
    if resultado.returncode != 0:
        detalle = (resultado.stderr or b"").decode("utf-8", "replace")
        raise AssertionError(f"ffmpeg no generó el WAV: {detalle}")


class TestSilencioInicial(unittest.TestCase):

    def test_tres_ventanas_al_principio(self):
        pcm = _pcm(_silencio(3) + _tono(2))
        self.assertEqual(silencio_inicial_ms(pcm), 3 * VENTANA_MS)

    def test_sin_silencio_al_principio(self):
        pcm = _pcm(_tono(3))
        self.assertEqual(silencio_inicial_ms(pcm), 0)

    def test_vacio_da_cero(self):
        self.assertEqual(silencio_inicial_ms(b""), 0)

    def test_todo_silencio_da_cero(self):
        pcm = _pcm(_silencio(4))
        self.assertEqual(silencio_inicial_ms(pcm), 0)

    def test_todo_silencio_con_ultima_ventana_corta_da_cero(self):
        pcm = _pcm(_silencio(3, MUESTRAS_POR_VENTANA // 2))
        self.assertEqual(silencio_inicial_ms(pcm), 0)


class TestSilencioFinal(unittest.TestCase):

    def test_dos_ventanas_al_final(self):
        pcm = _pcm(_tono(2) + _silencio(2))
        self.assertEqual(silencio_final_ms(pcm), 2 * VENTANA_MS)

    def test_sin_silencio_al_final(self):
        pcm = _pcm(_tono(3))
        self.assertEqual(silencio_final_ms(pcm), 0)

    def test_vacio_da_cero(self):
        self.assertEqual(silencio_final_ms(b""), 0)

    def test_todo_silencio_da_cero(self):
        pcm = _pcm(_silencio(4))
        self.assertEqual(silencio_final_ms(pcm), 0)

    def test_ultima_ventana_corta_cuenta_como_entera(self):
        pcm = _pcm(_tono(1) + _silencio(1, MUESTRAS_POR_VENTANA // 2))
        self.assertEqual(silencio_final_ms(pcm), 2 * VENTANA_MS)


class TestSilencioEnLosDosLados(unittest.TestCase):

    def test_mide_cada_lado_por_separado(self):
        pcm = _pcm(_silencio(2) + _tono(3) + _silencio(4))
        self.assertEqual(silencio_inicial_ms(pcm), 2 * VENTANA_MS)
        self.assertEqual(silencio_final_ms(pcm), 4 * VENTANA_MS)


class TestPropiedadVentanasDelante(unittest.TestCase):

    def test_k_ventanas_dan_k_por_ventana_y_nunca_mas(self):
        for k in range(51):
            with self.subTest(k=k):
                pcm = _pcm(_silencio(k) + _tono(2))
                self.assertEqual(silencio_inicial_ms(pcm), k * VENTANA_MS)
                self.assertLessEqual(silencio_inicial_ms(pcm),
                                     k * VENTANA_MS)


class TestMedirBordesReal(unittest.TestCase):

    def test_wav_real_da_los_dos_bordes(self):
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        with tempfile.TemporaryDirectory() as tmp:
            ruta = str(Path(tmp) / "bordes.wav")
            _wav_de_prueba(ruta, ffmpeg)
            bordes = medir_bordes(ffmpeg, ruta)
            self.assertIsNotNone(bordes)
            self.assertGreaterEqual(bordes.silencio_inicial_ms, 1900)
            self.assertLessEqual(bordes.silencio_inicial_ms, 2100)
            self.assertGreaterEqual(bordes.silencio_final_ms, 2900)
            self.assertLessEqual(bordes.silencio_final_ms, 3100)

    def test_ruta_inexistente_da_none_sin_lanzar(self):
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        self.assertIsNone(medir_bordes(ffmpeg, "C:/no/existe/cancion.mp3"))

    def test_ffmpeg_inexistente_da_none_sin_lanzar(self):
        self.assertIsNone(
            medir_bordes("C:/no/existe/ffmpeg.exe", "C:/musica/a.mp3"))


if __name__ == "__main__":
    unittest.main()
