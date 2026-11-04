"""Pestaña Destinos: los canales de la cuenta de Restream.

Muestra los destinos con su plataforma y si están activos, deja agregar uno
en la página de Restream, eliminarlo de la cuenta y releer la lista.
"""

from __future__ import annotations

import webbrowser

import wx

from bellbird.core import sonidos_eventos
from bellbird.core.idioma import _
from bellbird.ui.accesibilidad import nombre_accesible
from bellbird.ui.busqueda_teclado import instalar_busqueda_tipo
from bellbird.ui.preferencias_comun import fila_horizontal
from bellbird.voice import sound_player as _snd

# Página donde Restream agrega los canales de la cuenta.
URL_DESTINOS = "https://app.restream.io/channels"
abrir_navegador = webbrowser.open


def texto_de_destino(canal) -> str:
    if canal.activo:
        return canal.texto
    return _("{destino}, desactivado").format(destino=canal.texto)


class PaginaDestinos(wx.Panel):

    def __init__(self, parent, al_agregar, al_eliminar, al_actualizar):
        super().__init__(parent, name="PaginaDestinosRestream")
        self._al_agregar = al_agregar
        self._al_eliminar = al_eliminar
        self._al_actualizar = al_actualizar
        self.destinos = []
        self._crear_ui()

    def _crear_ui(self):
        vs = wx.BoxSizer(wx.VERTICAL)
        self.lista = wx.ListBox(
            self, style=wx.LB_SINGLE | wx.LB_HSCROLL, name=_("Destinos"))
        nombre_accesible(self.lista, _("Destinos"))
        instalar_busqueda_tipo(
            self.lista,
            lambda: [self.lista.GetString(i) for i
                     in range(self.lista.GetCount())])
        self.lista.Bind(wx.EVT_KEY_DOWN, self._al_tecla)
        vs.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)

        self.btn_agregar = wx.Button(
            self, label=_("&Agregar destino…"), name=_("Agregar destino"))
        self.btn_eliminar = wx.Button(
            self, label=_("&Eliminar destino"), name=_("Eliminar destino"))
        self.btn_actualizar = wx.Button(
            self, label=_("A&ctualizar"), name=_("Actualizar"))
        for boton in (self.btn_agregar, self.btn_eliminar,
                      self.btn_actualizar):
            nombre_accesible(boton, boton.GetName())
        self.btn_agregar.Bind(wx.EVT_BUTTON, lambda evento: self._agregar())
        self.btn_eliminar.Bind(
            wx.EVT_BUTTON, lambda evento: self._al_eliminar())
        self.btn_actualizar.Bind(
            wx.EVT_BUTTON, lambda evento: self._al_actualizar())
        vs.Add(fila_horizontal((self.btn_agregar, self.btn_eliminar,
                                self.btn_actualizar)), 0, wx.ALL, 10)
        self.SetSizer(vs)

    def mostrar(self, destinos):
        self.destinos = list(destinos)
        seleccion = self.lista.GetSelection()
        self.lista.Set([texto_de_destino(canal)
                        for canal in self.destinos])
        if 0 <= seleccion < len(self.destinos):
            self.lista.SetSelection(seleccion)

    def seleccionado(self):
        indice = self.lista.GetSelection()
        if 0 <= indice < len(self.destinos):
            return self.destinos[indice]
        return None

    def pregunta(self, destino):
        return _("¿Eliminar {destino} de la cuenta de Restream? Los perfiles "
                 "de Restream que lo usan dejan de transmitir ahí.").format(
                     destino=destino)

    def confirmar(self, destino):
        dialogo = wx.MessageDialog(
            self, self.pregunta(destino), _("Eliminar destino"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        try:
            return dialogo.ShowModal() == wx.ID_YES
        finally:
            dialogo.Destroy()

    def _agregar(self):
        abrir_navegador(URL_DESTINOS)
        self._al_agregar()

    def _al_tecla(self, evento):
        lista = evento.GetEventObject()
        try:
            seleccion, total = lista.GetSelection(), lista.GetCount()
        except Exception:
            seleccion, total = -1, 0
        tecla = evento.GetKeyCode()
        if sonidos_eventos.es_orilla(tecla, seleccion, total):
            _snd.reproducir("orilla")
        if tecla == wx.WXK_DELETE:
            self._al_eliminar()
        else:
            evento.Skip()
