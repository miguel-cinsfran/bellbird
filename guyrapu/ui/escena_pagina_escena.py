"""Pestaña Escena de la ventana Escena: la lista de escenas y sus fuentes."""

from __future__ import annotations

import wx

from guyrapu.core.idioma import _
from guyrapu.obs import consultas_transmision
from guyrapu.obs import escenas_obs
from guyrapu.obs import nombres_escena
from guyrapu.obs import obs_estado
from guyrapu.ui import escena_menu_escena
from guyrapu.ui.accesibilidad import anunciar, nombre_accesible
from guyrapu.ui.escena_pagina_fuentes import PaginaFuentes
from guyrapu.ui.preferencias_comun import (
    boton, fila_campo, nombre_de_etiqueta)


class PaginaEscena(wx.Panel):

    def __init__(self, parent, ventana, gestor, operaciones, registro,
                 escena_elegida, al_elegir):
        super().__init__(parent, name="PaginaEscena")
        self._gestor = gestor
        self._operaciones = operaciones
        self._al_elegir = al_elegir
        self._escenas = ()
        self._al_aire = ""
        self._crear_controles(ventana, registro, escena_elegida)
        self._acciones = {
            "cambiar": self._cambiar_al_aire,
            "renombrar": self._cambiar_nombre,
            "duplicar": self._duplicar,
            "eliminar": self._eliminar,
        }
        self.acciones = (self.lst_escenas, self.btn_cambiar, self.btn_agregar)
        self._enlazar_eventos()

    def _crear_controles(self, ventana, registro, escena_elegida):
        caja = wx.BoxSizer(wx.VERTICAL)
        self._crear_lista(caja)
        self._crear_botones(caja)
        self.pagina_fuentes = PaginaFuentes(
            self, ventana, self._gestor, self._operaciones, registro,
            escena_elegida)
        caja.Add(self.pagina_fuentes, 0, wx.EXPAND)
        self.SetSizer(caja)

    def _crear_lista(self, caja):
        rotulo = wx.StaticText(self, label=_("&Escenas:"))
        self.lst_escenas = wx.ListBox(
            self, name=nombre_de_etiqueta(_("&Escenas:")))
        nombre_accesible(self.lst_escenas, self.lst_escenas.GetName())
        self.lst_escenas.SetMinSize((-1, 120))
        fila_campo(caja, rotulo, self.lst_escenas)

    def _crear_botones(self, caja):
        self.btn_cambiar = boton(
            self, _("Cambiar e&scena"),
            nombre_de_etiqueta(_("Cambiar e&scena")))
        caja.Add(self.btn_cambiar, 0, wx.ALL, 8)
        self.btn_agregar = boton(
            self, _("A&gregar escena…"),
            nombre_de_etiqueta(_("A&gregar escena…")))
        caja.Add(self.btn_agregar, 0, wx.ALL, 8)

    def _enlazar_eventos(self):
        self.lst_escenas.Bind(wx.EVT_LISTBOX, self._elegir_escena)
        self.lst_escenas.Bind(wx.EVT_KEY_DOWN, self._tecla_escena)
        self.lst_escenas.Bind(wx.EVT_CONTEXT_MENU, self._menu_contextual)
        self.btn_cambiar.Bind(wx.EVT_BUTTON, self._cambiar_al_aire)
        self.btn_agregar.Bind(wx.EVT_BUTTON, self._agregar)

    def cargar(self, escenas, escena, al_aire, filas, fuente):
        self._escenas = tuple(escenas)
        self._al_aire = al_aire
        self._poner_textos()
        self._seleccionar(escena)
        self.pagina_fuentes.cargar(filas, fuente)

    def _poner_textos(self):
        self.lst_escenas.Set([
            nombres_escena.texto_de_fila(nombre, cantidad,
                                         nombre == self._al_aire)
            for nombre, cantidad in self._escenas])

    def _seleccionar(self, escena):
        indice = next(
            (i for i, (nombre, _cantidad) in enumerate(self._escenas)
             if nombre == escena), wx.NOT_FOUND)
        if indice == wx.NOT_FOUND and self._escenas:
            indice = 0
        self.lst_escenas.SetSelection(indice)

    def escena(self):
        indice = self.lst_escenas.GetSelection()
        if 0 <= indice < len(self._escenas):
            return self._escenas[indice][0]
        return ""

    def _nombres(self):
        return tuple(nombre for nombre, _cantidad in self._escenas)

    def _elegir_escena(self, event):
        if self._operaciones.en_vuelo:
            return
        self._al_elegir(self.escena())
        event.Skip()

    def _cambiar_al_aire(self, _event=None):
        escena = self.escena()
        if not escena or self._operaciones.en_vuelo:
            return
        if escena == self._al_aire:
            anunciar(_("{escena} ya es la escena actual.").format(
                escena=escena))
            return
        self._operaciones.en_hilo(
            lambda: self._gestor.poner_escena_al_aire(escena),
            lambda resultado: self._cambiada(resultado, escena))

    def _cambiada(self, resultado, escena):
        self._al_aire = resultado or escena
        self._poner_textos()
        self._seleccionar(escena)
        self.lst_escenas.SetFocus()
        anunciar(obs_estado.frase_escena_al_aire(self._al_aire))

    def _agregar(self, _event=None):
        if self._operaciones.en_vuelo:
            return
        nombre = self._pedir_nombre(
            _("Agregar escena"),
            nombres_escena.nombre_libre(self._nombres()))
        if not nombre:
            self.lst_escenas.SetFocus()
            return
        self._operaciones.en_hilo(
            lambda: self._crear_y_leer(nombre),
            lambda datos: self._agregada(nombre, datos))

    def _crear_y_leer(self, nombre):
        escenas_obs.crear(self._gestor._pedir, nombre)
        return self._leer_escenas(nombre)

    def _agregada(self, nombre, datos):
        self._mostrar_leidas(datos)
        anunciar(_("Escena {nombre} agregada.").format(nombre=nombre))

    def _mostrar_leidas(self, datos):
        escenas, escena, al_aire, leida = datos
        self.cargar(escenas, escena, al_aire, leida.filas, leida.fuente)
        self.lst_escenas.SetFocus()

    def _leer_escenas(self, escena):
        escenas = self._gestor.escenas()
        al_aire = self._gestor.escena_al_aire()
        inventario = escenas_obs.inventario(self._gestor, escenas)
        leida = consultas_transmision.leer_escena(self._gestor, escena)
        return inventario, escena, al_aire, leida

    def _menu_contextual(self, _event):
        self._mostrar_menu(self.lst_escenas)

    def _mostrar_menu(self, ancla):
        if self._operaciones.en_vuelo:
            return
        if not self.escena():
            anunciar(_("Sin selección"))
            return
        menu = escena_menu_escena.menu_de_escena(
            self._cambiar_al_aire, self._cambiar_nombre, self._duplicar,
            self._eliminar, self._guardar_imagen)
        ancla.PopupMenu(menu)
        menu.Destroy()

    def _tecla_escena(self, event):
        accion = escena_menu_escena.accion_de_tecla(event)
        if accion is None:
            event.Skip()
            return
        if accion == "menu":
            self._mostrar_menu(self.lst_escenas)
            return
        self._acciones[accion]()

    def _pedir_nombre(self, titulo, inicial, excepto=""):
        while True:
            nombre = self._dialogo_nombre(titulo, inicial)
            if nombre is None:
                return ""
            problema = nombres_escena.validar_nombre(
                nombre, self._nombres(), excepto)
            if problema == nombres_escena.NOMBRE_REPETIDO:
                anunciar(_("Ya hay una escena con ese nombre."))
                inicial = nombre
                continue
            if problema == nombres_escena.NOMBRE_VACIO:
                return ""
            return nombre.strip()

    def _dialogo_nombre(self, titulo, inicial):
        dialogo = wx.TextEntryDialog(
            self, _("Nombre de la escena:"), titulo, value=inicial)
        try:
            if dialogo.ShowModal() != wx.ID_OK:
                return None
            return dialogo.GetValue()
        finally:
            dialogo.Destroy()

    def _cambiar_nombre(self, _event=None):
        antes = self.escena()
        if not antes or self._operaciones.en_vuelo:
            return
        nombre = self._pedir_nombre(_("Cambiar nombre"), antes, excepto=antes)
        if not nombre or nombre == antes:
            self.lst_escenas.SetFocus()
            return
        self._operaciones.en_hilo(
            lambda: self._renombrar_y_leer(antes, nombre),
            lambda datos: self._renombrada(antes, nombre, datos))

    def _renombrar_y_leer(self, antes, nombre):
        escenas_obs.renombrar(self._gestor._pedir, antes, nombre)
        return self._leer_escenas(nombre)

    def _renombrada(self, antes, nombre, datos):
        self._mostrar_leidas(datos)
        anunciar(_("Escena {antes} cambiada a {nombre}.").format(
            antes=antes, nombre=nombre))

    def _duplicar(self, _event=None):
        origen = self.escena()
        if not origen or self._operaciones.en_vuelo:
            return
        nombre = nombres_escena.nombre_de_copia(origen, self._nombres())
        self._operaciones.en_hilo(
            lambda: self._duplicar_y_leer(origen, nombre),
            lambda datos: self._agregada(nombre, datos))

    def _duplicar_y_leer(self, origen, nombre):
        escenas_obs.duplicar(self._gestor._pedir, origen, nombre)
        return self._leer_escenas(nombre)

    def _eliminar(self, _event=None):
        escena = self.escena()
        if not escena or self._operaciones.en_vuelo:
            return
        if len(self._escenas) <= 1:
            anunciar(_("No se puede eliminar la única escena."))
            return
        if not self._confirmar_eliminar(escena):
            self.lst_escenas.SetFocus()
            return
        siguiente = self._siguiente(escena)
        self._operaciones.en_hilo(
            lambda: self._eliminar_y_leer(escena, siguiente),
            lambda datos: self._eliminada(escena, datos))

    def _siguiente(self, escena):
        nombres = self._nombres()
        indice = nombres.index(escena)
        if indice + 1 < len(nombres):
            return nombres[indice + 1]
        return nombres[indice - 1] if indice else ""

    def _confirmar_eliminar(self, escena):
        dialogo = wx.MessageDialog(
            self, _("¿Eliminar la escena {escena}?").format(escena=escena),
            _("Eliminar escena"), wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        try:
            dialogo.SetYesNoLabels(_("&Sí"), _("&No"))
            return dialogo.ShowModal() == wx.ID_YES
        finally:
            dialogo.Destroy()

    def _eliminar_y_leer(self, escena, siguiente):
        escenas_obs.eliminar(self._gestor._pedir, escena)
        return self._leer_escenas(siguiente)

    def _eliminada(self, escena, datos):
        self._mostrar_leidas(datos)
        anunciar(_("Escena {escena} eliminada.").format(escena=escena))

    def _guardar_imagen(self, _event=None):
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
            lambda _resultado: anunciar(_("Imagen guardada")))
