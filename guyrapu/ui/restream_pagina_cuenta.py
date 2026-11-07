"""Pestaña Cuenta: el estado de la cuenta de Restream y sus destinos.

Deja conectar, volver a autorizar o desconectar con lo que la ventana le
inyecta. El trabajo de red lo hace la ventana, en un hilo aparte.
"""

from __future__ import annotations

import wx

from guyrapu.core.idioma import _
from guyrapu.restream import resumen_cuenta
from guyrapu.ui import confirmar
from guyrapu.ui.accesibilidad import nombre_accesible
from guyrapu.ui.preferencias_comun import (
    CampoEstado, fila_horizontal, mostrar_control)


class PaginaCuenta(wx.Panel):

    def __init__(self, parent, al_conectar, al_reautorizar, al_desconectar):
        super().__init__(parent, name="PaginaCuentaRestream")
        self._al_conectar = al_conectar
        self._al_reautorizar = al_reautorizar
        self._al_desconectar = al_desconectar
        self._crear_ui()

    def _crear_ui(self):
        vs = wx.BoxSizer(wx.VERTICAL)
        self.txt_estado = CampoEstado(
            self, _("Estado de la cuenta"), lineas=2)
        nombre_accesible(self.txt_estado, _("Estado de la cuenta"))
        vs.Add(self.txt_estado, 0, wx.EXPAND | wx.ALL, 10)

        self.btn_conectar = wx.Button(
            self, label=_("&Conectar"), name=_("Conectar"))
        self.btn_reautorizar = wx.Button(
            self, label=_("&Volver a autorizar"),
            name=_("Volver a autorizar"))
        self.btn_desconectar = wx.Button(
            self, label=_("&Desconectar"), name=_("Desconectar"))
        for boton in (self.btn_conectar, self.btn_reautorizar,
                      self.btn_desconectar):
            nombre_accesible(boton, boton.GetName())
        self.btn_conectar.Bind(
            wx.EVT_BUTTON, lambda evento: self._al_conectar())
        self.btn_reautorizar.Bind(
            wx.EVT_BUTTON, lambda evento: self._al_reautorizar())
        self.btn_desconectar.Bind(
            wx.EVT_BUTTON, lambda evento: self._desconectar())
        vs.Add(fila_horizontal((self.btn_conectar, self.btn_reautorizar,
                                self.btn_desconectar)), 0, wx.ALL, 10)
        self.SetSizer(vs)

    def mostrar(self, conectada, nombre, destinos, perfiles, youtube="",
                errores=()):
        self.txt_estado.SetValue(resumen_cuenta.resumen(
            conectada, nombre, destinos, perfiles, youtube, errores))
        mostrar_control(self.btn_conectar, not conectada, self)
        mostrar_control(self.btn_reautorizar, conectada, self)
        mostrar_control(self.btn_desconectar, conectada, self)
        self.Layout()

    def fijar_botones(self, habilitados):
        for boton in (self.btn_conectar, self.btn_reautorizar,
                      self.btn_desconectar):
            boton.Enable(habilitados)

    def _desconectar(self):
        if not confirmar.preguntar(
                self,
                _("¿Desconectar la cuenta de Restream? Para volver a usarla "
                  "hay que iniciar sesión otra vez en el navegador."),
                _("Desconectar cuenta"), _("&Desconectar"), _("&Cancelar"),
                predeterminado_si=False):
            return
        self._al_desconectar()
