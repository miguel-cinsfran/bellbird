"""Frases de las teclas de silencio y salto de la música."""

from __future__ import annotations

from ytchat.music.anuncios import Aviso
from ytchat.music.vista import texto_duracion

TEXTO_SILENCIADA = "Música silenciada"
TEXTO_RESTAURADA = "Sonido de la música restaurado"


def aviso_silencio(activo: bool) -> Aviso:
    """Confirmación del atajo que silencia o devuelve el sonido."""
    return Aviso(TEXTO_SILENCIADA if activo else TEXTO_RESTAURADA)


def aviso_posicion(ms) -> Aviso:
    """Posición nueva tras saltar, como m:ss."""
    return Aviso(texto_duracion(ms) or "0:00")
