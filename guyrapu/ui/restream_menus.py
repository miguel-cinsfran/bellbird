"""Menús contextuales de la ventana de Restream.

Arma el menú de una fila de Destinos, Perfiles o Eventos y el de «Agregar
destino…». Cada elemento dice su tecla, como en la pestaña Escena del Panel
de OBS.
"""

from __future__ import annotations

import wx

from guyrapu.core.idioma import _

# Las dos entradas del menú de eventos comparten esta etiqueta.
ABRIR_DIRECTO = _("&Abrir el directo")


def menu_destino(destino, acciones):
    """El menú de un destino, con su estado y las acciones de la fila."""
    menu = wx.Menu()
    _casilla(menu, _("&Activo") + "\tSpace", destino.activo, acciones.activar)
    _accion(menu, _("Cambiar &título…"), acciones.cambiar_titulo)
    menu.AppendSeparator()
    _accion(menu, _("Abrir en el &navegador"), acciones.abrir)
    _accion(menu, _("&Copiar enlace") + "\tCtrl+C", acciones.copiar)
    menu.AppendSeparator()
    _accion(menu, _("&Eliminar") + "\tDel", acciones.eliminar)
    return menu


def menu_perfil(acciones):
    """El menú de un perfil de Restream."""
    menu = wx.Menu()
    _accion(menu, _("&Editar…") + "\tEnter", acciones.editar)
    _accion(menu, _("Cambiar &nombre…") + "\tF2", acciones.renombrar)
    _accion(menu, _("&Duplicar") + "\tCtrl+D", acciones.duplicar)
    menu.AppendSeparator()
    _accion(menu, _("E&liminar") + "\tDel", acciones.eliminar)
    return menu


def menu_evento(acciones, enlaces):
    """El menú de un evento; con varios enlaces, Abrir el directo es submenú."""
    menu = wx.Menu()
    _accion(menu, _("&Copiar enlaces") + "\tCtrl+C", acciones.copiar)
    _accion(menu, _("Copiar &información"), acciones.copiar_informacion)
    if len(enlaces) > 1:
        menu.AppendSubMenu(_menu_enlaces(acciones, enlaces), ABRIR_DIRECTO)
    else:
        _accion(menu, ABRIR_DIRECTO, acciones.abrir)
    _accion(menu, _("&Estadísticas") + "\tEnter", acciones.estadisticas)
    return menu


def _menu_enlaces(acciones, enlaces):
    menu = wx.Menu()
    for nombre, url in enlaces:
        _accion(menu, nombre, lambda url=url: acciones.abrir_url(url))
    return menu


def menu_agregar(abrir_pagina, manual):
    """El menú del botón Agregar destino con sus dos caminos."""
    menu = wx.Menu()
    _accion(menu, _("Página de &Restream…"), abrir_pagina)
    _accion(menu, _("&Manual, con servidor y clave…"), manual)
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
