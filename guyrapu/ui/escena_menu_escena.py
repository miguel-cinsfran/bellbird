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
    _accion(menu, _("Cambiar escena"), wx.WXK_RETURN, cambiar)
    _accion(menu, _("Cambiar nombre…"), wx.WXK_F2, renombrar)
    _accion(menu, _("Duplicar"), ord("D"), duplicar, wx.ACCEL_CTRL)
    _accion(menu, _("Eliminar"), wx.WXK_DELETE, eliminar)
    menu.AppendSeparator()
    _accion(menu, _("Guardar imagen…"), None, guardar)
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


def _accion(menu, etiqueta, tecla, funcion, modificador=wx.ACCEL_NORMAL):
    identificador = wx.NewIdRef()
    item = menu.Append(identificador, etiqueta)
    if tecla is not None:
        item.SetAccel(wx.AcceleratorEntry(modificador, tecla, identificador))
    menu.Bind(wx.EVT_MENU, lambda _evento: funcion(), id=identificador)
