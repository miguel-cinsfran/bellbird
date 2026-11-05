"""Espera al cierre de un proceso por su pid."""

from __future__ import annotations

import os
import time


def esperar_pid(pid: int, tope: float) -> bool:
    """Devuelve si el proceso terminó antes del tope en segundos."""
    inicio = time.monotonic()
    pid = int(pid)
    while True:
        if termino(pid):
            return True
        if time.monotonic() - inicio >= tope:
            return False
        time.sleep(0.2)


_SYNCHRONIZE = 0x00100000
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_ACCESO_TERMINO = _SYNCHRONIZE | _PROCESS_QUERY_LIMITED_INFORMATION
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 0x102


def termino(pid: int) -> bool:
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = (
                wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
            kernel32.OpenProcess.restype = ctypes.c_void_p
            kernel32.WaitForSingleObject.argtypes = (
                ctypes.c_void_p, wintypes.DWORD)
            kernel32.WaitForSingleObject.restype = wintypes.DWORD
            kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
            kernel32.CloseHandle.restype = wintypes.BOOL
            handle = kernel32.OpenProcess(_ACCESO_TERMINO, False, pid)
            if not handle:
                return True
            try:
                # Solo objeto señalado es terminado. El resto, incluido
                # _WAIT_TIMEOUT, es vivo.
                return kernel32.WaitForSingleObject(
                    handle, 0) == _WAIT_OBJECT_0
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            # En Windows os.kill no comprueba nada: la señal 0 es
            # CTRL_C_EVENT. Sin ctypes no se sabe si terminó.
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except (PermissionError, OSError):
        return False
    return False
