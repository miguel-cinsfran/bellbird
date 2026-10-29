"""Lista de directos recientes en la pantalla sin conexión.

Ocupa el hueco que deja la zona de contenido cuando no hay conexión: los
diez últimos directos y vídeos vistos, de YouTube y TikTok juntos, del más
nuevo al más viejo. Intro sobre uno lo vuelve a abrir, por el mismo camino
que el Historial.
"""

from __future__ import annotations

import wx

from bellbird.core import historial
from bellbird.core import paths
from bellbird.core.idioma import _
from bellbird.ui.accesibilidad import nombre_accesible
from bellbird.ui.busqueda_teclado import instalar_busqueda_tipo
from bellbird.ui.tema import _T, _pintar, _tc, _titulo

MAX_RECIENTES = 10


def entradas_recientes(ruta):
    """Las diez entradas más nuevas del historial, de ambas plataformas."""
    lista = historial.cargar(ruta)
    ordenadas = sorted(lista, key=lambda e: e.get("fecha") or "", reverse=True)
    return ordenadas[:MAX_RECIENTES]


def texto_reciente(entrada):
    """Fila con la plataforma delante y la etiqueta del historial detrás."""
    plataforma = "TikTok" if entrada.get("plataforma") == "tiktok" else "YouTube"
    # Traductores: fila de recientes; {plataforma} es YouTube o TikTok y
    # {etiqueta} el canal, el título y la fecha.
    return _("{plataforma}: {etiqueta}").format(
        plataforma=plataforma, etiqueta=historial.etiqueta(entrada))


def abrir_historial(parent, ruta, al_conectar):
    """Abre el Historial con la misma ruta y función que la lista."""
    from bellbird.ui.gui_historial import abrir_historial as _abrir
    _abrir(parent, ruta, al_conectar)


def armar(panel, sizer, zona, al_conectar, ruta=None):
    """Crea la lista en el sizer, antes de la zona. Nombre corto para que la
    llamada entre en una línea en quien la arma."""
    return RecientesInicio(panel, sizer, zona, al_conectar, ruta=ruta)


class RecientesInicio:
    """Rótulo y lista de recientes; se muestra sin conexión y con historial."""

    def __init__(self, panel, sizer, zona, al_conectar, ruta=None):
        self._panel = panel
        self._sizer = sizer
        self._zona = zona
        self._ruta = paths.historial_lives() if ruta is None else ruta
        self._al_conectar = al_conectar
        self.entradas = []
        self.caja = wx.Panel(panel, name="RecientesInicio")
        _pintar(self.caja, bg=_T.bg)
        vs = wx.BoxSizer(wx.VERTICAL)
        self.rotulo = wx.StaticText(
            self.caja, label=_("&Directos recientes:"), name="EtiquetaRecientes")
        _titulo(self.rotulo)
        vs.Add(self.rotulo, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        self.lista = wx.ListBox(
            self.caja, style=wx.LB_SINGLE | wx.LB_HSCROLL,
            name=_("Directos recientes"))
        _tc(self.lista)
        nombre_accesible(self.lista, _("Directos recientes"))
        instalar_busqueda_tipo(
            self.lista,
            lambda: [self.lista.GetString(i) for i in range(self.lista.GetCount())])
        self.lista.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._conectar())
        self.lista.Bind(wx.EVT_KEY_DOWN, self.al_tecla)
        vs.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)
        self.caja.SetSizer(vs)
        self._sizer.Insert(
            self._indice_zona(), self.caja, 1,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self._zona.Bind(wx.EVT_SHOW, self._al_cambio_zona)
        self._aplicar_visibilidad()

    def _indice_zona(self):
        """Posición de la zona en el sizer: la caja va justo antes."""
        total = self._sizer.GetItemCount()
        for i in range(total):
            if self._sizer.GetItem(i).GetWindow() is self._zona:
                return i
        return total

    def _aplicar_visibilidad(self):
        """Zona visible: caja oculta; zona oculta: recarga y muestra si hay."""
        if self._zona.IsShown():
            self.caja.Hide()
        else:
            self._recargar()
        self._panel.Layout()

    def _al_cambio_zona(self, event):
        event.Skip()
        if not self._zona or not self.caja or not self._panel:
            return
        self._aplicar_visibilidad()

    def _recargar(self):
        """Lee el historial y llena la lista, con la primera fila elegida."""
        self.entradas = entradas_recientes(self._ruta)
        self.lista.Clear()
        for entrada in self.entradas:
            self.lista.Append(texto_reciente(entrada))
        if self.entradas:
            self.lista.SetSelection(0)
            self.caja.Show()
        else:
            self.caja.Hide()

    def al_tecla(self, event):
        """Intro reconecta; el resto sigue su curso."""
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._conectar()
        else:
            event.Skip()

    def _conectar(self):
        elegida = self.lista.GetSelection()
        if elegida == wx.NOT_FOUND or elegida >= len(self.entradas):
            return
        url = self.entradas[elegida].get("url") or ""
        if url:
            self._al_conectar(url)

    def abrir_historial(self):
        """Abre el Historial con la misma ruta y función que la lista."""
        abrir_historial(self.caja.GetTopLevelParent(), self._ruta, self._al_conectar)
