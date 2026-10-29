"""La ley de volumen de libVLC, medida con el libVLC real.

VLC eleva el volumen al cubo: a 50 la amplitud es la octava parte de la de
100. Esta prueba lo fija con una salida a memoria, sin sonido real, para que
se note si una versión nueva de VLC cambia la ley.
"""

import array
import ctypes
import math
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

from bellbird.player import motor_vlc

PLAZO_S = 10.0
TASA = 44100
CANALES = 2
SEGUNDOS_TONO = 3.0
# El tramo que se mide, como fracción de las muestras recibidas: esquiva el
# arranque, donde libVLC todavía puede estar aplicando el volumen pedido.
DESDE = 0.50
HASTA = 0.90


def _generar_tono(ruta):
    """Un tono de 440 Hz de 3 s, con el ffmpeg real."""
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [ffmpeg, "-hide_banner", "-nostats", "-f", "lavfi",
         "-i", f"sine=frequency=440:duration={SEGUNDOS_TONO}",
         "-ac", str(CANALES), "-ar", str(TASA), "-y", str(ruta)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _rms_tramo(trozos):
    """La amplitud RMS del tramo entre DESDE y HASTA, de 0 a 1."""
    muestras = array.array("h")
    muestras.frombytes(b"".join(trozos))
    if not muestras:
        return 0.0
    inicio = int(len(muestras) * DESDE)
    fin = int(len(muestras) * HASTA)
    tramo = muestras[inicio:fin]
    if not tramo:
        return 0.0
    suma = sum(muestra * muestra for muestra in tramo)
    return math.sqrt(suma / len(tramo)) / 32768.0


def _medir_amplitud(instancia, vlc, ruta, volumen):
    """Reproduce `ruta` a ese volumen con salida a memoria y mide el tramo."""
    trozos = []
    candado = threading.Lock()

    def al_sonar(_datos, muestras, cuenta, _marca):
        if not muestras or cuenta <= 0:
            return
        tamano = cuenta * CANALES * 2
        with candado:
            trozos.append(ctypes.string_at(muestras, tamano))

    cb_play = vlc.CallbackDecorators.AudioPlayCb(al_sonar)
    reproductor = instancia.media_player_new()
    medio = instancia.media_new(str(ruta))
    try:
        reproductor.set_media(medio)
        reproductor.audio_set_callbacks(
            cb_play, None, None, None, None, None)
        reproductor.audio_set_format("S16N", TASA, CANALES)
        if reproductor.play() == -1:
            raise unittest.SkipTest("libVLC no pudo reproducir el tono")
        fin = time.monotonic() + PLAZO_S
        while not reproductor.is_playing() and time.monotonic() < fin:
            reproductor.audio_set_volume(volumen)
            time.sleep(0.01)
        while reproductor.is_playing() and time.monotonic() < fin:
            reproductor.audio_set_volume(volumen)
            time.sleep(0.02)
        reproductor.audio_set_volume(volumen)
        time.sleep(0.1)
        with candado:
            return _rms_tramo(trozos)
    finally:
        try:
            reproductor.stop()
        except Exception:
            pass
        reproductor.release()
        medio.release()


@unittest.skipUnless(motor_vlc.disponible(), "libVLC no está disponible")
class TestLeyDeVolumenReal(unittest.TestCase):

    def test_a_la_mitad_de_volumen_la_amplitud_es_un_octavo(self):
        instancia = motor_vlc.instancia()
        if instancia is None:
            self.skipTest("no se pudo crear la instancia de VLC")
        vlc = motor_vlc.modulo()
        if vlc is None:
            self.skipTest("no se pudo cargar el binding de libVLC")
        try:
            import imageio_ffmpeg
            imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            self.skipTest("falta ffmpeg (imageio_ffmpeg)")
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "tono.wav"
            _generar_tono(ruta)
            completa = _medir_amplitud(instancia, vlc, ruta, 100)
            mitad = _medir_amplitud(instancia, vlc, ruta, 50)
        self.assertGreater(completa, 0.0, "no se capturó audio a volumen 100")
        relativa = mitad / completa
        print(f"\n[ley de volumen] amplitud a 50 sobre 100: {relativa:.4f}")
        self.assertGreaterEqual(
            relativa, 0.10, f"amplitud relativa medida: {relativa:.4f}")
        self.assertLessEqual(
            relativa, 0.15, f"amplitud relativa medida: {relativa:.4f}")


if __name__ == "__main__":
    unittest.main()
