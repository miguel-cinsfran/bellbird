"""Pruebas del núcleo de sonoridad de música (sonoridad.py)."""

import json
import math
import struct
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

from tests.pseudo_prueba import con_pseudo
from ytchat.core.idioma import _
from ytchat.downloads.ffmpeg_bin import ruta_ffmpeg
from ytchat.music import sonoridad
from ytchat.music.sonoridad import (
    CacheSonoridad,
    ganancia_db,
    leer_medicion,
    medir,
    texto_progreso,
    volumen_efectivo,
)


# Resumen real de ffmpeg (stderr) con `ebur128=peak=sample:framelog=quiet`,
# tomado por el advisor sobre `Bonsai.opus`.
SALIDA_FUERTE = """\
[aist#0:0/opus @ 00000214ac791e00] Guessed Channel Layout: stereo
Input #0, opus, from 'fuerte.opus':
  Duration: 00:03:08.00, bitrate: 96 kb/s
  Stream #0:0: Audio: opus, 48000 Hz, stereo, fltp
Stream mapping:
  Stream #0:0 -> #0:0 (opus (native) -> pcm_s16le (native))
Press [q] to stop, [?] for help
Output #0, null, to 'pipe:':
  Metadata:
    encoder         : Lavf61.7.100
  Stream #0:0: Audio: pcm_s16le, 48000 Hz, stereo, s16, 1536 kb/s
[Parsed_ebur128_0 @ 00000214ac793440] Summary:

  Integrated loudness:
    I:          -9.7 LUFS
    Threshold: -19.7 LUFS

  Loudness range:
    LRA:         3.9 LU
    Threshold: -29.7 LUFS
    LRA low:   -11.9 LUFS
    LRA high:   -8.0 LUFS

  Sample peak:
    Peak:        1.1 dBFS

[Parsed_ebur128_0 @ 00000214ac793440] Target Level: -23.0 LUFS
[out#0/null @ 00000214ac792000] video:0KiB audio:1234KiB subtitle:0KiB other streams:0KiB global headers:0KiB muxing overhead: unknown
size=N/A time=00:03:08.00 bitrate=N/A speed=224x
"""


class TestLeerMedicion(unittest.TestCase):

    def test_resumen_real_devuelve_integrada_y_pico(self):
        self.assertEqual(leer_medicion(SALIDA_FUERTE), (-9.7, 1.1))

    def test_archivo_mudo_da_none(self):
        texto = SALIDA_FUERTE.replace("-9.7 LUFS", "-inf LUFS")
        self.assertIsNone(leer_medicion(texto))

    def test_pico_mudo_da_none(self):
        texto = SALIDA_FUERTE.replace("1.1 dBFS", "-inf dBFS")
        self.assertIsNone(leer_medicion(texto))

    def test_metadatos_con_i_antes_del_resumen_no_confunden(self):
        previa = ("Input #0, opus, from 'fuerte.opus':\n"
                  "  Metadata:\n"
                  "    I:          -99.9 LUFS\n"
                  "    Peak:        99.9 dBFS\n")
        self.assertEqual(leer_medicion(previa + SALIDA_FUERTE), (-9.7, 1.1))

    def test_toma_lo_que_sigue_al_ultimo_summary(self):
        self.assertEqual(leer_medicion(SALIDA_FUERTE + SALIDA_FUERTE),
                         (-9.7, 1.1))

    def test_sin_resumen_da_none(self):
        self.assertIsNone(leer_medicion("nada por aquí\n[error] algo falló\n"))

    def test_falta_la_linea_de_pico_da_none(self):
        lineas = [l for l in SALIDA_FUERTE.splitlines(keepends=True)
                  if "Peak:" not in l]
        self.assertIsNone(leer_medicion("".join(lineas)))

    def test_texto_vacio_da_none(self):
        self.assertIsNone(leer_medicion(""))


class TestGananciaDb(unittest.TestCase):

    def test_atenuacion_normal(self):
        self.assertEqual(ganancia_db(-9.05, -6.02), -4.9)

    def test_amplificacion_normal(self):
        self.assertEqual(ganancia_db(-15.05, -12.04), 1.1)

    def test_tope_por_el_pico_para_no_saturar(self):
        # Cruda 6,0 dB pero el pico solo deja 0,5 dB.
        self.assertEqual(ganancia_db(-20.0, -1.5), 0.5)

    def test_tope_maximo(self):
        self.assertEqual(ganancia_db(-30.0, -20.0), 10.0)

    def test_tope_minimo(self):
        self.assertEqual(ganancia_db(5.0, 0.0), -15.0)


class TestVolumenEfectivo(unittest.TestCase):

    def test_ganancia_cero_devuelve_el_mismo_volumen(self):
        self.assertEqual(volumen_efectivo(80, 0.0), 80)

    def test_ganancia_positiva_sube(self):
        self.assertEqual(volumen_efectivo(40, 6.0), 50)

    def test_ganancia_negativa_baja(self):
        self.assertEqual(volumen_efectivo(80, -6.0), 64)

    def test_con_cien_y_ganancia_positiva_sube(self):
        self.assertEqual(volumen_efectivo(100, 6.0), 126)

    def test_no_pasa_de_doscientos(self):
        self.assertEqual(volumen_efectivo(100, 10.0), 147)
        self.assertEqual(volumen_efectivo(100, 30.0), 200)

    def test_no_baja_de_cero(self):
        self.assertEqual(volumen_efectivo(0, -15.0), 0)

    def test_volumen_uno_con_la_atenuacion_maxima_queda_en_uno(self):
        self.assertEqual(volumen_efectivo(1, -15.0), 1)

    def test_la_amplitud_al_cubo_sube_o_baja_la_ganancia_pedida(self):
        for volumen in range(1, 101):
            for ganancia in range(-15, 11):
                with self.subTest(volumen=volumen, ganancia=ganancia):
                    resultado = volumen_efectivo(volumen, float(ganancia))
                    self.assertLessEqual(resultado, 200)
                    if resultado < 15:
                        continue
                    amplitud_db = 60.0 * math.log10(resultado / volumen)
                    self.assertLess(abs(amplitud_db - ganancia), 1.0)


class TestAvisoYProgreso(unittest.TestCase):

    def test_sin_progreso_el_texto_es_vacio(self):
        self.assertEqual(texto_progreso(None), "")

    def test_con_progreso_devuelve_hechas_y_total(self):
        self.assertEqual(texto_progreso((40, 195)),
                         "Igualando el volumen: 40 de 195")


class TestPseudoSonoridad(unittest.TestCase):
    """Pseudotraducción de los textos de la igualación.

    Sin ventanas: exige las constantes marcadas donde se usan y el
    progreso marcado con sus números presentes.
    """

    def test_constantes_salen_marcadas_donde_se_usan(self):
        nombres = (
            "TEXTO_IGUALANDO",
            "TEXTO_IGUALACION_DESACTIVADA",
            "TEXTO_SIN_FFMPEG",
            "TEXTO_NADA_PENDIENTE",
            "TEXTO_IGUALACION_DETENIDA",
            "TEXTO_PROGRESO",
        )
        with con_pseudo():
            for nombre in nombres:
                with self.subTest(nombre=nombre):
                    self.assertTrue(
                        _(getattr(sonoridad, nombre)).startswith("[¡"),
                        nombre)

    def test_progreso_marca_con_hechas_y_total(self):
        with con_pseudo():
            texto = texto_progreso((40, 195))
            vacio = texto_progreso(None)
        self.assertTrue(texto.startswith("[¡"), texto)
        self.assertIn("40", texto)
        self.assertIn("195", texto)
        self.assertEqual(vacio, "")


def _archivo(tmp, nombre="tema.mp3", contenido=b"audio"):
    ruta = Path(tmp) / nombre
    ruta.write_bytes(contenido)
    info = ruta.stat()
    return str(ruta.resolve()), info.st_mtime_ns, info.st_size


class TestCacheBuscarYPoner(unittest.TestCase):

    def test_buscar_sin_nada_da_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheSonoridad(Path(tmp) / "sonoridad_musica.json")
            self.assertIsNone(cache.buscar("C:/musica/a.mp3", 1, 2))

    def test_poner_y_buscar_devuelve_la_ganancia(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheSonoridad(Path(tmp) / "sonoridad_musica.json")
            origen, mtime_ns, tamano = _archivo(tmp)
            cache.poner(origen, mtime_ns, tamano, -4.9)
            self.assertEqual(cache.buscar(origen, mtime_ns, tamano), -4.9)

    def test_mtime_distinto_da_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheSonoridad(Path(tmp) / "sonoridad_musica.json")
            origen, mtime_ns, tamano = _archivo(tmp)
            cache.poner(origen, mtime_ns, tamano, -4.9)
            self.assertIsNone(cache.buscar(origen, mtime_ns + 1, tamano))

    def test_tamano_distinto_da_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheSonoridad(Path(tmp) / "sonoridad_musica.json")
            origen, mtime_ns, tamano = _archivo(tmp)
            cache.poner(origen, mtime_ns, tamano, -4.9)
            self.assertIsNone(cache.buscar(origen, mtime_ns, tamano + 1))

    def test_ganancia_no_finita_no_se_guarda(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheSonoridad(Path(tmp) / "sonoridad_musica.json")
            origen, mtime_ns, tamano = _archivo(tmp)
            cache.poner(origen, mtime_ns, tamano, float("inf"))
            self.assertIsNone(cache.buscar(origen, mtime_ns, tamano))


class TestCacheGuardarYLeer(unittest.TestCase):

    def test_guarda_y_vuelve_a_leer_de_un_archivo_de_verdad(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta_cache = Path(tmp) / "cache" / "sonoridad_musica.json"
            origen, mtime_ns, tamano = _archivo(tmp)
            cache = CacheSonoridad(ruta_cache)
            cache.poner(origen, mtime_ns, tamano, 1.1)
            self.assertTrue(cache.guardar())
            self.assertTrue(ruta_cache.is_file())
            recargada = CacheSonoridad(ruta_cache)
            self.assertEqual(recargada.buscar(origen, mtime_ns, tamano), 1.1)

    def test_json_roto_empieza_vacia_sin_lanzar(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta_cache = Path(tmp) / "sonoridad_musica.json"
            ruta_cache.write_text("{esto no es json", encoding="utf-8")
            cache = CacheSonoridad(ruta_cache)
            self.assertIsNone(cache.buscar("C:/musica/a.mp3", 1, 2))

    def test_otra_version_empieza_vacia(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta_cache = Path(tmp) / "sonoridad_musica.json"
            contenido = {"version": 999,
                         "sonoridad": {"C:/musica/a.mp3":
                                       {"mtime_ns": 1, "tamano": 2,
                                        "ganancia_db": 3.0}}}
            ruta_cache.write_text(json.dumps(contenido), encoding="utf-8")
            cache = CacheSonoridad(ruta_cache)
            self.assertIsNone(cache.buscar("C:/musica/a.mp3", 1, 2))


def _generar_seno(ruta, amplitud, segundos=5):
    """Un WAV mono de 1 kHz con esa amplitud, para medir de verdad."""
    cuadros = bytearray()
    for i in range(44100 * segundos):
        muestra = int(amplitud * 32767
                      * math.sin(2 * math.pi * 1000 * i / 44100))
        cuadros += struct.pack("<h", muestra)
    with wave.open(str(ruta), "w") as canal:
        canal.setnchannels(1)
        canal.setsampwidth(2)
        canal.setframerate(44100)
        canal.writeframes(bytes(cuadros))


class TestMedirReal(unittest.TestCase):
    """Mide dos senos de verdad con el ffmpeg de la app."""

    def test_los_dos_senos_miden_con_seis_db_de_diferencia(self):
        ffmpeg = ruta_ffmpeg()
        if ffmpeg is None:
            self.skipTest("ruta_ffmpeg() devolvió None: sin ffmpeg")
        with tempfile.TemporaryDirectory() as tmp:
            fuerte = str(Path(tmp) / "fuerte.wav")
            suave = str(Path(tmp) / "suave.wav")
            _generar_seno(fuerte, 0.5)
            _generar_seno(suave, 0.25)
            ganancia_fuerte = medir(ffmpeg, fuerte)
            ganancia_suave = medir(ffmpeg, suave)
            self.assertIsNotNone(ganancia_fuerte)
            self.assertIsNotNone(ganancia_suave)
            diferencia = ganancia_suave - ganancia_fuerte
            self.assertGreaterEqual(diferencia, 5)
            self.assertLessEqual(diferencia, 7)

    def test_sin_ffmpeg_da_none_sin_lanzar(self):
        with tempfile.TemporaryDirectory() as tmp:
            inexistente = str(Path(tmp) / "no_existe_ffmpeg.exe")
            self.assertIsNone(medir(inexistente, "C:/musica/a.mp3"))

    def test_plazo_vencido_mata_y_da_none(self):
        ffmpeg = ruta_ffmpeg()
        if ffmpeg is None:
            self.skipTest("ruta_ffmpeg() devolvió None: sin ffmpeg")
        with tempfile.TemporaryDirectory() as tmp:
            # Un seno de una hora que nunca termina de medirse en 2 s.
            largo = str(Path(tmp) / "largo.wav")
            args = [ffmpeg, "-hide_banner", "-nostats", "-f", "lavfi",
                    "-i", "sine=frequency=1000:duration=3600",
                    "-vn", "-sn", "-dn", "-af",
                    "ebur128=peak=sample:framelog=quiet",
                    "-f", "null", "-"]
            proceso = subprocess.Popen(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                with mock.patch("subprocess.Popen", return_value=proceso):
                    self.assertIsNone(medir(ffmpeg, largo, plazo_s=2))
            finally:
                try:
                    proceso.kill()
                except Exception:
                    pass
            self.assertIsNotNone(proceso.poll())


if __name__ == "__main__":
    unittest.main()
