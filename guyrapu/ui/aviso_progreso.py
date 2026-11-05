"""Emite los avisos de avance de las descargas aunque el diálogo esté cerrado.

Un único temporizador de nivel de módulo, sin dueño de ventana, lee la lista
del gestor cada segundo y pasa los avisos de la lógica pura a `anunciar` y al
reproductor de sonidos.
"""

from __future__ import annotations

import time

import wx

from guyrapu.core import config as cfg
from guyrapu.downloads.descargas import gestor
from guyrapu.downloads.progreso_anuncio import (
    TIPO_AVANCE, AnunciadorProgreso)
from guyrapu.ui.gui import anunciar
from guyrapu.voice import sound_player as _snd

INTERVALO_MS = 1000

_temporizador = None
_anunciador = None


class _TemporizadorProgreso(wx.Timer):
    """Sin dueño de ventana: sigue vivo aunque se cierre el diálogo."""

    def Notify(self) -> None:
        _latido()


def vigilar() -> None:
    """Arranca el temporizador una sola vez."""
    global _temporizador
    if _temporizador is not None:
        return
    _temporizador = _TemporizadorProgreso()
    _temporizador.Start(INTERVALO_MS)


def _latido() -> None:
    global _anunciador
    lista = gestor().lista()
    if not any(descarga.estado == "descargando" for descarga in lista):
        return
    if not cfg.obtener_opciones_descarga().get("anunciar_progreso", False):
        _anunciador = None
        return
    if _anunciador is None:
        _anunciador = AnunciadorProgreso()
    avisos = _anunciador.avisos(lista, time.monotonic())
    if not avisos:
        return
    anunciar(". ".join(aviso.texto for aviso in avisos))
    if any(aviso.tipo == TIPO_AVANCE for aviso in avisos):
        _snd.reproducir("descarga_avance")
    else:
        _snd.reproducir("descarga_quieta")
