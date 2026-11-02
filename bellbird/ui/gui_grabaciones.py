"""Ventana «Grabaciones»: lo que la app grabó y todavía está en el disco.

Su única razón para cambiar: la ventana Grabaciones. La lista, las teclas
y el foco siguen el patrón de `HistorialDialog`, y abrir un archivo o su
carpeta, el de las acciones de descargas.
"""

from __future__ import annotations

import os
import subprocess

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import N_, _
from bellbird.obs import grabaciones
from bellbird.ui import paleta
from bellbird.ui.accesibilidad import anunciar, nombre_accesible
from bellbird.ui.gui import copiar_al_portapapeles
from bellbird.ui.preferencias_comun import boton, nombre_de_etiqueta
from bellbird.voice import sound_player

logger = diagnostico.obtener_logger(__name__)

_NO_HAY = N_("No hay grabaciones guardadas.")
_ABRIR = N_("&Abrir")
_ABRIR_CARPETA = N_("Abrir ca&rpeta")
_COPIAR_RUTA = N_("&Copiar ruta")
_ELIMINAR = N_("E&liminar de la lista")
_CERRAR = N_("Cerrar")


class GrabacionesDialog(wx.Dialog):
    """Lista las grabaciones de la app, de la más nueva a la más vieja."""

    def __init__(self, parent):
        super().__init__(parent, title=_("Grabaciones"), size=(720, 460),
                         name="DialogoGrabaciones")
        self._entradas = []
        self._lista = None
        self._build_ui()
        paleta.pintar_ventana(self)
        self.Centre()

    def _build_ui(self):
        panel = wx.Panel(self, name="PanelGrabaciones")
        vertical = wx.BoxSizer(wx.VERTICAL)

        self._lista = wx.ListBox(panel, style=wx.LB_SINGLE | wx.LB_HSCROLL,
                                 name=_("Grabaciones"))
        nombre_accesible(self._lista, _("Grabaciones"))
        self._lista.Bind(wx.EVT_KEY_DOWN, self._on_key)
        vertical.Add(self._lista, 1, wx.EXPAND | wx.ALL, 10)

        fila = wx.BoxSizer(wx.HORIZONTAL)
        self._btn_abrir = self._boton(panel, _ABRIR)
        self._btn_carpeta = self._boton(panel, _ABRIR_CARPETA)
        self._btn_copiar = self._boton(panel, _COPIAR_RUTA)
        self._btn_eliminar = self._boton(panel, _ELIMINAR)
        self._btn_cerrar = boton(panel, _(_CERRAR),
                                 nombre_de_etiqueta(_(_CERRAR)),
                                 wx.ID_CANCEL)
        for control in (self._btn_abrir, self._btn_carpeta, self._btn_copiar,
                        self._btn_eliminar, self._btn_cerrar):
            fila.Add(control, 0, wx.RIGHT, 6)
        vertical.Add(fila, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(vertical)
        self._btn_abrir.Bind(wx.EVT_BUTTON, lambda evento: self._abrir())
        self._btn_carpeta.Bind(
            wx.EVT_BUTTON, lambda evento: self._abrir_carpeta())
        self._btn_copiar.Bind(wx.EVT_BUTTON, lambda evento: self._copiar_ruta())
        self._btn_eliminar.Bind(
            wx.EVT_BUTTON, lambda evento: self._eliminar())
        self.Bind(wx.EVT_SHOW, self._al_mostrar)
        self._poblar()

    def _boton(self, panel, etiqueta):
        return boton(panel, _(etiqueta), nombre_de_etiqueta(_(etiqueta)))

    def _al_mostrar(self, evento):
        if evento.IsShown():
            self._lista.SetFocus()
        evento.Skip()

    def _poblar(self, indice=0):
        self._entradas = grabaciones.existentes()
        self._lista.Clear()
        if not self._entradas:
            self._lista.Append(_(_NO_HAY))
            indice = 0
        else:
            for entrada in self._entradas:
                self._lista.Append(grabaciones.texto_fila(entrada))
            indice = min(max(indice, 0), len(self._entradas) - 1)
        self._lista.SetSelection(indice)

    def _seleccionada(self):
        indice = self._lista.GetSelection()
        if indice == wx.NOT_FOUND or indice >= len(self._entradas):
            return None
        return self._entradas[indice]

    def _sin_grabaciones(self):
        anunciar(_(_NO_HAY))

    def _falta(self, texto):
        try:
            sound_player.reproducir("error")
        except Exception as error:
            logger.debug("sin sonido: %s", error)
        anunciar(texto)

    def _on_key(self, evento):
        tecla = evento.GetKeyCode()
        if tecla in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._abrir()
        elif tecla == wx.WXK_DELETE:
            self._eliminar()
        else:
            evento.Skip()

    def _abrir(self):
        entrada = self._seleccionada()
        if entrada is None:
            self._sin_grabaciones()
            return
        try:
            if not os.path.exists(entrada.get("ruta") or ""):
                raise OSError("falta")
            os.startfile(entrada["ruta"])
        except Exception as error:
            logger.debug("abrir grabación: %s", error)
            self._falta(_("El archivo ya no está disponible."))

    def _abrir_carpeta(self):
        entrada = self._seleccionada()
        if entrada is None:
            self._sin_grabaciones()
            return
        ruta = entrada.get("ruta") or ""
        try:
            if ruta and os.path.exists(ruta):
                subprocess.Popen(["explorer", "/select,", ruta])
                return
            carpeta = os.path.dirname(ruta)
            if carpeta and os.path.exists(carpeta):
                os.startfile(carpeta)
                return
        except Exception as error:
            logger.debug("abrir carpeta de la grabación: %s", error)
        self._falta(_("La carpeta ya no está disponible."))

    def _copiar_ruta(self):
        entrada = self._seleccionada()
        if entrada is None:
            self._sin_grabaciones()
            return
        copiar_al_portapapeles(entrada.get("ruta") or "")
        try:
            sound_player.reproducir("copiar")
        except Exception as error:
            logger.debug("sin sonido: %s", error)
        anunciar(_("Ruta copiada"))

    def _eliminar(self):
        entrada = self._seleccionada()
        if entrada is None:
            self._sin_grabaciones()
            return
        indice = self._lista.GetSelection()
        grabaciones.quitar(entrada.get("ruta") or "")
        anunciar(_("Eliminada de la lista"))
        self._poblar(indice)
        self._lista.SetFocus()


def abrir_grabaciones(parent) -> None:
    dialogo = GrabacionesDialog(parent)
    try:
        dialogo.ShowModal()
    finally:
        dialogo.Destroy()
