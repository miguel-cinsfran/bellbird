"""Encuentra la ventana principal de OBS y la trae al frente.

Una sola responsabilidad: localizar entre las ventanas de nivel superior la
principal de OBS (título que empieza con «OBS » y proceso `obs64.exe`) y
restaurarla al frente con la API de Windows. No abre OBS ni toca su
websocket: si no hay ventana, OBS no está abierto.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from ytchat.core import diagnostico

logger = diagnostico.obtener_logger(__name__)

TEXTO_SIN_OBS = "OBS no está abierto."
TEXTO_SIN_FRENTE = "No se pudo mostrar la ventana de OBS."

_SW_RESTORE = 9
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def buscar_ventana():
    """Ventana principal de OBS o None si no se encuentra.

    Recorre las ventanas de nivel superior y devuelve la primera cuyo
    título empieza con «OBS » y cuyo proceso es `obs64.exe`. El título se
    mira antes que el proceso, que es lo caro. Nunca lanza: un fallo de
    ctypes se anota y cuenta como no encontrado.
    """
    try:
        return _buscar_ventana()
    except Exception as exc:
        logger.debug("No se pudo buscar la ventana de OBS: %s", exc)
        return None


def _buscar_ventana():
    user32 = ctypes.WinDLL("user32")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    prototipo = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [
        wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    kernel32.OpenProcess.argtypes = [
        wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    encontrada = []

    def _visitar(ventana, _parametro):
        try:
            if not _titulo_empieza_con_obs(user32, ventana):
                return True
            if _es_proceso_obs(user32, kernel32, ventana):
                encontrada.append(ventana)
                return False
        except Exception as exc:
            logger.debug("Se salta una ventana al buscar OBS: %s", exc)
        return True

    visitar = prototipo(_visitar)
    user32.EnumWindows(visitar, 0)
    return encontrada[0] if encontrada else None


def _titulo_empieza_con_obs(user32, ventana) -> bool:
    """True si el título de la ventana empieza con «OBS »."""
    largo = user32.GetWindowTextLengthW(ventana)
    if largo <= 0:
        return False
    bufer = ctypes.create_unicode_buffer(largo + 1)
    user32.GetWindowTextW(ventana, bufer, largo + 1)
    return (bufer.value or "").startswith("OBS ")


def _es_proceso_obs(user32, kernel32, ventana) -> bool:
    """True si la ventana pertenece a un proceso `obs64.exe`."""
    identificador = wintypes.DWORD()
    user32.GetWindowThreadProcessId(ventana, ctypes.byref(identificador))
    if not identificador.value:
        return False
    proceso = kernel32.OpenProcess(
        _PROCESS_QUERY_LIMITED_INFORMATION, False, identificador.value)
    if not proceso:
        return False
    try:
        return _nombre_ejecutable(kernel32, proceso).lower() == "obs64.exe"
    finally:
        kernel32.CloseHandle(proceso)


def _nombre_ejecutable(kernel32, proceso) -> str:
    """Nombre del ejecutable del proceso, sin la ruta."""
    tamano = wintypes.DWORD(260)
    bufer = ctypes.create_unicode_buffer(tamano.value)
    if not kernel32.QueryFullProcessImageNameW(
            proceso, 0, bufer, ctypes.byref(tamano)):
        return ""
    ruta = bufer.value or ""
    return ruta.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]


def _traer(ventana) -> bool:
    """Restaura la ventana y la trae al frente.

    Devuelve si `SetForegroundWindow` dio verdadero. Un fallo de ctypes
    se anota y cuenta como no traído.
    """
    try:
        user32 = ctypes.WinDLL("user32")
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype = wintypes.BOOL
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.restype = wintypes.BOOL
        user32.ShowWindow(ventana, _SW_RESTORE)
        return bool(user32.SetForegroundWindow(ventana))
    except Exception as exc:
        logger.debug("No se pudo traer al frente la ventana de OBS: %s", exc)
        return False


def mostrar(buscar=buscar_ventana, traer=_traer) -> str:
    """Trae al frente la ventana de OBS y devuelve el texto a anunciar.

    Vacío si la ventana quedó al frente: el lector ya lee la ventana que
    toma el foco. Si OBS no está abierto o no se pudo traer al frente,
    devuelve el aviso que toca anunciar. Nunca lanza.
    """
    try:
        ventana = buscar()
    except Exception as exc:
        logger.debug("No se pudo buscar la ventana de OBS: %s", exc)
        return TEXTO_SIN_OBS
    if ventana is None:
        return TEXTO_SIN_OBS
    try:
        al_frente = traer(ventana)
    except Exception as exc:
        logger.debug("No se pudo traer al frente la ventana de OBS: %s", exc)
        return TEXTO_SIN_FRENTE
    return "" if al_frente else TEXTO_SIN_FRENTE
