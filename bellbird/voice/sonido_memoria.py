"""Suena un WAV que ya está en memoria, sin pasar por el disco.

Su única razón para cambiar es cómo se suena un WAV en memoria. Usa
`PlaySoundW` de winmm por ctypes porque `winsound` no admite memoria
asíncrona y MCI necesita un archivo o un alias. `SND_ASYNC` vuelve en
seguida; `SND_LOOP` repite el tono del centro hasta que otro sonido lo
corte o se llame a `detener`. Fuera de Windows no hace nada.
"""

from __future__ import annotations

import ctypes
import sys
import threading

from bellbird.core import diagnostico
from bellbird.voice import sound_player

logger = diagnostico.obtener_logger(__name__)

SND_ASYNC = 0x0001
SND_NODEFAULT = 0x0002
SND_MEMORY = 0x0004
SND_LOOP = 0x0008

_winmm = None
_sonando = None
_candado = threading.Lock()


def _init_backend() -> None:
    global _winmm
    if _winmm is not None or sys.platform != "win32":
        return
    try:
        _winmm = ctypes.WinDLL("winmm.dll")
        _winmm.PlaySoundW.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
        ]
        _winmm.PlaySoundW.restype = ctypes.c_bool
    except Exception as exc:
        logger.warning("sonido_memoria: winmm.dll no disponible (%s).", exc)


def reproducir(datos: bytes, bucle: bool = False) -> bool:
    """Suena el WAV de `datos`. Devuelve si llegó a sonar.

    Guarda la referencia al buffer hasta el sonido siguiente o hasta
    `detener`, porque `PlaySoundW` lo lee mientras suena.
    """
    global _sonando
    if not datos or not sound_player.puede_sonar():
        return False
    if sys.platform != "win32":
        return False
    _init_backend()
    if _winmm is None:
        return False
    banderas = SND_MEMORY | SND_ASYNC | SND_NODEFAULT
    if bucle:
        banderas |= SND_LOOP
    with _candado:
        _sonando = ctypes.create_string_buffer(datos, len(datos))
        try:
            sono = bool(_winmm.PlaySoundW(
                ctypes.cast(_sonando, ctypes.c_void_p), None, banderas))
        except Exception as exc:
            logger.debug("sonido_memoria: no se pudo sonar: %s", exc)
            sono = False
        if not sono:
            _sonando = None
    return sono


def detener() -> None:
    """Corta cualquier tono de memoria y suelta su buffer."""
    global _sonando
    with _candado:
        _sonando = None
        if sys.platform != "win32":
            return
        _init_backend()
        if _winmm is None:
            return
        try:
            _winmm.PlaySoundW(None, None, 0)
        except Exception as exc:
            logger.debug("sonido_memoria: no se pudo detener: %s", exc)
