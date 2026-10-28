"""Frases de las teclas de silencio y salto de la música."""

from __future__ import annotations

from ytchat.core.idioma import N_, _
from ytchat.music.anuncios import Aviso
from ytchat.music.vista import texto_duracion

TEXTO_SILENCIADA = N_("Música silenciada")
TEXTO_RESTAURADA = N_("Sonido de la música restaurado")


def aviso_silencio(activo: bool) -> Aviso:
    """Confirmación del atajo que silencia o devuelve el sonido."""
    return Aviso(_(TEXTO_SILENCIADA) if activo else _(TEXTO_RESTAURADA))


def aviso_posicion(ms) -> Aviso:
    """Posición nueva tras saltar, como m:ss."""
    return Aviso(texto_duracion(ms) or "0:00")
