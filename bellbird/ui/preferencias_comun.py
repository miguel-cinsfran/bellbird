"""Piezas de construcción que comparten todas las páginas de Preferencias."""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.ui.tema import _T

logger = diagnostico.obtener_logger(__name__)


class EleccionTexto(wx.Choice):
    """Lista desplegable que guarda un valor de texto en vez del índice.

    La tabla de opciones simples habla con `SetValue` y `GetValue`, igual que
    una casilla o un contador. Acá se traduce entre el valor guardado y la
    etiqueta que se lee.
    """

    def __init__(self, parent, opciones, normalizar=None, **kwargs):
        self._valores = tuple(valor for valor, _etiqueta in opciones)
        self._normalizar = normalizar or (lambda valor: str(valor))
        super().__init__(parent, choices=[etiqueta for _valor, etiqueta
                                          in opciones], **kwargs)

    def SetValue(self, valor) -> None:
        try:
            indice = self._valores.index(self._normalizar(valor))
        except ValueError:
            indice = 0
        self.SetSelection(indice)

    def GetValue(self) -> str:
        indice = self.GetSelection()
        if 0 <= indice < len(self._valores):
            return self._valores[indice]
        return self._valores[0]


# Ancho al que se parten las notas de cada página. Con 560 desbordaban el área
# visible (unos 490 px) y no hay desplazamiento horizontal.
ANCHO_NOTA = 450


def crear_panel(parent, name):
    # Página desplazable (solo vertical): la de Atajos mide más de 1200 px
    # y en un wx.Panel fijo dos tercios de sus botones quedaban fuera del
    # alcance del ratón. El foco (Tab) desplaza solo hasta el control.
    p = wx.ScrolledWindow(parent, name=name, style=wx.TAB_TRAVERSAL | wx.VSCROLL)
    p.SetScrollRate(0, 20)
    p.SetBackgroundColour(_T.bg)
    p.SetForegroundColour(_T.text)
    return p


def fila_label(p, texto):
    lbl = wx.StaticText(p, label=texto)
    lbl.SetForegroundColour(_T.text)
    return lbl


def fila_botones(botones, borde=6):
    fila = wx.WrapSizer(wx.HORIZONTAL)
    for boton in botones:
        fila.Add(boton, 0, wx.RIGHT, borde)
    return fila


def opciones_con_elegida(automatico, elegida, encontradas) -> list:
    """El desplegable con la elegida conservada y las halladas sin repetir."""
    opciones = [automatico]
    for fuente in (elegida, *(encontradas or ())):
        if fuente and fuente not in opciones:
            opciones.append(fuente)
    return opciones


def _ancho_categorias(libro, lista):
    textos = [libro.GetPageText(i) for i in range(libro.GetPageCount())]
    if not textos:
        return 0
    medidos = [lista.GetTextExtent(t)[0] for t in textos]
    return max(medidos) + wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X) + 28


def ajustar_ancho_categorias(libro, lista):
    """La lista muestra el nombre más largo entero, medido con el texto real."""
    try:
        ancho = _ancho_categorias(libro, lista)
        if ancho:
            lista.SetColumnWidth(0, ancho)
            lista.SetMinSize((ancho, lista.GetMinSize().height))
    except Exception as exc:
        logger.debug("ancho de las categorías: %s", exc)
