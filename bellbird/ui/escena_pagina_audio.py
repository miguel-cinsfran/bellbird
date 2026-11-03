"""Pestaña Audio de la ventana Escena: silenciar y elegir el micrófono."""

from __future__ import annotations

import wx

from bellbird.core.idioma import _
from bellbird.ui import gui_microfono
from bellbird.ui.preferencias_comun import boton, nombre_de_etiqueta


class PaginaAudio(wx.Panel):

    def __init__(self, parent, principal, gestor, operaciones):
        super().__init__(parent, name="PaginaAudio")
        self._principal = principal
        self._crear_controles()
        self._silencio = gui_microfono.ControlSilencio(
            gestor, self.chk_silenciar, operaciones,
            lambda: gui_microfono.microfono_preferido(principal),
            lambda: None)
        self.acciones = (self.chk_silenciar, self.btn_microfono)
        self._enlazar_eventos()

    def _crear_controles(self):
        caja = wx.BoxSizer(wx.VERTICAL)
        self.chk_silenciar = wx.CheckBox(
            self, label=_("Si&lenciar micrófono"),
            name=nombre_de_etiqueta(_("Si&lenciar micrófono")))
        self.btn_microfono = boton(
            self, _("Elegir &micrófono…"),
            nombre_de_etiqueta(_("Elegir &micrófono…")))
        fila = wx.BoxSizer(wx.HORIZONTAL)
        fila.Add(self.chk_silenciar, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 6)
        fila.Add(self.btn_microfono, 0, wx.ALL, 6)
        caja.Add(fila, 0, wx.ALL, 8)
        self.SetSizer(caja)

    def _enlazar_eventos(self):
        self.btn_microfono.Bind(
            wx.EVT_BUTTON,
            lambda evento: gui_microfono.abrir_microfono_obs(
                self._principal, al_cerrar=self.btn_microfono.SetFocus))

    def fijar(self, silenciado):
        self._silencio.fijar(silenciado)
