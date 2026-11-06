"""Cuadros de confirmación nativos con los botones en el idioma de la app."""

from __future__ import annotations

import wx


# Nombres separados para que las pruebas sustituyan el cuadro sin abrir uno.
MessageDialog = wx.MessageDialog
OK = wx.OK
CANCEL = wx.CANCEL
CANCEL_DEFAULT = wx.CANCEL_DEFAULT
CENTRE = wx.CENTRE
ICON_QUESTION = wx.ICON_QUESTION
ICON_INFORMATION = wx.ICON_INFORMATION
ICON_WARNING = wx.ICON_WARNING
ICON_ERROR = wx.ICON_ERROR
ID_OK = wx.ID_OK
ID_CANCEL = wx.ID_CANCEL


def preguntar(padre, mensaje, titulo, etiqueta_si, etiqueta_no, *,
              icono=ICON_QUESTION, predeterminado_si=True,
              centrar=False) -> bool:
    """Pregunta con dos botones propios y dice si se eligió el primero."""
    estilo = OK | CANCEL | icono
    if not predeterminado_si:
        estilo |= CANCEL_DEFAULT
    if centrar:
        estilo |= CENTRE
    dialogo = MessageDialog(padre, mensaje, titulo, estilo)
    try:
        dialogo.SetOKCancelLabels(etiqueta_si, etiqueta_no)
        return dialogo.ShowModal() == ID_OK
    finally:
        dialogo.Destroy()


def avisar(padre, mensaje, titulo, etiqueta_ok, *,
           icono=ICON_INFORMATION) -> None:
    """Muestra un aviso de un solo botón con el texto dado."""
    dialogo = MessageDialog(padre, mensaje, titulo, OK | icono)
    try:
        dialogo.SetOKLabel(etiqueta_ok)
        dialogo.ShowModal()
    finally:
        dialogo.Destroy()
