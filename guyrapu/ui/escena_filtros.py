"""Cuadro Filtros del micrófono: ruido, puerta y ganancia de la fuente de OBS.

No habla con OBS: recibe el estado ya leído y devuelve el que se eligió para
que la pestaña Audio lo aplique.
"""

from __future__ import annotations

import wx

from guyrapu.core.idioma import _
from guyrapu.obs.filtros_microfono import GANANCIAS, Estado
from guyrapu.ui import paleta
from guyrapu.ui.preferencias_comun import (
    fila_campo, lista_con_nombre, nombre_de_etiqueta)


class FiltrosMicrofonoDialog(wx.Dialog):
    """Pide eliminación de ruido, puerta y ganancia del micrófono."""

    def __init__(self, padre, fuente, estado):
        super().__init__(
            padre,
            title=_("Filtros del micrófono: {fuente}").format(fuente=fuente),
            name="DialogoFiltrosMicrofono")
        self._elegido = None
        self._crear_controles(estado)
        paleta.pintar_ventana(self)
        self.Centre()
        self.chk_ruido.SetFocus()

    def _crear_controles(self, estado):
        caja = wx.BoxSizer(wx.VERTICAL)
        self.chk_ruido = self._casilla(
            _("&Eliminación de ruido"), estado.eliminacion)
        self.chk_puerta = self._casilla(
            _("&Puerta anti-ruidos"), estado.puerta)
        caja.Add(self.chk_ruido, 0, wx.ALL, 6)
        caja.Add(self.chk_puerta, 0, wx.ALL, 6)
        self._crear_ganancia(caja, estado)
        self._crear_botones(caja)
        self.SetSizerAndFit(caja)
        self.btn_aceptar.Bind(wx.EVT_BUTTON, self._al_aceptar)
        self.btn_cancelar.Bind(wx.EVT_BUTTON, self._al_cancelar)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)

    def _casilla(self, etiqueta, valor):
        casilla = wx.CheckBox(
            self, label=etiqueta, name=nombre_de_etiqueta(etiqueta))
        casilla.SetValue(bool(valor))
        return casilla

    def _crear_ganancia(self, caja, estado):
        etiqueta = _("&Ganancia:")
        self.rotulo_ganancia = wx.StaticText(self, label=etiqueta)
        self.cho_ganancia = lista_con_nombre(
            self, etiqueta, [_(nombre) for _db, nombre in GANANCIAS])
        self.cho_ganancia.SetSelection(self._indice_de(estado.ganancia_db))
        fila_campo(caja, self.rotulo_ganancia, self.cho_ganancia)

    @staticmethod
    def _indice_de(db):
        for indice, (valor, _nombre) in enumerate(GANANCIAS):
            if valor == db:
                return indice
        return 0

    def _crear_botones(self, caja):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_aceptar = wx.Button(self, wx.ID_OK, _("&Aceptar"))
        self.btn_aceptar.SetDefault()
        self.btn_cancelar = wx.Button(self, wx.ID_CANCEL, _("&Cancelar"))
        fila.Add(self.btn_aceptar, 0, wx.RIGHT, 8)
        fila.Add(self.btn_cancelar, 0)
        caja.Add(fila, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

    def estado_elegido(self):
        return self._elegido

    def _al_aceptar(self, _event):
        indice = self.cho_ganancia.GetSelection()
        ganancia = GANANCIAS[indice][0] if indice >= 0 else 0
        self._elegido = Estado(
            self.chk_ruido.GetValue(), self.chk_puerta.GetValue(), ganancia)
        self.EndModal(wx.ID_OK)

    def _al_cancelar(self, _event):
        self.EndModal(wx.ID_CANCEL)

    def _al_tecla(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        event.Skip()


def pedir_filtros(padre, fuente, estado):
    """Abre el cuadro y devuelve el estado elegido, o None si se cancela."""
    dialogo = FiltrosMicrofonoDialog(padre, fuente, estado)
    try:
        if dialogo.ShowModal() == wx.ID_OK:
            return dialogo.estado_elegido()
        return None
    finally:
        dialogo.Destroy()
