"""Cuadro Tamaño de la fuente del Panel de OBS: pedir ancho y alto.

No habla con OBS: devuelve lo elegido y la pestaña Fuentes aplica el tamaño.
"""

from __future__ import annotations

import wx

from bellbird.core.idioma import _
from bellbird.ui import paleta
from bellbird.ui.accesibilidad import ContadorAccesible
from bellbird.ui.preferencias_comun import fila_grilla, grilla_campos


class TamanoFuenteDialog(wx.Dialog):
    """Pide el ancho y el alto de una fuente, con el foco en Ancho."""

    def __init__(self, padre, ancho, alto):
        super().__init__(padre, title=_("Tamaño de la fuente"),
                         name="DialogoTamanoFuente")
        self._elegido = None
        self._crear_controles(ancho, alto)
        paleta.pintar_ventana(self)
        self.Centre()
        self.sp_ancho.SetFocus()

    def _crear_controles(self, ancho, alto):
        vertical = wx.BoxSizer(wx.VERTICAL)
        grilla = grilla_campos()
        rotulo_ancho = wx.StaticText(self, label=_("&Ancho:"))
        self.sp_ancho = ContadorAccesible(
            self, min=100, max=4000, initial=ancho,
            name=_("Ancho en píxeles"))
        fila_grilla(grilla, rotulo_ancho, self.sp_ancho)
        rotulo_alto = wx.StaticText(self, label=_("A&lto:"))
        self.sp_alto = ContadorAccesible(
            self, min=100, max=4000, initial=alto,
            name=_("Alto en píxeles"))
        fila_grilla(grilla, rotulo_alto, self.sp_alto)
        vertical.Add(grilla, 0, wx.EXPAND | wx.ALL, 10)
        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_aceptar = wx.Button(self, wx.ID_OK, _("Aceptar"))
        self.btn_aceptar.SetDefault()
        self.btn_cancelar = wx.Button(self, wx.ID_CANCEL, _("Cancelar"))
        fila.Add(self.btn_aceptar, 0, wx.RIGHT, 8)
        fila.Add(self.btn_cancelar, 0)
        vertical.Add(fila, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        self.SetSizerAndFit(vertical)
        self.btn_aceptar.Bind(wx.EVT_BUTTON, self._al_aceptar)
        self.btn_cancelar.Bind(wx.EVT_BUTTON, self._al_cancelar)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)

    def tamano_elegido(self):
        return self._elegido

    def _al_aceptar(self, _event):
        self._elegido = (self.sp_ancho.GetValue(), self.sp_alto.GetValue())
        self.EndModal(wx.ID_OK)

    def _al_cancelar(self, _event):
        self.EndModal(wx.ID_CANCEL)

    def _al_tecla(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        event.Skip()


def pedir_tamano(padre, ancho, alto):
    """Abre el cuadro y devuelve (ancho, alto), o None si se cancela."""
    dialogo = TamanoFuenteDialog(padre, ancho, alto)
    try:
        if dialogo.ShowModal() == wx.ID_OK:
            return dialogo.tamano_elegido()
        return None
    finally:
        dialogo.Destroy()
