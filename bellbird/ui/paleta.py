"""Pinta las ventanas grises con la paleta crema y salvia.

Recorre la ventana y sus hijos en profundidad y aplica `gui._pintar`
según la clase del control, igual que `gui_historial.py` hace a mano:
la ventana, paneles y grupos llevan fondo crema, los campos el beige,
los botones su tono y los textos el gris oscuro. Lo que no es texto
ni campo (la vista previa, el vídeo) no se toca. Con el contraste alto
de Windows no hace nada: mandan los colores del sistema.
"""

from __future__ import annotations

import wx

from bellbird.ui import gui

_FONDO = (wx.Dialog, wx.Frame, wx.Panel, wx.ScrolledWindow, wx.StaticBox)
_CAMPOS = (wx.TextCtrl, wx.ListBox, wx.ListCtrl, wx.Choice, wx.ComboBox,
           wx.SpinCtrl)
_BOTONES = (wx.Button,)
_SOLO_TEXTO = (wx.StaticText, wx.CheckBox, wx.RadioButton)


def pintar_ventana(ventana) -> None:
    """Aplica la paleta a la ventana y a todos sus hijos, en profundidad."""
    if gui.ALTO_CONTRASTE:
        return
    pendientes = [ventana]
    while pendientes:
        control = pendientes.pop()
        if isinstance(control, _FONDO):
            gui._pintar(control, gui._T.bg, gui._T.text)
        elif isinstance(control, _CAMPOS):
            gui._pintar(control, gui._T.field, gui._T.text)
        elif isinstance(control, _BOTONES):
            gui._pintar(control, gui._T.btn, gui._T.btn_t)
        elif isinstance(control, _SOLO_TEXTO):
            gui._pintar(control, fg=gui._T.text)
        pendientes.extend(reversed(control.GetChildren()))
    ventana.Refresh()
