"""Menú contextual de una fuente de la pestaña Escena del Panel de OBS."""

from __future__ import annotations

import wx

from guyrapu.core.idioma import _


def menu_de_fuente(fila, acciones):
    """Arma el menú de una fila con las acciones de la fuente elegida."""
    menu = wx.Menu()
    _casillas(menu, fila, acciones)
    _edicion(menu, acciones)
    menu.AppendSubMenu(_menu_transformar(acciones), _("&Transformar"))
    menu.AppendSubMenu(_menu_ordenar(acciones), _("&Ordenar"))
    return menu


def _casillas(menu, fila, acciones):
    _casilla(menu, _("&Mostrar en la escena") + "\tSpace", fila.visible,
             acciones.mostrar)
    _casilla(menu, _("&Bloquear posición"), fila.bloqueada,
             acciones.bloquear)


def _edicion(menu, acciones):
    menu.AppendSeparator()
    _accion(menu, _("&Propiedades…") + "\tAlt+Enter", acciones.propiedades)
    _accion(menu, _("&Cambiar nombre…") + "\tF2", acciones.renombrar)
    _accion(menu, _("&Duplicar") + "\tCtrl+D", acciones.duplicar)
    _accion(menu, _("E&liminar") + "\tDel", acciones.eliminar)


def _menu_transformar(acciones):
    menu = wx.Menu()
    _accion(menu, _("&Tamaño y posición…"), acciones.posicion_tamano)
    _accion(menu, _("&Mover con flechas"), acciones.mover_con_flechas)
    menu.AppendSeparator()
    _menu_transformar_forma(menu, acciones)
    _accion(menu, _("&Restablecer tamaño y posición"), acciones.restablecer)
    return menu


def _menu_transformar_forma(menu, acciones):
    _accion(menu, _("&Centrar en el vídeo"), acciones.centrar)
    _accion(menu, _("&Ajustar al vídeo"), acciones.ajustar)
    _accion(menu, _("&Llenar el vídeo"), acciones.llenar)
    menu.AppendSeparator()
    _accion(menu, _("Voltear &horizontalmente"), acciones.voltear_horizontal)
    _accion(menu, _("Voltear &verticalmente"), acciones.voltear_vertical)
    _accion(menu, _("Girar a la &derecha"), acciones.girar_derecha)
    _accion(menu, _("Girar a la &izquierda"), acciones.girar_izquierda)
    menu.AppendSeparator()


def _menu_ordenar(acciones):
    menu = wx.Menu()
    for etiqueta, tecla, movimiento in (
            (_("Traer al &frente"), "\tCtrl+Home", "frente"),
            (_("Traer a&delante"), "\tCtrl+Up", "adelante"),
            (_("Enviar a&trás"), "\tCtrl+Down", "atras"),
            (_("Enviar al fo&ndo"), "\tCtrl+End", "fondo")):
        _accion(menu, etiqueta + tecla,
                lambda movimiento=movimiento: acciones.ordenar(movimiento))
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
