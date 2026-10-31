"""Paleta «pájaro campana» (ver docs/PALETA-COLORES.md)
Blanco frío de fondo, campos y listas en blanco puro para que se distingan
del fondo, y el turquesa de la garganta del ave como color de marca en la
acción principal y en los títulos de grupo. `accent` es turquesa oscuro de
texto y de botón principal, `red` el rojo de error: ambos dan 4.5:1 o más
con la fórmula WCAG en cada fondo de la app (blanco frío, blanco de
superficie, blanco de campo y gris verdoso de botón), igual que el texto
principal y el secundario. Con el contraste alto de Windows activado
(ALTO_CONTRASTE) la paleta no se aplica y manda el tema del sistema.
"""

from __future__ import annotations

import wx

from bellbird.core import diagnostico


logger = diagnostico.obtener_logger(__name__)


class _T:
    bg      = wx.Colour(243, 246, 246)  # #F3F6F6  fondo blanco frío de la app
    surface = wx.Colour(255, 255, 255)  # #FFFFFF  paneles, grupos y pestañas
    field   = wx.Colour(255, 255, 255)  # #FFFFFF  campos y listas, blancos
    text    = wx.Colour(28,  38,  41)   # #1C2629  pizarra, texto principal
    dim     = wx.Colour(86,  101, 106)  # #56656A  pizarra media, texto secundario
    accent  = wx.Colour(11,  110, 99)   # #0B6E63  turquesa de marca y títulos
    red     = wx.Colour(180, 35,  24)   # #B42318  texto de error
    btn     = wx.Colour(226, 232, 232)  # #E2E8E8  gris verdoso, botones secundarios
    btn_t   = wx.Colour(28,  38,  41)   # #1C2629  texto de botón secundario
    # Botón principal: turquesa de marca con texto blanco encima.
    primary   = wx.Colour(11,  110, 99)   # #0B6E63  acción principal
    primary_t = wx.Colour(255, 255, 255)  # #FFFFFF  texto sobre el principal


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


def boton_principal(boton):
    """Pinta el botón de la acción principal con `primary` y `primary_t`."""
    _pintar(boton, _T.primary, _T.primary_t)


def _titulo(w, color=None):
    """Etiqueta de sección: color de acento y seminegrita, para jerarquía."""
    _pintar(w, fg=color or _T.accent)
    w.SetFont(w.GetFont().Bold())
