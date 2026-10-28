"""Distinción de los sonidos: un WAV por evento, sin duplicados.

Dentro de cada tema no hay dos WAV con el mismo contenido (md5), y todo
evento de `_EVENTOS_SONIDO` tiene su archivo en cada tema. Lee los WAV del
disco, sin ventanas y sin reproducir nada.
"""

import hashlib
import struct
import unittest
import wave
from pathlib import Path

from ytchat.core import config, eventos_sonido

RAIZ = Path(__file__).resolve().parent.parent
TEMAS_DIR = RAIZ / "sounds" / "themes"

# Los doce avisos con sonido propio (encargo 174, más directo_finalizado y
# la vuelta de la conexión), los cuatro de música y los siete de la IA.
EVENTOS_NUEVOS = [
    "descarga_iniciada", "descarga_completada", "descarga_fallida",
    "descarga_cancelada", "al_aire", "transmision_detenida",
    "transmision_problema", "transmision_recuperada", "aviso",
    "grabacion_problema",
    "actualizacion_disponible", "actualizacion_lista", "directo_finalizado",
    "musica_tema", "musica_fin", "musica_fallo", "musica_igualando",
    "ia_enviada", "ia_respuesta", "ia_error",
    "ia_analizando", "ia_captura", "ia_cancelada", "ia_imagen_negra",
    "atajos_ocupados",
    "microfono_sin_senal",
    "directo_pausado", "directo_reanudado",
]

# Tope de duración por evento: la espera de la IA lleva una figura melódica
# de hasta 1,2 segundos porque se repite cada 2 segundos sin tapar al lector.
DURACION_MAXIMA = {
    "ia_analizando": 1.2,
}


def _md5(ruta: Path) -> str:
    return hashlib.md5(ruta.read_bytes()).hexdigest()


def _duracion(ruta: Path) -> float:
    with wave.open(str(ruta), "rb") as wav:
        return wav.getnframes() / float(wav.getframerate() or 44100)


def _canal_izquierdo(ruta: Path) -> tuple[list[int], int]:
    with wave.open(str(ruta), "rb") as wav:
        canales = wav.getnchannels()
        ancho = wav.getsampwidth()
        frecuencia = wav.getframerate()
        crudo = wav.readframes(wav.getnframes())
    if ancho != 2:
        raise AssertionError(f"{ruta.name}: se esperaba 16 bits")
    enteros = struct.unpack(f"<{len(crudo) // 2}h", crudo)
    return list(enteros[0::canales]), frecuencia


def _rms(muestras: list[int]) -> float:
    if not muestras:
        return 0.0
    return (sum(m * m for m in muestras) / len(muestras)) ** 0.5


class PruebasSonidosDistintos(unittest.TestCase):
    def test_cada_evento_tiene_su_wav_en_cada_tema(self):
        temas = sorted(d.name for d in TEMAS_DIR.iterdir() if d.is_dir())
        faltantes = []
        for tema in temas:
            for evento in config._EVENTOS_SONIDO:
                if not (TEMAS_DIR / tema / f"{evento}.wav").exists():
                    faltantes.append(f"{tema}/{evento}.wav")
        self.assertEqual(faltantes, [])

    def test_sin_duplicados_dentro_de_cada_tema(self):
        temas = sorted(d.name for d in TEMAS_DIR.iterdir() if d.is_dir())
        for tema in temas:
            vistos: dict[str, str] = {}
            duplicados = []
            for ruta in sorted((TEMAS_DIR / tema).glob("*.wav")):
                firma = _md5(ruta)
                if firma in vistos:
                    duplicados.append(f"{vistos[firma]} == {ruta.name}")
                else:
                    vistos[firma] = ruta.name
            with self.subTest(tema=tema):
                self.assertEqual(duplicados, [])

    def test_los_eventos_nuevos_estan_en_la_lista_y_con_nombre(self):
        for evento in EVENTOS_NUEVOS:
            with self.subTest(evento=evento):
                self.assertIn(evento, eventos_sonido.EVENTOS)
                self.assertIn(evento, eventos_sonido.NOMBRES)

    def test_los_nuevos_duran_entre_015_y_07_segundos(self):
        temas = sorted(d.name for d in TEMAS_DIR.iterdir() if d.is_dir())
        for tema in temas:
            for evento in EVENTOS_NUEVOS:
                ruta = TEMAS_DIR / tema / f"{evento}.wav"
                with self.subTest(tema=tema, evento=evento):
                    self.assertTrue(ruta.exists(), f"falta {ruta.name}")
                    self.assertGreaterEqual(_duracion(ruta), 0.15, ruta.name)
                    self.assertLessEqual(
                        _duracion(ruta),
                        DURACION_MAXIMA.get(evento, 0.7), ruta.name)

    def test_musica_tema_suena_suave_y_calido(self):
        for tema in ("default", "suave"):
            ruta = TEMAS_DIR / tema / "musica_tema.wav"
            with self.subTest(tema=tema):
                muestras, frecuencia = _canal_izquierdo(ruta)
                pico = max(abs(m) for m in muestras) / 32768.0
                self.assertLessEqual(pico, 0.40, ruta.name)
                self.assertLessEqual(_duracion(ruta), 0.6, ruta.name)
                fin_ataque = int(frecuencia * 0.010)
                desde = int(frecuencia * 0.020)
                hasta = int(frecuencia * 0.040)
                self.assertLess(
                    _rms(muestras[:fin_ataque]),
                    _rms(muestras[desde:hasta]) / 2,
                    f"{ruta.name}: el ataque no es lento")


if __name__ == "__main__":
    unittest.main()
