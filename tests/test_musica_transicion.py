"""Pruebas del movimiento de volúmenes durante un cambio de tema."""

import ctypes
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from bellbird.downloads import ffmpeg_bin
from bellbird.music import transicion
from bellbird.music.bordes import Bordes
from bellbird.music.transicion import Transiciones
from bellbird.player import motor_vlc


def esperar(condicion, plazo=5.0):
    fin = time.monotonic() + plazo
    while time.monotonic() < fin:
        if condicion():
            return True
        time.sleep(0.01)
    return condicion()


class ReproductorFalso:
    """Reproductor con el tiempo bajo control de la prueba."""

    def __init__(self, largo=0, tiempo=0):
        self.largo = largo
        self.tiempo = tiempo
        self.volumen = None
        self.volumenes = []
        self.saltos = []
        self.consultas_tiempo = 0
        self.consultas_largo = 0

    def get_time(self):
        self.consultas_tiempo += 1
        return self.tiempo

    def get_length(self):
        self.consultas_largo += 1
        return self.largo

    def set_time(self, ms):
        self.tiempo = ms
        self.saltos.append(ms)

    def audio_set_volume(self, valor):
        self.volumen = valor
        self.volumenes.append(valor)


class TestTransiciones(unittest.TestCase):

    def _crear(self, **kwargs):
        kwargs.setdefault("cruce_de", lambda: 6)
        objeto = Transiciones(**kwargs)
        self.addCleanup(objeto.cerrar)
        return objeto

    def test_el_cruce_termina_con_la_que_entra_a_su_volumen(self):
        objeto = self._crear()
        sale = ReproductorFalso()
        entra = ReproductorFalso()
        soltados = []

        objeto.cruzar(sale, 100, entra, 80, 150, soltados.append)

        self.assertTrue(esperar(lambda: bool(soltados)))
        self.assertEqual(soltados, [sale])
        self.assertEqual(entra.volumen, 80)
        self.assertFalse(objeto.en_fundido(entra))

    def test_olvidar_la_que_sale_no_le_mueve_mas_el_volumen(self):
        objeto = self._crear()
        sale = ReproductorFalso()
        entra = ReproductorFalso()
        soltados = []

        objeto.cruzar(sale, 100, entra, 80, 2000, soltados.append)
        time.sleep(0.1)
        objeto.olvidar(sale)
        movimientos = len(sale.volumenes)
        time.sleep(0.2)

        self.assertEqual(len(sale.volumenes), movimientos)
        self.assertEqual(soltados, [])
        self.assertFalse(objeto.en_fundido(entra))

    def test_terminar_ya_a_mitad_deja_lo_mismo(self):
        objeto = self._crear()
        sale = ReproductorFalso()
        entra = ReproductorFalso()
        soltados = []

        objeto.cruzar(sale, 100, entra, 80, 2000, soltados.append)
        time.sleep(0.12)
        objeto.terminar_ya()

        self.assertEqual(soltados, [sale])
        self.assertEqual(entra.volumen, 80)
        self.assertFalse(objeto.en_fundido(entra))
        objeto.terminar_ya()
        self.assertEqual(soltados, [sale])

    def test_al_por_terminar_se_llama_una_sola_vez(self):
        objeto = self._crear(
            medir=lambda ruta_ffmpeg, ruta: Bordes(0, 0))
        with tempfile.NamedTemporaryFile(delete=False) as archivo:
            ruta = archivo.name
        self.addCleanup(os.remove, ruta)
        reproductor = ReproductorFalso(largo=3000, tiempo=1000)
        avisos = []

        objeto.vigilar(reproductor, 7, ruta, avisos.append)
        self.assertTrue(esperar(lambda: reproductor.consultas_largo > 0))
        reproductor.tiempo = 2500
        self.assertTrue(esperar(lambda: avisos == [7]))
        reproductor.tiempo = 2900
        time.sleep(0.15)
        self.assertEqual(avisos, [7])

    def test_el_silencio_inicial_se_saltea(self):
        objeto = self._crear(
            medir=lambda ruta_ffmpeg, ruta: Bordes(1500, 0))
        with tempfile.NamedTemporaryFile(delete=False) as archivo:
            ruta = archivo.name
        self.addCleanup(os.remove, ruta)
        reproductor = ReproductorFalso(largo=5000, tiempo=0)

        objeto.vigilar(reproductor, 1, ruta, lambda ficha: None)

        self.assertTrue(esperar(lambda: reproductor.saltos == [1500]))

    def test_con_cero_segundos_no_mide_ni_vigila(self):
        medidas = []
        objeto = self._crear(
            cruce_de=lambda: 0,
            medir=lambda ruta_ffmpeg, ruta: medidas.append(ruta) or Bordes(0, 0))
        with tempfile.NamedTemporaryFile(delete=False) as archivo:
            ruta = archivo.name
        self.addCleanup(os.remove, ruta)
        reproductor = ReproductorFalso(largo=5000, tiempo=0)

        objeto.vigilar(reproductor, 1, ruta, lambda ficha: None)
        time.sleep(0.15)

        self.assertEqual(medidas, [])
        self.assertEqual(reproductor.consultas_tiempo, 0)
        self.assertEqual(reproductor.consultas_largo, 0)

    def test_los_bordes_se_miden_una_vez_por_archivo(self):
        medidas = []
        objeto = self._crear(
            medir=lambda ruta_ffmpeg, ruta: medidas.append(ruta) or Bordes(0, 0))
        with tempfile.NamedTemporaryFile(delete=False) as archivo:
            ruta = archivo.name
        self.addCleanup(os.remove, ruta)

        objeto.vigilar(ReproductorFalso(largo=5000), 1, ruta, lambda f: None)
        self.assertTrue(esperar(lambda: len(medidas) == 1))
        objeto.vigilar(ReproductorFalso(largo=5000), 2, ruta, lambda f: None)
        time.sleep(0.15)

        self.assertEqual(len(medidas), 1)


def _generar_wav(ruta, ffmpeg):
    subprocess.run(
        [ffmpeg, "-hide_banner", "-nostats", "-v", "error", "-y",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         "-ac", "2", "-ar", "44100", str(ruta)],
        check=True, capture_output=True)


def _reproductor_memoria(instancia, ruta):
    reproductor = instancia.media_player_new()

    @ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p,
                      ctypes.c_uint, ctypes.c_long)
    def al_reproducir(_datos, _muestras, _cantidad, _tiempo):
        return None

    reproductor.audio_set_callbacks(al_reproducir, None, None, None, None, None)
    reproductor._callback = al_reproducir
    reproductor.audio_set_format("S16N", 44100, 2)
    reproductor.set_media(instancia.media_new(str(ruta)))
    return reproductor


@unittest.skipUnless(motor_vlc.disponible(), "libVLC no está disponible")
class TestTransicionReal(unittest.TestCase):
    """Dos WAV reales y dos reproductores reales con salida a memoria."""

    def setUp(self):
        ffmpeg = ffmpeg_bin.ruta_ffmpeg()
        if not ffmpeg:
            self.skipTest("falta ffmpeg")
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.uno = Path(self.temporal.name) / "uno.wav"
        self.dos = Path(self.temporal.name) / "dos.wav"
        _generar_wav(self.uno, ffmpeg)
        _generar_wav(self.dos, ffmpeg)
        self.instancia = motor_vlc.instancia()
        if self.instancia is None:
            self.skipTest("no se pudo crear la instancia de VLC")

    def test_el_cruce_suelta_la_que_sale_y_deja_la_que_entra(self):
        objeto = Transiciones(lambda: 6)
        self.addCleanup(objeto.cerrar)
        sale = _reproductor_memoria(self.instancia, self.uno)
        entra = _reproductor_memoria(self.instancia, self.dos)
        self.addCleanup(entra.release)
        soltados = []

        def al_soltar(reproductor):
            soltados.append(reproductor)
            reproductor.stop()
            reproductor.release()

        volumenes = {"sale": [], "entra": []}
        original_sale = sale.audio_set_volume
        original_entra = entra.audio_set_volume
        sale.audio_set_volume = lambda valor: (
            volumenes["sale"].append(valor), original_sale(valor))[1]
        entra.audio_set_volume = lambda valor: (
            volumenes["entra"].append(valor), original_entra(valor))[1]

        self.assertEqual(sale.play(), 0)
        self.assertEqual(entra.play(), 0)
        objeto.cruzar(sale, 100, entra, 80, 1000, al_soltar)

        self.assertTrue(esperar(lambda: bool(soltados)), "no terminó el cruce")
        self.assertIs(soltados[0], sale)
        self.assertEqual(volumenes["entra"][-1], 80)


if __name__ == "__main__":
    unittest.main()
