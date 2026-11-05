"""Menú contextual de una fuente de la pestaña Escena del Panel de OBS."""

from __future__ import annotations

import wx

from bellbird.core.idioma import _, pgettext


def menu_de_fuente(fila, mostrar, bloquear, posicion_tamano, mover):
    """Arma el menú de una fila con las acciones de la fuente elegida.

    `mostrar` y `bloquear` reciben el estado nuevo de la casilla; `mover`
    recibe el movimiento de capa y `posicion_tamano` no recibe nada.
    """
    menu = wx.Menu()
    _casilla(menu, _("&Mostrar en la escena"), fila.visible, mostrar)
    _casilla(menu, _("&Bloquear posición"), fila.bloqueada, bloquear)
    menu.AppendSeparator()
    _accion(menu, _("&Posición y tamaño…"), posicion_tamano)
    menu.AppendSubMenu(_menu_de_orden(mover), _("&Ordenar"))
    return menu


def _menu_de_orden(mover):
    menu = wx.Menu()
    for etiqueta, movimiento in (
            (_("Mover a la &cima"), "cima"),
            (pgettext("orden de fuentes", "&Subir"), "adelante"),
            (pgettext("orden de fuentes", "&Bajar"), "atras"),
            (_("Mover al &fondo"), "fondo")):
        _accion(menu, etiqueta, lambda movimiento=movimiento: mover(movimiento))
    return menu


def _casilla(menu, etiqueta, marcada, funcion):
    identificador = wx.NewIdRef()
    item = menu.AppendCheckItem(identificador, etiqueta)
    item.Check(bool(marcada))
    menu.Bind(wx.EVT_MENU,
              lambda evento: funcion(evento.IsChecked()), id=identificador)


def _accion(menu, etiqueta, funcion):
    identificador = wx.NewIdRef()
    menu.Append(identificador, etiqueta)
    menu.Bind(wx.EVT_MENU, lambda _evento: funcion(), id=identificador)
