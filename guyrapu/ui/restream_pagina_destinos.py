"""Pestaña Destinos: los canales de la cuenta de Restream.

Muestra los destinos con su plataforma y si están activos. Las acciones de
la fila viven en su menú contextual, como en la pestaña Escena del Panel de
OBS: activar, cambiar el título, abrir o copiar el enlace y eliminar. Los
botones son los que no dependen de la fila: agregar un destino y actualizar.
"""

from __future__ import annotations

import webbrowser
from types import SimpleNamespace

import wx

from guyrapu.core import sonidos_eventos
from guyrapu.core.idioma import _
from guyrapu.ui import confirmar, restream_menus
from guyrapu.ui.accesibilidad import anunciar, nombre_accesible
from guyrapu.ui.busqueda_teclado import instalar_busqueda_tipo
from guyrapu.ui.preferencias_comun import fila_horizontal
from guyrapu.voice import sound_player as _snd

# Página donde Restream agrega los canales de la cuenta.
URL_DESTINOS = "https://app.restream.io/channels"
abrir_navegador = webbrowser.open


def texto_de_destino(canal) -> str:
    if canal.activo:
        return canal.texto
    return _("{destino}, desactivado").format(destino=canal.texto)


class PaginaDestinos(wx.Panel):

    def __init__(self, parent, al_agregar, al_eliminar, al_actualizar,
                 al_activar=None, al_cambiar_titulo=None,
                 al_agregar_manual=None, al_abrir=None, al_copiar=None,
                 esta_conectada=None):
        super().__init__(parent, name="PaginaDestinosRestream")
        self._al_agregar = al_agregar
        self._al_eliminar = al_eliminar
        self._al_actualizar = al_actualizar
        self._al_activar = al_activar or (lambda: None)
        self._al_cambiar_titulo = al_cambiar_titulo or (lambda: None)
        self._al_agregar_manual = al_agregar_manual or (lambda: None)
        self._al_abrir = al_abrir or (lambda: None)
        self._al_copiar = al_copiar or (lambda: None)
        self._esta_conectada = esta_conectada
        self.destinos = []
        self.leidos = False
        self._crear_ui()

    def _crear_ui(self):
        vs = wx.BoxSizer(wx.VERTICAL)
        self._crear_lista(vs)
        self._crear_botones(vs)
        self.SetSizer(vs)

    def _crear_lista(self, vs):
        self.lista = wx.ListBox(
            self, style=wx.LB_SINGLE | wx.LB_HSCROLL, name=_("Destinos"))
        nombre_accesible(self.lista, _("Destinos"))
        instalar_busqueda_tipo(
            self.lista,
            lambda: [self.lista.GetString(i) for i
                     in range(self.lista.GetCount())])
        self.lista.Bind(wx.EVT_KEY_DOWN, self._al_tecla)
        self.lista.Bind(wx.EVT_CONTEXT_MENU, self._menu_contextual)
        self.lista.Bind(wx.EVT_SET_FOCUS, self._al_foco)
        self.lista.Bind(wx.EVT_LISTBOX, self._al_elegir_destino)
        vs.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)

    def _crear_botones(self, vs):
        self.btn_agregar = wx.Button(
            self, label=_("&Agregar destino…"), name=_("Agregar destino"))
        self.btn_actualizar = wx.Button(
            self, label=_("A&ctualizar"), name=_("Actualizar"))
        for boton in (self.btn_agregar, self.btn_actualizar):
            nombre_accesible(boton, boton.GetName())
        self.btn_agregar.Bind(wx.EVT_BUTTON, self._abrir_menu_agregar)
        self.btn_actualizar.Bind(
            wx.EVT_BUTTON, lambda evento: self._al_actualizar())
        vs.Add(fila_horizontal((self.btn_agregar, self.btn_actualizar)),
               0, wx.ALL, 10)

    def mostrar(self, destinos, elegido=None):
        self.destinos = list(destinos)
        self.leidos = True
        seleccion = self.lista.GetSelection()
        self.lista.Set([texto_de_destino(canal)
                        for canal in self.destinos])
        if elegido is not None:
            seleccion = next(
                (indice for indice, canal in enumerate(self.destinos)
                 if canal.id == elegido), seleccion)
        if 0 <= seleccion < len(self.destinos):
            self.lista.SetSelection(seleccion)

    def seleccionado(self):
        indice = self.lista.GetSelection()
        if 0 <= indice < len(self.destinos):
            return self.destinos[indice]
        return None

    def _al_elegir_destino(self, evento):
        evento.Skip()

    def _al_foco(self, evento):
        if not self.lista.GetCount() and not self._conectada():
            self._avisar_sin_cuenta()
        evento.Skip()

    def _conectada(self):
        if self._esta_conectada is None:
            return True
        try:
            return bool(self._esta_conectada())
        except Exception:
            return False

    def _avisar_sin_cuenta(self):
        padre = self.GetParent()
        if getattr(padre, "_sin_cuenta_anunciado", False):
            return
        padre._sin_cuenta_anunciado = True
        anunciar(_("Sin cuenta de Restream. Conéctala en la pestaña Cuenta."))

    def _activar(self):
        self._al_activar()

    def _cambiar_titulo(self):
        self._al_cambiar_titulo()

    def _agregar_manual(self):
        self._al_agregar_manual()

    def _abrir_enlace(self):
        self._al_abrir()

    def _copiar_enlace(self):
        self._al_copiar()

    def pregunta(self, destino):
        return _("¿Eliminar {destino} de la cuenta de Restream? Los perfiles "
                 "de Restream que lo usan dejan de transmitir ahí.").format(
                     destino=destino)

    def confirmar(self, destino):
        return confirmar.preguntar(
            self, self.pregunta(destino), _("Eliminar destino"),
            _("&Eliminar"), _("&Cancelar"), predeterminado_si=False)

    def _agregar(self):
        abrir_navegador(URL_DESTINOS)
        self._al_agregar()

    def _abrir_menu_agregar(self, evento):
        menu = restream_menus.menu_agregar(self._agregar,
                                           self._agregar_manual)
        self.btn_agregar.PopupMenu(menu)
        menu.Destroy()

    def _menu_contextual(self, evento):
        destino = self.seleccionado()
        if destino is None:
            anunciar(_("Sin selección"))
            return
        acciones = SimpleNamespace(
            activar=lambda _marcado: self._activar(),
            cambiar_titulo=self._cambiar_titulo,
            abrir=self._abrir_enlace,
            copiar=self._copiar_enlace,
            eliminar=self._al_eliminar)
        menu = restream_menus.menu_destino(destino, acciones)
        self.lista.PopupMenu(menu)
        menu.Destroy()
        evento.Skip()

    def _al_tecla(self, evento):
        lista = evento.GetEventObject()
        try:
            seleccion, total = lista.GetSelection(), lista.GetCount()
        except Exception:
            seleccion, total = -1, 0
        tecla = evento.GetKeyCode()
        if sonidos_eventos.es_orilla(tecla, seleccion, total):
            _snd.reproducir("orilla")
        if tecla == wx.WXK_SPACE:
            self._activar()
        elif tecla == wx.WXK_DELETE:
            self._al_eliminar()
        elif tecla == wx.WXK_F5:
            self._al_actualizar()
        elif (tecla == wx.WXK_WINDOWS_MENU
              or (tecla == wx.WXK_F10 and evento.ShiftDown())):
            self._menu_contextual(evento)
        else:
            evento.Skip()
