"""Detector de rostros de la cámara con YuNet, el modelo que trae OpenCV.

Recibe la imagen como bytes, la decodifica y devuelve los rostros como
`encuadre.Rostro`, más la luz del rostro y del fondo y una huella para
saber si la imagen se congeló. Lo que se dice a partir de eso vive en
`encuadre`: este módulo solo sabe cómo hablarle a OpenCV.
"""

from __future__ import annotations

import hashlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path

from bellbird.camera import encuadre
from bellbird.core import paths
from bellbird.core.idioma import _

# Umbral de confianza con el que se crea el detector: valores de partida.
UMBRAL_CONFIANZA = 0.7


class DetectorNoDisponible(Exception):
    """OpenCV no pudo cargar el detector: lleva el texto para el usuario."""


class ImagenIlegible(Exception):
    """Los bytes no se pudieron decodificar como imagen."""


def disponible() -> bool:
    """¿Están instalados OpenCV y numpy? Sin importarlos, para no frenar el arranque."""
    try:
        return importlib.util.find_spec("cv2") is not None \
            and importlib.util.find_spec("numpy") is not None
    except Exception:
        return False


@dataclass(frozen=True, slots=True)
class Cuadro:
    """Una imagen decodificada: rostros, tamaño, luz y huella de sus píxeles."""

    rostros: tuple
    ancho: int
    alto: int
    luz_rostro: float | None
    luz_fondo: float | None
    huella: bytes


def _rostro_de_fila(fila):
    """Un `encuadre.Rostro` desde una fila de YuNet.

    Columnas 0 a 3: recuadro; 4 a 7: los dos ojos; 8 y 9: la nariz;
    la última: la confianza. El ojo de la izquierda es el de menor x
    en la imagen, sin fiarse de a cuál llama YuNet derecho.
    """
    ojo_uno = (float(fila[4]), float(fila[5]))
    ojo_otro = (float(fila[6]), float(fila[7]))
    if ojo_otro[0] < ojo_uno[0]:
        ojo_uno, ojo_otro = ojo_otro, ojo_uno
    return encuadre.Rostro(
        x=float(fila[0]), y=float(fila[1]),
        ancho=float(fila[2]), alto=float(fila[3]),
        ojo_izquierda=ojo_uno, ojo_derecha=ojo_otro,
        nariz=(float(fila[8]), float(fila[9])),
        confianza=float(fila[-1]))


def _luces(gris, rostro, ancho, alto):
    """Luz media dentro del recuadro y en el resto de la imagen en gris."""
    x0 = min(max(int(rostro.x), 0), ancho)
    y0 = min(max(int(rostro.y), 0), alto)
    x1 = min(max(int(rostro.x + rostro.ancho), 0), ancho)
    y1 = min(max(int(rostro.y + rostro.alto), 0), alto)
    dentro = gris[y0:y1, x0:x1]
    if not dentro.size:
        return None, float(gris.mean())
    resto = gris.size - dentro.size
    if resto:
        return float(dentro.mean()), float(
            (gris.sum() - dentro.sum()) / resto)
    return float(dentro.mean()), None


class DetectorRostros:
    """Envuelve a `cv2.FaceDetectorYN`, que se crea la primera vez que se usa."""

    def __init__(self, ruta_modelo=None):
        if ruta_modelo is None:
            self.ruta_modelo = paths.modelo_rostros()
        else:
            self.ruta_modelo = Path(ruta_modelo)
        self._detector = None

    def _cargar(self):
        """El detector compartido, creado una sola vez."""
        if self._detector is None:
            try:
                import cv2
            except ImportError:
                raise DetectorNoDisponible(
                    _("No se pudo cargar el detector de rostros.")) from None
            if not self.ruta_modelo.is_file():
                raise DetectorNoDisponible(
                    _("No se pudo cargar el detector de rostros."))
            try:
                self._detector = cv2.FaceDetectorYN.create(
                    str(self.ruta_modelo), "", (320, 320), UMBRAL_CONFIANZA)
            except Exception:
                raise DetectorNoDisponible(
                    _("No se pudo cargar el detector de rostros.")) from None
        return self._detector

    def analizar(self, datos: bytes) -> Cuadro:
        """Rostros, luz y huella de la imagen en `datos`."""
        try:
            import cv2
            import numpy
        except ImportError:
            raise DetectorNoDisponible(
                _("No se pudo cargar el detector de rostros.")) from None
        matriz = numpy.frombuffer(datos, dtype=numpy.uint8)
        try:
            imagen = cv2.imdecode(matriz, cv2.IMREAD_COLOR)
        except Exception:
            imagen = None
        if imagen is None:
            raise ImagenIlegible(_("No se pudo leer la imagen."))
        alto, ancho = imagen.shape[:2]
        huella = hashlib.blake2b(imagen.tobytes()).digest()
        detector = self._cargar()
        detector.setInputSize((ancho, alto))
        _ok, hallados = detector.detect(imagen)
        if hallados is None:
            rostros = ()
        else:
            rostros = tuple(_rostro_de_fila(fila) for fila in hallados)
        gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
        if rostros:
            luz_rostro, luz_fondo = _luces(
                gris, encuadre.principal(rostros), ancho, alto)
        else:
            luz_rostro, luz_fondo = None, float(gris.mean())
        return Cuadro(rostros=rostros, ancho=ancho, alto=alto,
                      luz_rostro=luz_rostro, luz_fondo=luz_fondo,
                      huella=huella)
