"""Paleta «crema + salvia» (ver docs/PALETA-COLORES.md)
Fondo crema, salvia como color de marca y muy pocos tonos con papel fijo.
`accent` y `red` son colores de TEXTO (secciones, estados, errores), no
fondos: son la salvia y el rojo oscurecidos lo justo para dar 4.5:1 sobre
el fondo. Contraste comprobado con la fórmula WCAG en cada par texto/fondo
real de la app; todos dan 4.5:1 o más. Con el contraste alto de Windows
activado (ALTO_CONTRASTE) la paleta no se aplica y manda el tema del sistema.
"""

from __future__ import annotations

import wx

from ytchat.core import diagnostico


logger = diagnostico.obtener_logger(__name__)


class _T:
    bg      = wx.Colour(247, 244, 238)  # #F7F4EE  crema (fondo de marca)
    surface = wx.Colour(255, 255, 255)  # #FFFFFF  paneles, grupos, pestañas
    field   = wx.Colour(233, 225, 211)  # #E9E1D3  campos (secundario/beige)
    text    = wx.Colour(51,  51,  51)   # #333333  texto principal
    dim     = wx.Colour(107, 107, 107)  # #6B6B6B  texto secundario
    accent  = wx.Colour(63,  91,  58)   # #3F5B3A  salvia oscurecida (primario, texto)
    red     = wx.Colour(179, 38,  30)   # #B3261E  error
    btn     = wx.Colour(233, 225, 211)  # botones secundarios (= field)
    btn_t   = wx.Colour(51,  51,  51)
    # Botón primario (Conectar): salvia tal cual del md, texto oscuro encima.
    primary   = wx.Colour(202, 215, 197)  # #CAD7C5  salvia (marca, sin oscurecer)
    primary_t = wx.Colour(51,  51,  51)


def _detectar_alto_contraste() -> bool:
    """¿Windows tiene activado un tema de alto contraste? (SPI_GETHIGHCONTRAST)"""
    try:
        import ctypes

        class _HighContrast(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwFlags", ctypes.c_uint),
                        ("lpszDefaultScheme", ctypes.c_wchar_p)]

        datos = _HighContrast()
        datos.cbSize = ctypes.sizeof(_HighContrast)
        if ctypes.windll.user32.SystemParametersInfoW(
                0x42, datos.cbSize, ctypes.byref(datos), 0):   # SPI_GETHIGHCONTRAST
            return bool(datos.dwFlags & 1)                      # HCF_HIGHCONTRASTON
    except Exception as exc:
        logger.debug("No se pudo consultar el contraste alto de Windows: %s", exc)
    return False


# Con alto contraste la paleta propia pisaría los colores que el usuario eligió
# precisamente para ver: en ese caso no se pinta nada y mandan los del sistema.
ALTO_CONTRASTE = _detectar_alto_contraste()


def _pintar(w, bg=None, fg=None):
    """Aplica colores de la paleta a un control, salvo en alto contraste."""
    if ALTO_CONTRASTE:
        return
    if bg is not None:
        w.SetBackgroundColour(bg)
    if fg is not None:
        w.SetForegroundColour(fg)


def _tc(w, bg=None, fg=None):
    _pintar(w, bg or _T.field, fg or _T.text)


def _titulo(w, color=None):
    """Etiqueta de sección: color de acento y seminegrita, para jerarquía."""
    _pintar(w, fg=color or _T.accent)
    w.SetFont(w.GetFont().Bold())
