"""Asegura que haya una sola instancia de la aplicación."""

from __future__ import annotations

# Mutex de Windows para impedir que se abran dos ventanas a la vez. Se usa
# ctypes (en vez de win32event) para no añadir otra dependencia.

_mutex_handle = None

_ERROR_ACCESS_DENIED = 5      # el mutex existe pero es de otro usuario / instancia elevada
_ERROR_ALREADY_EXISTS = 183   # el mutex ya lo tiene otra instancia de este usuario

_NOMBRE_MUTEX = "YTChatTTS_SingleInstance_Mutex"


def hay_otra_instancia(error: int) -> bool:
    """Decide, a partir de GetLastError tras CreateMutexW, si ya hay otra
    instancia. ACCESS_DENIED también cuenta: el mutex existe (lo creó una
    instancia elevada o de otro usuario) aunque no nos dejen abrirlo."""
    return error in (_ERROR_ALREADY_EXISTS, _ERROR_ACCESS_DENIED)


def verificar_instancia_unica(nombre: str = _NOMBRE_MUTEX) -> bool:
    global _mutex_handle
    try:
        import ctypes
        # use_last_error + get_last_error: leer GetLastError «a mano» tras una
        # llamada ctypes no es fiable (el propio ctypes puede pisarlo entre medias).
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # Sin restype ctypes devuelve un int de 32 bits y trunca el HANDLE en x64.
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        _mutex_handle = kernel32.CreateMutexW(None, False, nombre)
        if hay_otra_instancia(ctypes.get_last_error()):
            return False
    except Exception:
        pass  # fuera de Windows, dejamos que arranque igualmente
    return True
