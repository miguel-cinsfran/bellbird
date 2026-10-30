"""Cómo se dibuja el avance de una fila de la lista de descargas.

La barra es una imagen de la lista de imágenes chica del `ListCtrl`, que
Windows dibuja en la columna 0 delante del texto. El texto no cambia y el
lector sigue diciendo lo mismo: la imagen no lleva texto propio.
"""

from __future__ import annotations

import math

ANCHO = 60
ALTO = 12
TRAMOS = 20


def tramo(estado, progreso) -> int:
    """Índice de imagen para la fila: -1 sin imagen, 0 a 20 con avance."""
    if estado == "completado":
        return TRAMOS
    if estado not in ("descargando", "en_cola"):
        return -1
    try:
        valor = float(progreso)
    except (TypeError, ValueError):
        return 0
    if math.isnan(valor) or valor <= 0:
        return 0
    if valor >= 100:
        return TRAMOS
    return max(0, min(TRAMOS, round(valor / 5)))


def _colores():
    """Pista, relleno y contorno: del tema, o del sistema en alto contraste."""
    import wx

    from bellbird.ui import tema

    if tema.ALTO_CONTRASTE:
        ventana = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
        return (ventana, wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT),
                wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT))
    return (tema._T.field, tema._T.accent, tema._T.dim)


def _imagen(n, fondo, pista, relleno, contorno):
    """El mapa de bits N, con N veinteavos rellenos, sobre `fondo`."""
    import wx

    bmp = wx.Bitmap(ANCHO, ALTO)
    dc = wx.MemoryDC(bmp)
    dc.SetBackground(wx.Brush(fondo))
    dc.Clear()
    izquierda, arriba = 1, 2
    ancho, alto = ANCHO - 2, ALTO - 4
    dc.SetPen(wx.Pen(contorno))
    dc.SetBrush(wx.Brush(pista))
    dc.DrawRectangle(izquierda, arriba, ancho, alto)
    relleno_ancho = round((ancho - 2) * n / TRAMOS)
    if relleno_ancho > 0:
        dc.SetPen(wx.Pen(relleno))
        dc.SetBrush(wx.Brush(relleno))
        dc.DrawRectangle(izquierda + 1, arriba + 1, relleno_ancho, alto - 2)
    dc.SelectObject(wx.NullBitmap)
    return bmp


def lista_de_imagenes(fondo):
    """Las 21 imágenes de la columna Progreso, de 60 por 12 píxeles."""
    import wx

    pista, relleno, contorno = _colores()
    lista = wx.ImageList(ANCHO, ALTO)
    for n in range(TRAMOS + 1):
        lista.Add(_imagen(n, fondo, pista, relleno, contorno))
    return lista
