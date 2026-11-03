"""Pestaña Agregar de la ventana Escena: capturar una ventana o una cámara."""

from __future__ import annotations

import wx

from bellbird.core.idioma import _
from bellbird.obs import consultas_transmision
from bellbird.ui import agregar_camara
from bellbird.ui.accesibilidad import anunciar
from bellbird.ui.gui import caja_de_grupo
from bellbird.ui.preferencias_comun import (
    boton, fila_grilla, grilla_campos, lista_con_nombre, nombre_de_etiqueta)


class PaginaAgregar(wx.Panel):

    def __init__(self, parent, ventana, gestor, operaciones, escena_elegida,
                 al_recargar):
        super().__init__(parent, name="PaginaAgregar")
        self._ventana = ventana
        self._gestor = gestor
        self._operaciones = operaciones
        self._escena_elegida = escena_elegida
        self._al_recargar = al_recargar
        self._valores_ventana = []
        self._crear_controles()
        self.acciones = (
            self.cho_ventana, self.btn_usar_ventana, self.btn_camara)
        self._enlazar_eventos()

    def _crear_controles(self):
        caja = wx.BoxSizer(wx.VERTICAL)
        sizer, padre = caja_de_grupo(self, _("Ventana capturada"))
        grilla = grilla_campos()
        rotulo_ventana = wx.StaticText(padre, label=_("&Ventana:"))
        self.cho_ventana = lista_con_nombre(padre, _("&Ventana:"))
        self.btn_usar_ventana = boton(
            padre, _("&Capturar ventana"),
            nombre_de_etiqueta(_("&Capturar ventana")))
        fila_grilla(grilla, rotulo_ventana, self.cho_ventana,
                    self.btn_usar_ventana)
        sizer.Add(grilla, 0, wx.EXPAND | wx.ALL, 6)
        caja.Add(sizer, 0, wx.EXPAND | wx.ALL, 8)
        self.btn_camara = boton(
            self, _("Agregar cá&mara…"),
            nombre_de_etiqueta(_("Agregar cá&mara…")))
        caja.Add(self.btn_camara, 0, wx.ALL, 8)
        self.SetSizer(caja)

    def _enlazar_eventos(self):
        self.btn_usar_ventana.Bind(wx.EVT_BUTTON, self._usar_ventana)
        self.btn_camara.Bind(wx.EVT_BUTTON, self._agregar_camara)

    def cargar_ventanas(self, opciones, actual):
        self._valores_ventana = [valor for _sin_uso, valor in opciones or ()]
        self.cho_ventana.Set([texto for texto, _sin_uso in opciones or ()])
        if actual in self._valores_ventana:
            self.cho_ventana.SetSelection(self._valores_ventana.index(actual))
        elif opciones:
            self.cho_ventana.SetSelection(wx.NOT_FOUND)

    def _valor_ventana(self):
        indice = self.cho_ventana.GetSelection()
        if indice == wx.NOT_FOUND or indice < 0 or indice >= len(self._valores_ventana):
            return ""
        return self._valores_ventana[indice]

    def _usar_ventana(self, event):
        valor = self._valor_ventana()
        if not valor:
            anunciar(_("Elige primero una ventana en Ventana."))
            return
        escena = self._escena_elegida()
        self._operaciones.en_hilo(
            lambda: consultas_transmision.aplicar_ventana(
                self._gestor, escena, valor),
            self._ventana_aplicada)

    def _ventana_aplicada(self, datos):
        anunciar(datos.frase)
        self._al_recargar()

    def _agregar_camara(self, event):
        agregar_camara.agregar(self._ventana, self._camara_agregada)

    def _camara_agregada(self, fuentes):
        self._al_recargar()
