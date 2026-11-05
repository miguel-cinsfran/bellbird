"""Pestaña Escena de la ventana Escena: elegir, fuentes y guardar."""

from __future__ import annotations

import wx

from bellbird.core.idioma import _
from bellbird.obs import consultas_transmision
from bellbird.obs import obs_estado
from bellbird.ui.accesibilidad import anunciar
from bellbird.ui.escena_pagina_fuentes import PaginaFuentes
from bellbird.ui.preferencias_comun import (
    boton, fila_grilla, grilla_campos, lista_con_nombre, nombre_de_etiqueta)


class PaginaEscena(wx.Panel):

    def __init__(self, parent, ventana, gestor, operaciones, registro,
                 escena_elegida, al_elegir):
        super().__init__(parent, name="PaginaEscena")
        self._gestor = gestor
        self._operaciones = operaciones
        self._al_elegir = al_elegir
        self._crear_controles(ventana, registro, escena_elegida)
        self.acciones = (self.cho_escena, self.btn_cambiar, self.btn_imagen)
        self._enlazar_eventos()

    def _crear_controles(self, ventana, registro, escena_elegida):
        caja = wx.BoxSizer(wx.VERTICAL)
        grilla = grilla_campos()
        rotulo_escena = wx.StaticText(self, label=_("&Escena:"))
        self.cho_escena = lista_con_nombre(self, _("&Escena:"))
        self.btn_cambiar = boton(
            self, _("Cambiar e&scena"),
            nombre_de_etiqueta(_("Cambiar e&scena")))
        fila_grilla(grilla, rotulo_escena, self.cho_escena, self.btn_cambiar)
        caja.Add(grilla, 0, wx.EXPAND | wx.ALL, 8)
        self.pagina_fuentes = PaginaFuentes(
            self, ventana, self._gestor, self._operaciones, registro,
            escena_elegida)
        caja.Add(self.pagina_fuentes, 0, wx.EXPAND)
        self.btn_imagen = boton(
            self, _("Guardar &imagen…"),
            nombre_de_etiqueta(_("Guardar &imagen…")))
        caja.Add(self.btn_imagen, 0, wx.ALL, 8)
        self.SetSizer(caja)

    def _enlazar_eventos(self):
        self.cho_escena.Bind(wx.EVT_CHOICE, self._elegir_escena)
        self.btn_cambiar.Bind(wx.EVT_BUTTON, self._cambiar_al_aire)
        self.btn_imagen.Bind(wx.EVT_BUTTON, self._guardar_imagen)

    def cargar(self, escenas, escena, filas, fuente):
        self.cho_escena.Set(list(escenas))
        if escena in escenas:
            self.cho_escena.SetStringSelection(escena)
        elif escenas:
            self.cho_escena.SetSelection(0)
        self.pagina_fuentes.cargar(filas, fuente)

    def escena(self):
        return self.cho_escena.GetStringSelection()

    def _elegir_escena(self, event):
        if self._operaciones.en_vuelo:
            return
        self._al_elegir(self.escena())
        event.Skip()

    def _cambiar_al_aire(self, event):
        escena = self.escena()
        self._operaciones.en_hilo(
            lambda: self._gestor.poner_escena_al_aire(escena),
            lambda resultado: anunciar(
                obs_estado.frase_escena_al_aire(resultado)))

    def _guardar_imagen(self, event):
        # Traductores: traduce solo «Imagen PNG»; no cambies «(*.png)|*.png».
        with wx.FileDialog(self, _("Guardar imagen de la escena"),
                           wildcard=_("Imagen PNG (*.png)|*.png"),
                           defaultFile="captura-escena.png",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialogo:
            if dialogo.ShowModal() != wx.ID_OK:
                return
            ruta = dialogo.GetPath()
        escena = self.escena()
        self._operaciones.en_hilo(
            lambda: consultas_transmision.capturar(
                self._gestor, escena, "", ruta),
            lambda resultado: anunciar(_("Imagen guardada")))
