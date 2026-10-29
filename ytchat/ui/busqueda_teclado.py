"""Búsqueda por prefijo (type-ahead) en listas de texto
Estando en el chat o en comentarios, escribir letras seguidas salta al
primer mensaje cuyo texto MOSTRADO («autor: mensaje…») empiece por eso, con
buffer multiletra («mig» → «Miguel», no una letra a la vez) que se resetea
solo tras un rato sin teclear. La lógica de búsqueda vive en
`busqueda_lista.py` (pura, sin wx); esto solo engancha el evento y lleva el
buffer/temporizador.
"""

from __future__ import annotations

import wx

from ytchat.core import diagnostico
from ytchat.core.idioma import _
from ytchat.ui.accesibilidad import anunciar
from ytchat.ui.busqueda_lista import buscar_prefijo, coincide


logger = diagnostico.obtener_logger(__name__)

_MS_RESET_BUSQUEDA = 900


class _BusquedaAlTeclear:
    """Buffer de teclas y temporizador de reseteo de una lista. Uno por
    control (instalar_busqueda_tipo lo crea al enganchar el evento)."""

    def __init__(self, listbox: wx.ListBox, obtener_textos) -> None:
        self._listbox = listbox
        self._obtener_textos = obtener_textos
        self._buffer = ""
        self._timer = None

    def _resetear_buffer(self) -> None:
        self._buffer = ""
        self._timer = None

    def _on_char(self, event) -> None:
        # Combinaciones con Ctrl/Alt son atajos, no texto de búsqueda.
        if event.ControlDown() or event.AltDown():
            event.Skip()
            return
        code = event.GetUnicodeKey()
        if code == wx.WXK_NONE:
            event.Skip()
            return
        ch = chr(code)
        if not ch.isprintable():
            event.Skip()
            return
        if ch == " " and not self._buffer:
            # Espacio con el buffer vacío: no es inicio de búsqueda, que se
            # comporte como en cualquier lista (no lo consumimos).
            event.Skip()
            return

        self._buffer += ch
        if self._timer is not None:
            try:
                self._timer.Stop()
            except Exception as exc:
                logger.debug("No se pudo parar el temporizador de búsqueda: %s", exc)
        self._timer = wx.CallLater(_MS_RESET_BUSQUEDA, self._resetear_buffer)

        textos = self._obtener_textos()
        if not textos:
            return
        actual = self._listbox.GetSelection()
        if (len(self._buffer) > 1 and actual != wx.NOT_FOUND
                and 0 <= actual < len(textos)
                and coincide(textos[actual], self._buffer)):
            return   # el seleccionado ya cumple: no mover nada
        desde = (actual + 1) if actual != wx.NOT_FOUND else 0
        idx = buscar_prefijo(textos, desde, self._buffer)
        if idx is not None:
            self._listbox.SetSelection(idx)
            # NVDA no siempre anuncia una selección puesta por programa.
            anunciar(textos[idx])
        else:
            # Que quien busca sepa que se buscó (en toda la lista, dando la
            # vuelta) y no hubo nada; se descarta la última letra para poder
            # seguir completando la búsqueda anterior.
            # Traductores: aviso de la búsqueda al teclear; {texto} es lo escrito sin coincidencia.
            anunciar(_("No hay coincidencias con {texto}").format(texto=self._buffer))
            self._buffer = self._buffer[:-1]


def instalar_busqueda_tipo(listbox: wx.ListBox, obtener_textos) -> None:
    """Engancha en `listbox` el type-ahead sobre EVT_CHAR (aparte de
    EVT_KEY_DOWN, que ya usan estas listas para Enter/Ctrl+C/menú, para no
    pelearse con esos keycodes). `obtener_textos` es una función sin
    argumentos que devuelve, en orden de fila, el texto mostrado de cada
    ítem (normalmente `[listbox.GetString(i) for i in range(GetCount())]`).
    """
    busqueda = _BusquedaAlTeclear(listbox, obtener_textos)
    listbox.Bind(wx.EVT_CHAR, busqueda._on_char)
