"""Menú contextual y teclas de la lista de escenas del Panel de OBS."""

from __future__ import annotations

import wx

from guyrapu.core.idioma import _

ACCIONES = {
    wx.WXK_RETURN: "cambiar",
    wx.WXK_NUMPAD_ENTER: "cambiar",
    wx.WXK_F2: "renombrar",
    wx.WXK_DELETE: "eliminar",
    wx.WXK_NUMPAD_DELETE: "eliminar",
}


def menu_de_escena(cambiar, renombrar, duplicar, eliminar, guardar):
    """Arma el menú de la escena elegida, con la tecla a la vista."""
    menu = wx.Menu()
    _accion(menu, _("&Cambiar escena") + "\tEnter", cambiar)
    _accion(menu, _("Cambiar &nombre…") + "\tF2", renombrar)
    _accion(menu, _("&Duplicar") + "\tCtrl+D", duplicar)
    _accion(menu, _("E&liminar") + "\tDel", eliminar)
    menu.AppendSeparator()
    _accion(menu, _("&Guardar imagen…"), guardar)
    return menu


def accion_de_tecla(evento):
    """La acción de la lista para esa tecla, o None si no le toca."""
    codigo = evento.GetKeyCode()
    if codigo == ord("D") and evento.ControlDown():
        return "duplicar"
    if (codigo == wx.WXK_WINDOWS_MENU
            or (codigo == wx.WXK_F10 and evento.ShiftDown())):
        return "menu"
    return ACCIONES.get(codigo)


def _accion(menu, etiqueta, funcion):
    identificador = wx.NewIdRef()
    menu.Append(identificador, etiqueta)
    menu.Bind(wx.EVT_MENU, lambda _evento: funcion(), id=identificador)
