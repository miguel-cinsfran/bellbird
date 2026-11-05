"""Pestaña Grabación del panel de OBS: grabar y ver lo grabado."""

from __future__ import annotations

import wx

from guyrapu.core.idioma import _
from guyrapu.ui import gui_transmitir
from guyrapu.ui.control_grabacion import ControlGrabacion
from guyrapu.ui.gui_grabaciones import PanelGrabaciones
from guyrapu.ui.preferencias_comun import fila_horizontal


class PaginaGrabacion(wx.Panel):

    def __init__(self, parent, principal, gestor, operaciones, al_cambiar):
        super().__init__(parent, name="PaginaGrabacion")
        self._principal = principal
        self._al_cambiar = al_cambiar
        self._crear_controles(gestor, operaciones)
        self._enlazar_eventos()
        self.acciones = (
            self._grabacion.boton, self._grabacion.pausar, self.chk_grabar,
            self.lista)

    def _crear_controles(self, gestor, operaciones):
        caja = wx.BoxSizer(wx.VERTICAL)
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
        self.lista = PanelGrabaciones(self)
        caja.Add(self.lista, 1, wx.EXPAND | wx.ALL, 6)
        self.SetSizer(caja)

    def _enlazar_eventos(self):
        self.chk_grabar.Bind(wx.EVT_CHECKBOX, self._alternar_casilla)

    def _grabacion_cambiada(self):
        self.lista.poblar()
        self._al_cambiar()

    def releer_lista(self):
        self.lista.poblar()

    def _alternar_casilla(self, event):
        gui_transmitir.alternar_grabar_al_transmitir(self._principal)
        event.Skip()

    def aplicar(self, datos):
        """Pone el estado de grabación en sus botones."""
        self._grabacion.fijar(
            bool(datos.grabacion.get("outputActive", False)),
            bool(datos.grabacion.get("outputPaused", False)))
