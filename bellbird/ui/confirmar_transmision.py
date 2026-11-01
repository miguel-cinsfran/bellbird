"""Confirmación previa a salir al aire."""

from __future__ import annotations

import wx

from bellbird.core.idioma import N_, _


_ETIQUETA_TRANSMITIR = N_("&Transmitir")


def confirmar_transmision(padre, revision) -> bool:
    """Pide confirmar el inicio del directo con la revisión a la vista.

    Mismo texto, título, etiquetas y regla de cancelación por defecto
    que la ventana Transmisión: si la revisión trae problemas, el foco
    arranca en Cancelar.
    """
    from bellbird.obs import obs_prevuelo
    frase = obs_prevuelo.frase_revision(revision)
    problemas = bool(getattr(revision, "problemas", ()))
    estilo = wx.OK | wx.CANCEL
    if problemas:
        estilo |= wx.CANCEL_DEFAULT
    dialogo = wx.MessageDialog(padre, frase, _("Antes de transmitir"), estilo)
    try:
        dialogo.SetOKCancelLabels(_(_ETIQUETA_TRANSMITIR), _("&Cancelar"))
        return dialogo.ShowModal() == wx.ID_OK
    finally:
        dialogo.Destroy()
