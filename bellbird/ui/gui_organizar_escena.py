"""Ventana accesible para organizar las fuentes de una escena de OBS."""

from __future__ import annotations

import wx

from bellbird.core.idioma import _
from bellbird.obs import consultas_transmision
from bellbird.obs import obs_disposicion
from bellbird.obs import obs_estado
from bellbird.obs.restablecimiento import RegistroRestablecimiento
from bellbird.ui.accesibilidad import ContadorAccesible, anunciar, nombre_accesible
from bellbird.ui.gui import caja_de_grupo
from bellbird.ui.mover_con_flechas import MoverConFlechas
from bellbird.ui.operaciones_obs import OperacionesObs
from bellbird.ui import paleta
from bellbird.ui.preferencias_comun import (
    boton, fijar_zona, fila_campo, fila_grilla, grilla_campos,
    lista_con_nombre, nombre_de_etiqueta)


class OrganizarEscenaDialog(wx.Dialog):

    def __init__(self, parent, gestor, escena):
        super().__init__(parent, title=_("Organizar escena"), size=(600, 560),
                         name="DialogoOrganizarEscena")
        self._gestor = gestor
        self._escena_inicial = escena or ""
        self._restablecimiento = RegistroRestablecimiento()
        self._valores_ventana = []
        self._descripcion_escena = ""
        self._operaciones = OperacionesObs(
            self, self._activar, self._escribir_fallo, self._enfocar_tras_fallo,
            self._tras_operacion)
        self._crear_controles()
        self._mover = MoverConFlechas(
            self, self.btn_ajuste, gestor, self._operaciones,
            self._restablecimiento, self._destino, self._mostrar_snap)
        self._en_hilo(self._cargar_inicial, self._inicial_cargada)

    def _crear_controles(self):
        caja = wx.BoxSizer(wx.VERTICAL)
        # Contenido desplazable solo vertical. Con Fit, el alto del diálogo
        # sigue al contenido y en una pantalla normal no aparece la barra.
        zona = wx.ScrolledWindow(self, name="ZonaOrganizarEscena",
                                 style=wx.TAB_TRAVERSAL | wx.VSCROLL)
        zona.SetScrollRate(0, 20)
        self._zona_desplazable = zona
        contenido = wx.BoxSizer(wx.VERTICAL)
        self._crear_grupo_escena(zona, contenido)
        self._crear_grupo_ventana(zona, contenido)
        self._crear_grupo_colocar(zona, contenido)
        fijar_zona(self, zona, contenido)
        caja.Add(zona, 1, wx.EXPAND)
        caja.Add(self._crear_botones(), 0, wx.EXPAND | wx.ALL, 12)
        self.SetSizer(caja)
        self._acciones = (
            self.cho_escena, self.btn_captura, self.cho_ventana,
            self.btn_usar_ventana, self.cho_fuente, self.cho_posicion,
            self.btn_colocar, self.sp_ancho, self.sp_alto, self.btn_tamano,
            self.chk_mostrar, self.chk_fijar, self.btn_frente, self.btn_ajuste,
            self.btn_restaurar)
        self._enlazar_eventos()
        self.SetMinSize((600, -1))
        self.Fit()
        self.Centre()
        paleta.pintar_ventana(self)

    def _crear_grupo_escena(self, zona, contenido):
        sizer, padre = caja_de_grupo(zona, _("Escena"))
        grilla = grilla_campos()
        rotulo_escena = wx.StaticText(padre, label=_("&Escena:"))
        self.cho_escena = lista_con_nombre(padre, _("&Escena:"))
        self.btn_captura = boton(
            padre, _("Guardar &imagen…"),
            nombre_de_etiqueta(_("Guardar &imagen…")))
        fila_grilla(grilla, rotulo_escena, self.cho_escena, self.btn_captura)
        rotulo_descripcion = wx.StaticText(
            padre, label=_("&Descripción de la escena:"))
        self.txt_descripcion = wx.TextCtrl(
            padre, style=wx.TE_MULTILINE | wx.TE_READONLY,
            name=nombre_de_etiqueta(_("&Descripción de la escena:")))
        nombre_accesible(self.txt_descripcion, self.txt_descripcion.GetName())
        self.txt_descripcion.SetMinSize((-1, 120))
        sizer.Add(grilla, 0, wx.EXPAND | wx.ALL, 6)
        fila_campo(sizer, rotulo_descripcion, self.txt_descripcion)
        contenido.Add(sizer, 0, wx.EXPAND | wx.ALL, 12)

    def _crear_grupo_ventana(self, zona, contenido):
        sizer, padre = caja_de_grupo(zona, _("Ventana capturada"))
        grilla = grilla_campos()
        rotulo_ventana = wx.StaticText(padre, label=_("&Ventana:"))
        self.cho_ventana = lista_con_nombre(padre, _("&Ventana:"))
        self.btn_usar_ventana = boton(
            padre, _("&Capturar ventana"),
            nombre_de_etiqueta(_("&Capturar ventana")))
        fila_grilla(grilla, rotulo_ventana, self.cho_ventana,
                    self.btn_usar_ventana)
        sizer.Add(grilla, 0, wx.EXPAND | wx.ALL, 6)
        contenido.Add(sizer, 0, wx.EXPAND | wx.ALL, 12)

    def _crear_grupo_colocar(self, zona, contenido):
        sizer, padre = caja_de_grupo(zona, _("Colocar fuente"))
        grilla = grilla_campos()
        rotulo_fuente = wx.StaticText(padre, label=_("&Fuente:"))
        self.cho_fuente = lista_con_nombre(padre, _("&Fuente:"))
        fila_grilla(grilla, rotulo_fuente, self.cho_fuente)
        rotulo_posicion = wx.StaticText(padre, label=_("&Posición:"))
        self.cho_posicion = lista_con_nombre(
            padre, _("&Posición:"),
            [_(obs_disposicion.etiqueta_anclaje(nombre))
             for nombre in obs_disposicion.ANCLAJES])
        self.btn_colocar = boton(
            padre, _("&Mover fuente"), nombre_de_etiqueta(_("&Mover fuente")))
        fila_grilla(grilla, rotulo_posicion, self.cho_posicion, self.btn_colocar)
        sizer.Add(grilla, 0, wx.EXPAND | wx.ALL, 6)
        self._crear_fila_tamano(padre, sizer)
        self._crear_fila_controles(padre, sizer)
        contenido.Add(sizer, 0, wx.EXPAND | wx.ALL, 12)

    def _crear_fila_tamano(self, padre, sizer):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        rotulo_ancho = wx.StaticText(padre, label=_("&Ancho:"))
        self.sp_ancho = ContadorAccesible(padre, min=100, max=4000, initial=460,
                                          name=_("Ancho en píxeles"))
        rotulo_alto = wx.StaticText(padre, label=_("A&lto:"))
        self.sp_alto = ContadorAccesible(padre, min=100, max=4000, initial=620,
                                         name=_("Alto en píxeles"))
        self.btn_tamano = boton(
            padre, _("Cambiar &tamaño"), nombre_de_etiqueta(_("Cambiar &tamaño")))
        controles = (rotulo_ancho, self.sp_ancho, rotulo_alto, self.sp_alto,
                     self.btn_tamano)
        for control in controles:
            fila.Add(control, 0, wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.BOTTOM | wx.RIGHT, 4)
        sizer.Add(fila, 0, wx.ALIGN_LEFT | wx.ALL, 6)

    def _crear_fila_controles(self, padre, sizer):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.chk_mostrar = wx.CheckBox(
            padre, label=_("Mostrar en la esce&na"),
            name=nombre_de_etiqueta(_("Mostrar en la esce&na")))
        self.chk_fijar = wx.CheckBox(
            padre, label=_("&Bloquear posición"),
            name=nombre_de_etiqueta(_("&Bloquear posición")))
        self.btn_frente = boton(
            padre, _("Traer al f&rente"), nombre_de_etiqueta(_("Traer al f&rente")))
        self._etiqueta_ajuste = _("Mover con flec&has")
        self.btn_ajuste = boton(
            padre, self._etiqueta_ajuste, nombre_de_etiqueta(self._etiqueta_ajuste))
        for control in (self.chk_mostrar, self.chk_fijar, self.btn_frente,
                        self.btn_ajuste):
            fila.Add(control, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        sizer.Add(fila, 0, wx.EXPAND | wx.ALL, 6)

    def _crear_botones(self):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_restaurar = boton(
            self, _("Deshacer cambi&os"), nombre_de_etiqueta(_("Deshacer cambi&os")))
        self.btn_ayuda = boton(self, _("A&yuda"), nombre_de_etiqueta(_("A&yuda")))
        self.btn_cerrar = boton(self, _("Cerrar"), _("Cerrar"), wx.ID_CANCEL)
        fila.Add(self.btn_restaurar, 0, wx.RIGHT, 8)
        fila.Add(self.btn_ayuda, 0, wx.RIGHT, 8)
        fila.AddStretchSpacer(1)
        fila.Add(self.btn_cerrar, 0)
        return fila

    def _enlazar_eventos(self):
        self.btn_captura.Bind(wx.EVT_BUTTON, self._captura)
        self.btn_usar_ventana.Bind(wx.EVT_BUTTON, self._usar_ventana)
        self.cho_escena.Bind(wx.EVT_CHOICE, self._cambiar_escena)
        self.cho_fuente.Bind(wx.EVT_CHOICE, self._cambiar_fuente)
        # Recorrer con flechas dispara EVT_CHOICE y esto no debe mover nada.
        self.btn_colocar.Bind(wx.EVT_BUTTON, self._colocar)
        self.btn_tamano.Bind(wx.EVT_BUTTON, self._tamano)
        self.chk_mostrar.Bind(wx.EVT_CHECKBOX, self._mostrar)
        self.chk_fijar.Bind(wx.EVT_CHECKBOX, self._fijar)
        self.btn_frente.Bind(wx.EVT_BUTTON, self._frente)
        self.btn_restaurar.Bind(wx.EVT_BUTTON, self._restaurar)
        self.btn_ayuda.Bind(wx.EVT_BUTTON, self._ayuda)
        self.btn_cerrar.Bind(wx.EVT_BUTTON, self._cerrar)
        self.Bind(wx.EVT_CLOSE, self._cerrar)

    def _activar(self, activo):
        for control in self._acciones:
            control.Enable(activo)

    def _tras_operacion(self, resultado):
        if isinstance(resultado, obs_disposicion.SnapshotPanel):
            self._mostrar_snap(resultado)

    def _escribir_fallo(self, mensaje):
        self.txt_descripcion.SetValue(mensaje)

    def _enfocar_tras_fallo(self):
        self.btn_cerrar.SetFocus()

    def _en_hilo(self, funcion, al_terminar=None):
        self._operaciones.en_hilo(funcion, al_terminar)

    def _cargar_inicial(self):
        escenas = self._gestor.escenas()
        return escenas, consultas_transmision.leer_escena(
            self._gestor, self._escena_inicial)

    def _inicial_cargada(self, datos):
        escenas, leida = datos
        self.cho_escena.Set(list(escenas))
        if self._escena_inicial in escenas:
            self.cho_escena.SetStringSelection(self._escena_inicial)
        elif escenas:
            self.cho_escena.SetSelection(0)
        self._cargar_fuentes(leida.fuentes, leida.fuente)
        self._cargar_ventanas(leida.opciones, leida.actual)
        self._mostrar_vista(leida.descripcion)
        self._mostrar_snap(leida.snap)
        self._anunciar_snap(leida.snap)
        self.cho_escena.SetFocus()

    def _mostrar_snap(self, snap):
        self.txt_descripcion.SetValue(consultas_transmision.descripcion_de_fuente(
            self._descripcion_escena, self._fuente(), snap))
        anclaje = obs_disposicion.anclaje_de(
            (snap.izquierda, snap.arriba, snap.ancho, snap.alto),
            snap.lienzo_ancho, snap.lienzo_alto)
        self.cho_posicion.SetSelection(
            tuple(obs_disposicion.ANCLAJES).index(anclaje)
            if anclaje else wx.NOT_FOUND)
        if snap.ancho:
            self.sp_ancho.SetValue(snap.ancho)
        if snap.alto:
            self.sp_alto.SetValue(snap.alto)
        self.chk_mostrar.SetValue(snap.visible)
        self.chk_fijar.SetValue(snap.bloqueada)

    def _mostrar_vista(self, descripcion):
        self._descripcion_escena = descripcion or ""
        self.txt_descripcion.SetValue(self._descripcion_escena)

    def _cargar_fuentes(self, fuentes, fuente=""):
        self.cho_fuente.Set(list(fuentes))
        if fuente:
            self.cho_fuente.SetStringSelection(fuente)
        if not fuentes:
            self.txt_descripcion.SetValue(_("La escena no tiene fuentes."))

    def _cargar_ventanas(self, opciones, actual):
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

    def _escena(self):
        return self.cho_escena.GetStringSelection()

    def _fuente(self):
        return self.cho_fuente.GetStringSelection()

    def _destino(self):
        return self._escena(), self._fuente()

    def _anunciar_snap(self, snap):
        anunciar(obs_disposicion.describir_fuente(
            self._fuente(), snap, obs_disposicion.ACTIVOS_DEFECTO))

    def _usar_ventana(self, event):
        escena = self._escena()
        valor = self._valor_ventana()
        if not valor:
            anunciar(_("Elige primero una ventana en Ventana."))
            return
        self._en_hilo(
            lambda: consultas_transmision.aplicar_ventana(self._gestor, escena, valor),
            self._ventana_aplicada)

    def _ventana_aplicada(self, datos):
        self._cargar_fuentes(datos.fuentes, datos.fuente)
        self._mostrar_snap(datos.snap)
        self._cargar_ventanas(datos.opciones, datos.actual)
        anunciar(datos.frase)

    def _cambiar_escena(self, event):
        if self._operaciones.en_vuelo:
            return
        escena = self._escena()
        self._en_hilo(
            lambda: consultas_transmision.leer_escena(self._gestor, escena),
            self._escena_cambiada)
        event.Skip()

    def _escena_cambiada(self, datos):
        self._cargar_fuentes(datos.fuentes, datos.fuente)
        self._cargar_ventanas(datos.opciones, datos.actual)
        self._mostrar_vista(datos.descripcion)
        if datos.fuentes:
            self._mostrar_snap(datos.snap)
            self._anunciar_snap(datos.snap)

    def _cambiar_fuente(self, event):
        if self._operaciones.en_vuelo:
            return
        escena, fuente = self._destino()
        # Escena y fuente llegan como argumentos: los hilos de trabajo no deben
        # leer controles de wx, eso solo es seguro desde el hilo principal.
        self._en_hilo(
            lambda: self._gestor.instantanea(escena, fuente=fuente),
            self._anunciar_snap)
        event.Skip()

    def _colocar(self, event):
        anclaje = tuple(obs_disposicion.ANCLAJES)[self.cho_posicion.GetSelection()]
        escena, fuente = self._escena(), self._fuente()
        self._en_hilo(lambda: consultas_transmision.cambiar_y_leer(
            self._gestor, self._restablecimiento, escena, fuente,
            self._gestor.colocar, anclaje), self._anunciar_snap)
        event.Skip()

    def _tamano(self, event):
        escena, fuente = self._escena(), self._fuente()
        ancho, alto = self.sp_ancho.GetValue(), self.sp_alto.GetValue()
        self._en_hilo(lambda: consultas_transmision.aplicar_tamano(
            self._gestor, self._restablecimiento, escena, fuente, ancho, alto),
            self._tamano_aplicado)

    def _tamano_aplicado(self, datos):
        snap, aplicado = datos
        self._mostrar_snap(snap)
        if aplicado:
            self._anunciar_snap(snap)
        else:
            anunciar(_("{fuente} todavía no informa su tamaño.").format(
                fuente=self._fuente()))

    def _mostrar(self, event):
        visible = self.chk_mostrar.GetValue()
        escena, fuente = self._escena(), self._fuente()
        self._en_hilo(lambda: consultas_transmision.cambiar_y_leer(
            self._gestor, self._restablecimiento, escena, fuente,
            self._gestor.mostrar, visible), self._anunciar_snap)
        event.Skip()

    def _fijar(self, event):
        fijada = self.chk_fijar.GetValue()
        escena, fuente = self._escena(), self._fuente()
        self._en_hilo(lambda: consultas_transmision.cambiar_y_leer(
            self._gestor, self._restablecimiento, escena, fuente,
            self._gestor.fijar, fijada), self._anunciar_snap)
        event.Skip()

    def _frente(self, event):
        escena, fuente = self._escena(), self._fuente()
        self._en_hilo(lambda: consultas_transmision.cambiar_y_leer(
            self._gestor, self._restablecimiento, escena, fuente,
            self._gestor.al_frente), self._anunciar_snap)

    def _captura(self, event):
        # Traductores: traduce solo «Imagen PNG»; no cambies «(*.png)|*.png».
        with wx.FileDialog(self, _("Guardar imagen de la escena"),
                           wildcard=_("Imagen PNG (*.png)|*.png"),
                           defaultFile="captura-escena.png",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialogo:
            if dialogo.ShowModal() != wx.ID_OK:
                return
            ruta = dialogo.GetPath()
        escena, fuente = self._escena(), self._fuente()
        self._en_hilo(lambda: consultas_transmision.capturar(
            self._gestor, escena, fuente, ruta),
            lambda resultado: anunciar(_("Imagen guardada")))

    def _ayuda(self, event):
        wx.MessageBox(_(obs_estado.TEXTO_AYUDA_ESCENA),
                      _("Ayuda de Organizar escena"),
                      wx.OK | wx.ICON_INFORMATION, self)

    def _restaurar(self, event):
        escena, fuente = self._escena(), self._fuente()
        self._en_hilo(lambda: consultas_transmision.restaurar(
            self._gestor, self._restablecimiento, escena, fuente),
            lambda snap: anunciar(_("Cambios deshechos")))

    def _cerrar(self, event):
        if self._operaciones.cerrando:
            return
        self._operaciones.cerrar()
        self.EndModal(wx.ID_CANCEL)
