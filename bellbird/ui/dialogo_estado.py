"""Cuadro con el estado de la sesión en una lista, para recorrer con flechas.

Su única razón para cambiar es cómo se muestra el estado en lista. Recibe
las líneas ya armadas y no consulta nada por su cuenta: la foto es la del
momento de abrir.
"""

from __future__ import annotations

import wx

from bellbird.core.idioma import N_, _
from bellbird.ui import paleta
from bellbird.ui.accesibilidad import nombre_accesible

TITULO = N_("Estado de la sesión")
SIN_ESTADO = N_("Sin información de estado.")
CERRAR = N_("Cerrar")


class DialogoEstado(wx.Dialog):
    """El estado de la sesión, una línea por elemento de la lista."""

    def __init__(self, parent, lineas):
        super().__init__(parent, title=_(TITULO), name="DialogoEstado")
        self._lineas = list(lineas) or [_(SIN_ESTADO)]
        self._crear_controles()
        self.SetEscapeId(wx.ID_CANCEL)
        paleta.pintar_ventana(self)
        self.Centre()

    def _crear_controles(self):
        panel = wx.Panel(self, name="PanelEstado")
        self.panel = panel
        vs = wx.BoxSizer(wx.VERTICAL)

        self.lista = wx.ListBox(panel, choices=self._lineas, name=_(TITULO))
        nombre_accesible(self.lista, _(TITULO))
        vs.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)

        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_cerrar = wx.Button(
            panel, wx.ID_CANCEL, _("&Cerrar"), name=_(CERRAR))
        fila.Add(self.btn_cerrar, 0)
        vs.Add(fila, 0, wx.ALL, 8)

        panel.SetSizer(vs)
        self.lista.SetSelection(0)
        self.lista.SetFocus()


def _ventana_con_foco():
    return wx.Window.FindFocus()


def _devolver_foco(foco, padre):
    try:
        if foco is not None:
            foco.SetFocus()
        else:
            padre.SetFocus()
    except (RuntimeError, AttributeError):
        # La ventana que tenía el foco pudo cerrarse mientras el cuadro
        # estaba abierto; la principal también pudo irse.
        return


def abrir_estado(padre, lineas):
    """Abre el cuadro y, al cerrarlo, devuelve el foco a la ventana."""
    foco = _ventana_con_foco()
    dialogo = DialogoEstado(padre, lineas)
    try:
        dialogo.ShowModal()
    finally:
        dialogo.Destroy()
        _devolver_foco(foco, padre)
