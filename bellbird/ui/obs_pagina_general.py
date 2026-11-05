"""Pestaña General del panel de OBS: el estado completo de OBS."""

from __future__ import annotations

import wx

from bellbird.core.idioma import _
from bellbird.ui.accesibilidad import nombre_accesible
from bellbird.ui.preferencias_comun import (
    boton, nombre_de_etiqueta)


class PaginaGeneral(wx.Panel):

    def __init__(self, parent, al_actualizar, al_mostrar):
        super().__init__(parent, name="PaginaGeneral")
        self._al_actualizar = al_actualizar
        self._al_mostrar = al_mostrar
        self._crear_controles()
        self._enlazar_eventos()
        self.acciones = (self.txt_estado, self.btn_actualizar, self.btn_mostrar)

    def _crear_controles(self):
        caja = wx.BoxSizer(wx.VERTICAL)
        rotulo = wx.StaticText(self, label=_("&Estado:"))
        self.txt_estado = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY,
            name=_("Estado"))
        nombre_accesible(self.txt_estado, _("Estado"))
        self.txt_estado.SetMinSize((-1, 150))
        caja.Add(rotulo, 0, wx.ALL, 6)
        caja.Add(self.txt_estado, 1, wx.EXPAND | wx.LEFT | wx.RIGHT
                 | wx.BOTTOM, 6)
        self.btn_actualizar = boton(
            self, _("Ac&tualizar estado"), nombre_de_etiqueta(
                _("Ac&tualizar estado")))
        self.btn_mostrar = boton(
            self, _("Mostrar &OBS"), nombre_de_etiqueta(_("Mostrar &OBS")))
        fila = wx.BoxSizer(wx.HORIZONTAL)
        fila.Add(self.btn_actualizar, 0, wx.ALL, 4)
        fila.Add(self.btn_mostrar, 0, wx.ALL, 4)
        caja.Add(fila, 0, wx.ALL, 6)
        self.SetSizer(caja)

    def _enlazar_eventos(self):
        self.btn_actualizar.Bind(wx.EVT_BUTTON, self._actualizar)
        self.btn_mostrar.Bind(wx.EVT_BUTTON, self._mostrar)

    def _actualizar(self, event):
        self._al_actualizar()

    def _mostrar(self, event):
        self._al_mostrar()

    def mostrar(self, lineas):
        self.txt_estado.SetValue("\n".join(lineas or ()))

    def texto(self):
        return self.txt_estado.GetValue()
