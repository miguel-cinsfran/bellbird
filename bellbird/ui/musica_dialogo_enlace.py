"""Cuadro para abrir un enlace de YouTube en la música.

Pide la dirección y con qué modo aplicarla. La validación y los anuncios
los hace `ControlMusica.abrir_enlace`; acá solo se recoge la respuesta.
"""

from __future__ import annotations

import wx

from bellbird.core.idioma import N_, _
from bellbird.ui.accesibilidad import nombre_accesible
from bellbird.ui.tema import _T, _pintar

TITULO = N_("Abrir enlace")
MODO_AHORA = "ahora"
MODO_CONTINUACION = "continuacion"
MODO_FINAL = "final"
MODOS = (MODO_AHORA, MODO_CONTINUACION, MODO_FINAL)


def resultado(url, modo):
    """La dirección limpia y el modo, o None si no hay dirección."""
    direccion = (url or "").strip()
    if not direccion:
        return None
    return direccion, modo if modo in MODOS else MODO_AHORA


class DialogoEnlace(wx.Dialog):
    """Dirección de YouTube y los tres modos de agregarla."""

    def __init__(self, parent):
        super().__init__(parent, title=_(TITULO), name="DialogoEnlace")
        self._modo = MODO_AHORA
        self._crear_controles()
        self.Bind(wx.EVT_CHAR_HOOK, self._tecla)
        self.Centre()

    def _crear_controles(self):
        panel = wx.Panel(self, name="PanelEnlace")
        self._panel = panel
        panel.SetBackgroundColour(_T.bg)
        panel.SetForegroundColour(_T.text)
        vs = wx.BoxSizer(wx.VERTICAL)

        vs.Add(wx.StaticText(panel, label=_("&Dirección de YouTube:")),
                0, wx.ALL, 8)
        self.txt_enlace = wx.TextCtrl(panel, name=_("Dirección de YouTube"))
        _pintar(self.txt_enlace, _T.field, _T.text)
        nombre_accesible(self.txt_enlace, _("Dirección de YouTube"))
        vs.Add(self.txt_enlace, 0, wx.EXPAND | wx.ALL, 8)

        botones = wx.WrapSizer(wx.HORIZONTAL, flags=0)
        self.btn_ahora = self._boton(
            panel, _("Reproducir &ahora"), _("Reproducir ahora"))
        self.btn_continuacion = self._boton(
            panel, _("A co&ntinuación"), _("A continuación"))
        self.btn_cola = self._boton(
            panel, _("Agregar a la &cola"), _("Agregar a la cola"))
        self.btn_cancelar = wx.Button(
            panel, wx.ID_CANCEL, _("Cancelar"), name=_("Cancelar"))
        _pintar(self.btn_cancelar, _T.btn, _T.btn_t)
        for boton in (self.btn_ahora, self.btn_continuacion,
                      self.btn_cola, self.btn_cancelar):
            botones.Add(boton, 0, wx.RIGHT, 6)
        vs.Add(botones, 0, wx.ALL, 8)

        panel.SetSizer(vs)

        self.btn_ahora.SetDefault()
        self.btn_ahora.Bind(wx.EVT_BUTTON, lambda e: self._elegir(MODO_AHORA))
        self.btn_continuacion.Bind(
            wx.EVT_BUTTON, lambda e: self._elegir(MODO_CONTINUACION))
        self.btn_cola.Bind(wx.EVT_BUTTON, lambda e: self._elegir(MODO_FINAL))
        self.btn_cancelar.Bind(
            wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
        self.txt_enlace.SetFocus()

    @staticmethod
    def _boton(panel, etiqueta, nombre):
        boton = wx.Button(panel, wx.ID_ANY, etiqueta, name=nombre)
        _pintar(boton, _T.btn, _T.btn_t)
        return boton

    def _elegir(self, modo):
        self._modo = modo
        self.EndModal(wx.ID_OK)

    def datos(self):
        """La dirección y el modo elegidos, o None si está vacía."""
        return resultado(self.txt_enlace.GetValue(), self._modo)

    def _tecla(self, evento):
        if evento.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        evento.Skip()


def pedir_enlace(parent):
    """Abre el cuadro y devuelve (dirección, modo), o None si se cancela."""
    with DialogoEnlace(parent) as dialogo:
        if dialogo.ShowModal() != wx.ID_OK:
            return None
        return dialogo.datos()
