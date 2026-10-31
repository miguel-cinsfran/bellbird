"""Paleta «crema + salvia» (ver docs/PALETA-COLORES.md)
Fondo crema, campos y listas en blanco para que se distingan del fondo, y
la salvia viva como color de marca en la acción principal y en los títulos
de grupo. `accent` es salvia de texto y de botón principal, `red` el rojo
de error: ambos dan 4.5:1 o más con la fórmula WCAG en cada fondo de la
app (crema, blanco de superficie y blanco de campo), igual que el texto
principal y el secundario. Con el contraste alto de Windows activado
(ALTO_CONTRASTE) la paleta no se aplica y manda el tema del sistema.
"""

from __future__ import annotations

import wx

from bellbird.core import diagnostico


logger = diagnostico.obtener_logger(__name__)


class _T:
    bg      = wx.Colour(247, 244, 238)  # #F7F4EE  fondo crema de la app
    surface = wx.Colour(255, 255, 255)  # #FFFFFF  paneles, grupos y pestañas
    field   = wx.Colour(255, 255, 255)  # #FFFFFF  campos y listas, blancos
    text    = wx.Colour(51,  51,  51)   # #333333  texto principal
    dim     = wx.Colour(107, 107, 107)  # #6B6B6B  texto secundario
    accent  = wx.Colour(51,  112, 74)   # #33704A  salvia de marca y títulos
    red     = wx.Colour(179, 38,  30)   # #B3261E  texto de error
    btn     = wx.Colour(233, 225, 211)  # #E9E1D3  botones secundarios
    btn_t   = wx.Colour(51,  51,  51)   # #333333  texto de botón secundario
    # Botón principal: salvia de marca con texto blanco encima.
    primary   = wx.Colour(51,  112, 74)   # #33704A  acción principal
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
