"""Carpetas conocidas de Windows, preguntadas al sistema.

Razón: preguntarle a Windows por una carpeta conocida.
"""

from __future__ import annotations

import ctypes
import logging
import os

logger = logging.getLogger("bellbird.carpetas_windows")


class _GUID(ctypes.Structure):
    """GUID de ctypes para pedir carpetas conocidas a Windows."""
    _fields_ = [("Data1", ctypes.c_uint32),
                ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16),
                ("Data4", ctypes.c_ubyte * 8)]


def _guid_musica() -> _GUID:
    """FOLDERID_Music, la carpeta conocida Música de Windows."""
    return _GUID(0x4BD8D571, 0x6D19, 0x48D3,
                 (ctypes.c_ubyte * 8)(0xBE, 0x97, 0x42, 0x22,
                                      0x20, 0x08, 0x0E, 0x43))


def _leer_carpeta_conocida(identidad: _GUID) -> str:
    """Pide una carpeta conocida a Windows; falla si no se puede leer."""
    conocida = ctypes.windll.shell32.SHGetKnownFolderPath
    conocida.argtypes = [ctypes.POINTER(_GUID), ctypes.c_uint32,
                         ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]
    conocida.restype = ctypes.c_long
    puntero = ctypes.c_wchar_p()
    try:
        resultado = conocida(ctypes.byref(identidad), 0, None, ctypes.byref(puntero))
        if resultado != 0 or not puntero.value:
            raise OSError(f"SHGetKnownFolderPath devolvió {resultado:#x}")
        return puntero.value
    finally:
        if puntero.value is not None:
            ctypes.windll.ole32.CoTaskMemFree(puntero)


def carpeta_musica_windows() -> str:
    """Carpeta Música conocida de Windows, o «» si no se puede leer.

    Respeta que el usuario la haya movido a otro disco. No la crea ni
    comprueba que exista. Cualquier fallo deja una línea en el registro.
    """
    try:
        if os.name != "nt":
            logger.debug("carpeta_musica_windows: sin Windows, sin carpeta conocida")
            return ""
        return _leer_carpeta_conocida(_guid_musica())
    except Exception as exc:
        logger.warning("no se pudo leer la carpeta Música de Windows: %s", exc)
        return ""
