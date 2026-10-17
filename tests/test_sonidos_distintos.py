"""Distinción de los sonidos: un WAV por evento, sin duplicados.

Dentro de cada tema no hay dos WAV con el mismo contenido (md5), y todo
evento de `_EVENTOS_SONIDO` tiene su archivo en cada tema. Lee los WAV del
disco, sin ventanas y sin reproducir nada.
"""

import hashlib
import unittest
import wave
from pathlib import Path

from ytchat.core import config

RAIZ = Path(__file__).resolve().parent.parent
TEMAS_DIR = RAIZ / "sounds" / "themes"

# Los doce avisos con sonido propio (encargo 174, más directo_finalizado y
# la vuelta de la conexión).
EVENTOS_NUEVOS = [
    "descarga_iniciada", "descarga_completada", "descarga_fallida",
    "descarga_cancelada", "al_aire", "transmision_detenida",
    "transmision_problema", "transmision_recuperada", "aviso",
    "actualizacion_disponible", "actualizacion_lista", "directo_finalizado",
]


def _md5(ruta: Path) -> str:
    return hashlib.md5(ruta.read_bytes()).hexdigest()


def _duracion(ruta: Path) -> float:
    with wave.open(str(ruta), "rb") as wav:
        return wav.getnframes() / float(wav.getframerate() or 44100)


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

    def test_los_nuevos_duran_entre_015_y_07_segundos(self):
        temas = sorted(d.name for d in TEMAS_DIR.iterdir() if d.is_dir())
        for tema in temas:
            for evento in EVENTOS_NUEVOS:
                ruta = TEMAS_DIR / tema / f"{evento}.wav"
                with self.subTest(tema=tema, evento=evento):
                    self.assertTrue(ruta.exists(), f"falta {ruta.name}")
                    self.assertGreaterEqual(_duracion(ruta), 0.15, ruta.name)
                    self.assertLessEqual(_duracion(ruta), 0.7, ruta.name)


if __name__ == "__main__":
    unittest.main()
