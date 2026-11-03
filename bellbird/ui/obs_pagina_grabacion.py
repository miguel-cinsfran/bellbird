"""Pestaña Grabación del panel de OBS: grabar y ver lo grabado."""

from __future__ import annotations

import wx

from bellbird.core.idioma import _
from bellbird.obs.estado_grabacion import resumir
from bellbird.obs.estado_panel import EstadoPanel
from bellbird.ui import gui_transmitir
from bellbird.ui.control_grabacion import ControlGrabacion
from bellbird.ui.gui_grabaciones import PanelGrabaciones
from bellbird.ui.preferencias_comun import (
    CampoEstado, boton, fila_horizontal)


class PaginaGrabacion(wx.Panel):

    def __init__(self, parent, principal, gestor, operaciones, al_cambiar,
                 al_actualizar):
        super().__init__(parent, name="PaginaGrabacion")
        self._principal = principal
        self._al_cambiar = al_cambiar
        self._al_actualizar = al_actualizar
        self._estado_actual = EstadoPanel("", "listo", ())
        self._crear_controles(gestor, operaciones)
        self._enlazar_eventos()
        self.acciones = (
            self._grabacion.boton, self._grabacion.pausar, self.chk_grabar,
            self.btn_actualizar, self.lista)

    def _crear_controles(self, gestor, operaciones):
        caja = wx.BoxSizer(wx.VERTICAL)
        rotulo = wx.StaticText(self, label=_("&Estado:"))
        self.txt_estado = CampoEstado(self, _("Estado"))
        caja.Add(rotulo, 0, wx.ALL, 6)
        caja.Add(self.txt_estado, 0, wx.EXPAND | wx.LEFT | wx.RIGHT
                 | wx.BOTTOM, 6)
        self._grabacion = ControlGrabacion(
            self, operaciones, gestor, self._grabacion_cambiada, self)
        caja.Add(fila_horizontal((self._grabacion.boton,
                                  self._grabacion.pausar)), 0, wx.ALL, 6)
        self.chk_grabar = wx.CheckBox(
            self, label=_("Grabar ta&mbién al transmitir"),
            name=_("Grabar también al transmitir"))
        self.chk_grabar.SetValue(
            bool(self._principal._config.get("grabar_al_transmitir", False)))
        caja.Add(self.chk_grabar, 0, wx.ALL, 10)
        self.btn_actualizar = boton(
            self, _("Ac&tualizar estado"), _("Actualizar estado"))
        caja.Add(self.btn_actualizar, 0, wx.ALL, 10)
        self.lista = PanelGrabaciones(self)
        caja.Add(self.lista, 1, wx.EXPAND | wx.ALL, 6)
        self.SetSizer(caja)

    def _enlazar_eventos(self):
        self.chk_grabar.Bind(wx.EVT_CHECKBOX, self._alternar_casilla)
        self.btn_actualizar.Bind(wx.EVT_BUTTON, self._actualizar)

    def _grabacion_cambiada(self):
        self.lista.poblar()
        self._al_cambiar()

    def _alternar_casilla(self, event):
        gui_transmitir.alternar_grabar_al_transmitir(self._principal)
        event.Skip()

    def _actualizar(self, event):
        self._al_actualizar()

    def aplicar(self, datos):
        """Pone el estado de grabación y las líneas que lo acompañan."""
        self._grabacion.fijar(
            bool(datos.grabacion.get("outputActive", False)),
            bool(datos.grabacion.get("outputPaused", False)))
        self.mostrar_estado(resumir(
            datos.grabacion, datos.transmision, datos.escena,
            datos.microfono, datos.silenciado))

    def mostrar_estado(self, estado):
        self._estado_actual = estado
        self.txt_estado.mostrar(estado)

    @property
    def titular(self):
        return self._estado_actual.titular
