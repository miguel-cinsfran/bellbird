"""Pestaña Destinos: los canales de la cuenta de Restream.

Muestra los destinos con su plataforma y si están activos, deja agregar uno
en la página de Restream o uno manual, activarlo o desactivarlo, cambiar su
título, eliminarlo de la cuenta y releer la lista.
"""

from __future__ import annotations

import webbrowser

import wx

from guyrapu.core import sonidos_eventos
from guyrapu.core.idioma import _
from guyrapu.ui import confirmar
from guyrapu.ui.accesibilidad import nombre_accesible
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
                 al_agregar_manual=None):
        super().__init__(parent, name="PaginaDestinosRestream")
        self._al_agregar = al_agregar
        self._al_eliminar = al_eliminar
        self._al_actualizar = al_actualizar
        self._al_activar = al_activar or (lambda: None)
        self._al_cambiar_titulo = al_cambiar_titulo or (lambda: None)
        self._al_agregar_manual = al_agregar_manual or (lambda: None)
        self.destinos = []
        self._crear_ui()

    def _crear_ui(self):
        vs = wx.BoxSizer(wx.VERTICAL)
        self._crear_lista(vs)
        self._crear_botones(vs)
        self.SetSizer(vs)
        self._actualizar_activar()

    def _crear_lista(self, vs):
        self.lista = wx.ListBox(
            self, style=wx.LB_SINGLE | wx.LB_HSCROLL, name=_("Destinos"))
        nombre_accesible(self.lista, _("Destinos"))
        instalar_busqueda_tipo(
            self.lista,
            lambda: [self.lista.GetString(i) for i
                     in range(self.lista.GetCount())])
        self.lista.Bind(wx.EVT_KEY_DOWN, self._al_tecla)
        self.lista.Bind(wx.EVT_LISTBOX, self._al_elegir_destino)
        vs.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)

    def _crear_botones(self, vs):
        definiciones = (
            ("btn_agregar", _("&Agregar destino…"), _("Agregar destino"),
             self._agregar),
            ("btn_agregar_manual", _("Agregar destino &manual…"),
             _("Agregar destino manual"), self._agregar_manual),
            ("btn_activar", _("Ac&tivar destino"), _("Activar destino"),
             self._activar),
            ("btn_titulo", _("Cambiar tít&ulo…"), _("Cambiar título"),
             self._cambiar_titulo),
            ("btn_eliminar", _("&Eliminar destino"), _("Eliminar destino"),
             self._al_eliminar),
            ("btn_actualizar", _("A&ctualizar"), _("Actualizar"),
             self._al_actualizar),
        )
        botones = []
        for atributo, etiqueta, nombre, accion in definiciones:
            boton = wx.Button(self, label=etiqueta, name=nombre)
            nombre_accesible(boton, nombre)
            boton.Bind(
                wx.EVT_BUTTON, lambda evento, accion=accion: accion())
            setattr(self, atributo, boton)
            botones.append(boton)
        vs.Add(fila_horizontal(botones), 0, wx.ALL, 10)

    def mostrar(self, destinos, elegido=None):
        self.destinos = list(destinos)
        seleccion = self.lista.GetSelection()
        self.lista.Set([texto_de_destino(canal)
                        for canal in self.destinos])
        if elegido is not None:
            seleccion = next(
                (indice for indice, canal in enumerate(self.destinos)
                 if canal.id == elegido), seleccion)
        if 0 <= seleccion < len(self.destinos):
            self.lista.SetSelection(seleccion)
        self._actualizar_activar()

    def seleccionado(self):
        indice = self.lista.GetSelection()
        if 0 <= indice < len(self.destinos):
            return self.destinos[indice]
        return None

    def _actualizar_activar(self):
        destino = self.seleccionado()
        activo = destino is not None and destino.activo
        self.btn_activar.SetLabel(
            _("Desac&tivar destino") if activo else _("Ac&tivar destino"))
        nombre_accesible(
            self.btn_activar,
            _("Desactivar destino") if activo else _("Activar destino"))
        self.btn_activar.Enable(destino is not None)

    def _al_elegir_destino(self, evento):
        self._actualizar_activar()
        evento.Skip()

    def _activar(self):
        self._al_activar()

    def _cambiar_titulo(self):
        self._al_cambiar_titulo()

    def _agregar_manual(self):
        self._al_agregar_manual()

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
