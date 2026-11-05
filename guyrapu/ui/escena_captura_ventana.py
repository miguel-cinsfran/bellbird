"""Cuadro para elegir la ventana que captura la escena del Panel de OBS."""

from __future__ import annotations

import wx

from guyrapu.core.idioma import _
from guyrapu.obs import consultas_transmision
from guyrapu.ui import paleta
from guyrapu.ui.accesibilidad import anunciar
from guyrapu.ui.preferencias_comun import (
    boton, fila_campo, lista_con_nombre, nombre_de_etiqueta)


class DialogoCapturarVentana(wx.Dialog):
    """Pide una ventana; el foco empieza en la lista."""

    def __init__(self, padre, opciones, actual):
        super().__init__(padre, title=_("Capturar ventana"),
                         name="DialogoCapturarVentana")
        self._valores = [valor for _texto, valor in opciones or ()]
        self._crear_controles(opciones, actual)
        paleta.pintar_ventana(self)
        self.Centre()
        self.cho_ventana.SetFocus()

    def _crear_controles(self, opciones, actual):
        vertical = wx.BoxSizer(wx.VERTICAL)
        self.rotulo_ventana = wx.StaticText(self, label=_("&Ventana:"))
        self.cho_ventana = lista_con_nombre(
            self, _("&Ventana:"), [texto for texto, _valor in opciones or ()])
        self.cho_ventana.SetSelection(self._seleccion(actual))
        fila_campo(vertical, self.rotulo_ventana, self.cho_ventana)
        self._crear_botones(vertical)
        self.SetSizerAndFit(vertical)
        self._enlazar_eventos()

    def _seleccion(self, actual):
        if actual in self._valores:
            return self._valores.index(actual)
        return wx.NOT_FOUND

    def _crear_botones(self, vertical):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_aceptar = boton(
            self, _("&Aceptar"), nombre_de_etiqueta(_("&Aceptar")),
            wx.ID_OK)
        self.btn_aceptar.SetDefault()
        self.btn_cancelar = boton(
            self, _("&Cancelar"), nombre_de_etiqueta(_("&Cancelar")),
            wx.ID_CANCEL)
        fila.Add(self.btn_aceptar, 0, wx.RIGHT, 8)
        fila.Add(self.btn_cancelar, 0)
        vertical.Add(fila, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

    def _enlazar_eventos(self):
        self.btn_aceptar.Bind(wx.EVT_BUTTON, self._al_aceptar)
        self.btn_cancelar.Bind(wx.EVT_BUTTON, self._al_cancelar)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)

    def valor(self):
        indice = self.cho_ventana.GetSelection()
        if indice == wx.NOT_FOUND or indice < 0 or indice >= len(self._valores):
            return ""
        return self._valores[indice]

    def _al_aceptar(self, _event):
        if not self.valor():
            anunciar(_("Elige primero una ventana en Ventana."))
            return
        self.EndModal(wx.ID_OK)

    def _al_cancelar(self, _event):
        self.EndModal(wx.ID_CANCEL)

    def _al_tecla(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        event.Skip()


def pedir_ventana(padre, gestor, operaciones, escena, al_aplicar, al_cerrar):
    """Pide las ventanas a OBS en el hilo y abre el cuadro."""
    if operaciones.en_vuelo:
        return
    operaciones.en_hilo(
        lambda: gestor.ventanas(escena),
        lambda datos: _abrir(padre, gestor, operaciones, escena, datos,
                             al_aplicar, al_cerrar))


def _abrir(padre, gestor, operaciones, escena, datos, al_aplicar, al_cerrar):
    opciones, actual = datos
    dialogo = DialogoCapturarVentana(padre, opciones, actual)
    try:
        aceptado = dialogo.ShowModal() == wx.ID_OK
        valor = dialogo.valor()
    finally:
        dialogo.Destroy()
    al_cerrar()
    if not aceptado or not valor:
        return
    if operaciones.en_vuelo:
        return
    operaciones.en_hilo(
        lambda: consultas_transmision.aplicar_ventana(gestor, escena, valor),
        al_aplicar)
