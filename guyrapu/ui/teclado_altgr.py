"""Consulta qué escribe AltGr con una tecla según el teclado en uso."""

from __future__ import annotations

import sys


_CTRL = 0x11
_ALT = 0x12
_APRETADA = 0x80
# No altera el estado de las teclas muertas: solo interesa qué escribe AltGr.
_BANDERA_NO_TOCAR_MUERTAS = 4
# MAPVK_VK_TO_VSC: del código virtual de la tecla a su código de exploración.
_MAPVK_VK_TO_VSC = 0

# WinDLL propio, creado una sola vez: las firmas puestas sobre el objeto
# compartido las heredaría el resto del proceso.
_user32 = None


def _obtener_user32():
    global _user32
    if _user32 is None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetKeyboardLayout.argtypes = [wintypes.DWORD]
        user32.GetKeyboardLayout.restype = wintypes.HKL
        user32.LoadKeyboardLayoutW.argtypes = [wintypes.LPCWSTR, wintypes.UINT]
        user32.LoadKeyboardLayoutW.restype = wintypes.HKL
        user32.MapVirtualKeyExW.argtypes = [
            wintypes.UINT, wintypes.UINT, wintypes.HKL,
        ]
        user32.MapVirtualKeyExW.restype = wintypes.UINT
        user32.ToUnicodeEx.argtypes = [
            wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_ubyte),
            wintypes.LPWSTR, ctypes.c_int, wintypes.UINT, wintypes.HKL,
        ]
        user32.ToUnicodeEx.restype = ctypes.c_int
        _user32 = user32
    return _user32


def caracter_altgr(tecla: str, distribucion: str | None = None) -> str:
    """Devuelve lo que escribe AltGr con `tecla`, o "" si no escribe nada.

    `tecla` es una letra o un dígito en minúscula. `distribucion` es el
    identificador de una distribución de teclado (por ejemplo "0000080A");
    si es None se usa la del hilo actual. Nunca lanza: sin saber la
    distribución no se bloquea al usuario.
    """
    if sys.platform != "win32":
        return ""
    try:
        return _caracter_altgr_windows(tecla, distribucion)
    except Exception:
        return ""


def _caracter_altgr_windows(tecla: str, distribucion: str | None) -> str:
    import ctypes

    user32 = _obtener_user32()

    if distribucion is not None:
        distribucion = user32.LoadKeyboardLayoutW(str(distribucion), 0)
    else:
        distribucion = user32.GetKeyboardLayout(0)

    estado = (ctypes.c_ubyte * 256)()
    estado[_CTRL] = _APRETADA
    estado[_ALT] = _APRETADA
    buffer = ctypes.create_unicode_buffer(8)
    codigo = ord(tecla.upper())
    exploracion = user32.MapVirtualKeyExW(
        codigo, _MAPVK_VK_TO_VSC, distribucion)
    escrito = user32.ToUnicodeEx(
        codigo, exploracion, estado, buffer, len(buffer),
        _BANDERA_NO_TOCAR_MUERTAS, distribucion)
    if escrito < 0:
        # Tecla muerta: cuenta como que escribe algo.
        return buffer.value or "?"
    return buffer.value if escrito > 0 else ""
