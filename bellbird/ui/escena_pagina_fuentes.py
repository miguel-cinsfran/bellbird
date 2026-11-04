"""Pestaña Fuentes de la ventana Escena: colocar y ajustar una fuente."""

from __future__ import annotations

import wx

from bellbird.core.idioma import _, pgettext
from bellbird.obs import (
    aplicar_diseno, consultas_transmision, disenos_fabrica, disenos_guardados,
    obs_disposicion)
from bellbird.ui import escena_disenos, escena_tamano
from bellbird.ui.accesibilidad import anunciar, nombre_accesible
from bellbird.ui.gui import caja_de_grupo
from bellbird.ui.mover_con_flechas import MoverConFlechas
from bellbird.ui.preferencias_comun import (
    boton, fila_campo, fila_grilla, grilla_campos, lista_con_nombre,
    nombre_de_etiqueta)


class PaginaFuentes(wx.Panel):

    def __init__(self, parent, ventana, gestor, operaciones, registro,
                 escena_elegida):
        super().__init__(parent, name="PaginaFuentes")
        self._gestor = gestor
        self._operaciones = operaciones
        self._registro = registro
        self._escena_elegida = escena_elegida
        self._crear_controles()
        self._mover = MoverConFlechas(
            ventana, self.btn_ajuste, gestor, operaciones, registro,
            self._destino, self._mostrar_snap)
        self.acciones = (
            self.cho_fuente, self.cho_posicion, self.btn_colocar,
            self.chk_mostrar, self.chk_fijar, self.btn_capa,
            self.btn_tamano, self.btn_ajuste, self.btn_diseno,
            self.btn_restaurar, self.txt_detalle)
        self._enlazar_eventos()

    @property
    def en_ajuste(self):
        return self._mover.en_curso

    def _crear_controles(self):
        self._ancho, self._alto = 460, 620
        caja = wx.BoxSizer(wx.VERTICAL)
        sizer, padre = caja_de_grupo(self, _("Colocar fuente"))
        self._crear_grupo_colocar(padre, sizer)
        caja.Add(sizer, 0, wx.EXPAND | wx.ALL, 8)
        self.btn_diseno = boton(
            self, _("&Aplicar diseño…"),
            nombre_de_etiqueta(_("&Aplicar diseño…")))
        caja.Add(self.btn_diseno, 0, wx.ALL, 8)
        self.btn_restaurar = boton(
            self, _("Deshacer cambi&os"),
            nombre_de_etiqueta(_("Deshacer cambi&os")))
        caja.Add(self.btn_restaurar, 0, wx.ALL, 8)
        self.SetSizer(caja)

    def _crear_grupo_colocar(self, padre, sizer):
        grilla = grilla_campos()
        rotulo_fuente = wx.StaticText(padre, label=_("&Fuente:"))
        self.cho_fuente = lista_con_nombre(padre, _("&Fuente:"))
        fila_grilla(grilla, rotulo_fuente, self.cho_fuente)
        sizer.Add(grilla, 0, wx.EXPAND | wx.ALL, 6)
        self._crear_detalle(padre, sizer)
        self._crear_fila_posicion(padre, sizer)
        self._crear_fila_controles(padre, sizer)

    def _crear_fila_posicion(self, padre, sizer):
        grilla = grilla_campos()
        rotulo_posicion = wx.StaticText(padre, label=_("&Posición:"))
        self.cho_posicion = lista_con_nombre(
            padre, _("&Posición:"),
            [_(obs_disposicion.etiqueta_anclaje(nombre))
             for nombre in obs_disposicion.ANCLAJES])
        self.btn_colocar = boton(
            padre, _("&Mover fuente"), nombre_de_etiqueta(_("&Mover fuente")))
        fila_grilla(grilla, rotulo_posicion, self.cho_posicion,
                    self.btn_colocar)
        sizer.Add(grilla, 0, wx.EXPAND | wx.ALL, 6)

    def _crear_detalle(self, padre, sizer):
        rotulo_detalle = wx.StaticText(
            padre, label=_("&Detalle de la fuente:"))
        self.txt_detalle = wx.TextCtrl(
            padre, style=wx.TE_MULTILINE | wx.TE_READONLY,
            name=nombre_de_etiqueta(_("&Detalle de la fuente:")))
        nombre_accesible(self.txt_detalle, self.txt_detalle.GetName())
        self.txt_detalle.SetMinSize((-1, 90))
        fila_campo(sizer, rotulo_detalle, self.txt_detalle)

    def _crear_fila_controles(self, padre, sizer):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        self._crear_casillas(padre)
        self.btn_capa = boton(
            padre, _("Ord&enar"), nombre_de_etiqueta(_("Ord&enar")))
        self.btn_tamano = boton(
            padre, _("&Tamaño…"), nombre_de_etiqueta(_("&Tamaño…")))
        self.btn_ajuste = boton(
            padre, _("Mover con flec&has"),
            nombre_de_etiqueta(_("Mover con flec&has")))
        for control in (self.chk_mostrar, self.chk_fijar, self.btn_capa,
                        self.btn_tamano, self.btn_ajuste):
            fila.Add(control, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        sizer.Add(fila, 0, wx.EXPAND | wx.ALL, 6)

    def _crear_casillas(self, padre):
        self.chk_mostrar = wx.CheckBox(
            padre, label=_("Mostrar en la esce&na"),
            name=nombre_de_etiqueta(_("Mostrar en la esce&na")))
        self.chk_fijar = wx.CheckBox(
            padre, label=_("&Bloquear posición"),
            name=nombre_de_etiqueta(_("&Bloquear posición")))

    def _enlazar_eventos(self):
        self.cho_fuente.Bind(wx.EVT_CHOICE, self._cambiar_fuente)
        self.cho_fuente.Bind(wx.EVT_KEY_DOWN, self._tecla_fuente)
        self.cho_fuente.Bind(wx.EVT_CONTEXT_MENU,
                             self._menu_contextual_fuente)
        # Recorrer con flechas dispara EVT_CHOICE y esto no debe mover nada.
        self.btn_colocar.Bind(wx.EVT_BUTTON, self._colocar)
        self.btn_tamano.Bind(wx.EVT_BUTTON, self._tamano)
        self.btn_capa.Bind(wx.EVT_BUTTON, self._capa)
        self.chk_mostrar.Bind(wx.EVT_CHECKBOX, self._mostrar)
        self.chk_fijar.Bind(wx.EVT_CHECKBOX, self._fijar)
        self.btn_diseno.Bind(wx.EVT_BUTTON, self._aplicar_diseno)
        self.btn_restaurar.Bind(wx.EVT_BUTTON, self._restaurar)

    def _capa(self, _event):
        self._mostrar_menu_capa(self.btn_capa)

    def _tecla_fuente(self, event):
        tecla = event.GetKeyCode()
        if (tecla == wx.WXK_WINDOWS_MENU
                or (tecla == wx.WXK_F10 and event.ShiftDown())):
            self._mostrar_menu_capa(self.cho_fuente)
            return
        event.Skip()

    def _menu_contextual_fuente(self, _event):
        self._mostrar_menu_capa(self.cho_fuente)

    def _mostrar_menu_capa(self, ancla):
        if not self._fuente():
            anunciar(_("Sin selección"))
            return
        menu = self._menu_de_capa()
        ancla.PopupMenu(menu)
        menu.Destroy()

    def _menu_de_capa(self):
        menu = wx.Menu()
        for etiqueta, accion in (
                (_("Mover a la &cima"), lambda: self._frente(None)),
                (pgettext("orden de fuentes", "&Subir"),
                 lambda: self._movimiento("adelante")),
                (pgettext("orden de fuentes", "&Bajar"),
                 lambda: self._movimiento("atras")),
                (_("Mover al &fondo"),
                 lambda: self._movimiento("fondo"))):
            identificador = wx.NewIdRef()
            menu.Append(identificador, etiqueta)
            menu.Bind(wx.EVT_MENU,
                      lambda _evento, funcion=accion: funcion(),
                      id=identificador)
        return menu

    def cargar(self, fuentes, fuente, snap):
        self.cho_fuente.Set(list(fuentes))
        if fuente:
            self.cho_fuente.SetStringSelection(fuente)
        if not fuentes:
            self.txt_detalle.SetValue(_("La escena no tiene fuentes."))
        else:
            self._mostrar_snap(snap)

    def mostrar_snap(self, snap):
        self._mostrar_snap(snap)

    def anunciar_snap(self, snap):
        self._anunciar_snap(snap)

    def _escena(self):
        return self._escena_elegida()

    def _fuente(self):
        return self.cho_fuente.GetStringSelection()

    def _destino(self):
        return self._escena(), self._fuente()

    def _mostrar_snap(self, snap):
        self.txt_detalle.SetValue(consultas_transmision.descripcion_de_fuente(
            "", self._fuente(), snap))
        anclaje = obs_disposicion.anclaje_de(
            (snap.izquierda, snap.arriba, snap.ancho, snap.alto),
            snap.lienzo_ancho, snap.lienzo_alto)
        self.cho_posicion.SetSelection(
            tuple(obs_disposicion.ANCLAJES).index(anclaje)
            if anclaje else wx.NOT_FOUND)
        if snap.ancho:
            self._ancho = snap.ancho
        if snap.alto:
            self._alto = snap.alto
        self.chk_mostrar.SetValue(snap.visible)
        self.chk_fijar.SetValue(snap.bloqueada)

    def _anunciar_snap(self, snap):
        anunciar(self._descripcion_corta(snap))

    def _descripcion_corta(self, snap):
        return obs_disposicion.describir_fuente(
            self._fuente(), snap, obs_disposicion.ACTIVOS_DEFECTO)

    def _cambiar_fuente(self, event):
        if self._operaciones.en_vuelo:
            return
        escena, fuente = self._destino()
        # Escena y fuente llegan como argumentos: los hilos de trabajo no deben
        # leer controles de wx, eso solo es seguro desde el hilo principal.
        self._operaciones.en_hilo(
            lambda: self._gestor.instantanea(escena, fuente=fuente),
            self._anunciar_snap)
        event.Skip()

    def _colocar(self, event):
        anclaje = tuple(obs_disposicion.ANCLAJES)[self.cho_posicion.GetSelection()]
        escena, fuente = self._destino()
        self._operaciones.en_hilo(
            lambda: consultas_transmision.cambiar_y_leer(
                self._gestor, self._registro, escena, fuente,
                self._gestor.colocar, anclaje),
            self._anunciar_snap)
        event.Skip()

    def _tamano(self, event):
        escena, fuente = self._destino()
        if not fuente:
            anunciar(_("Sin selección"))
            return
        tamano = escena_tamano.pedir_tamano(self, self._ancho, self._alto)
        self.btn_tamano.SetFocus()
        if tamano is None:
            return
        ancho, alto = tamano
        self._operaciones.en_hilo(
            lambda: consultas_transmision.aplicar_tamano(
                self._gestor, self._registro, escena, fuente, ancho, alto),
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
        escena, fuente = self._destino()
        self._operaciones.en_hilo(
            lambda: consultas_transmision.cambiar_y_leer(
                self._gestor, self._registro, escena, fuente,
                self._gestor.mostrar, visible),
            self._anunciar_snap)
        event.Skip()

    def _fijar(self, event):
        fijada = self.chk_fijar.GetValue()
        escena, fuente = self._destino()
        self._operaciones.en_hilo(
            lambda: consultas_transmision.cambiar_y_leer(
                self._gestor, self._registro, escena, fuente,
                self._gestor.fijar, fijada),
            self._anunciar_snap)
        event.Skip()

    def _frente(self, event):
        escena, fuente = self._destino()
        self._operaciones.en_hilo(
            lambda: consultas_transmision.cambiar_y_leer(
                self._gestor, self._registro, escena, fuente,
                self._gestor.al_frente),
            self._anunciar_snap)

    def _movimiento(self, movimiento):
        escena, fuente = self._destino()
        datos = {}

        def mover(escena, movimiento, fuente):
            datos["movio"], datos["frase"] = self._gestor.mover_capa(
                escena, movimiento, fuente=fuente)
            datos["fuentes"] = self._gestor.fuentes(escena)

        self._operaciones.en_hilo(
            lambda: consultas_transmision.cambiar_y_leer(
                self._gestor, self._registro, escena, fuente, mover,
                movimiento),
            lambda snap: self._movimiento_aplicado(snap, datos, fuente))

    def _movimiento_aplicado(self, snap, datos, fuente):
        self.cho_fuente.Set(list(datos["fuentes"]))
        self.cho_fuente.SetStringSelection(fuente)
        texto = datos["frase"]
        if datos["movio"]:
            texto = f"{texto} {self._descripcion_corta(snap)}"
        anunciar(texto)

    def _aplicar_diseno(self, event):
        escena = self._escena()
        if not escena:
            anunciar(_("Sin selección"))
            return
        if self._operaciones.en_vuelo:
            return
        self._operaciones.en_hilo(
            lambda: aplicar_diseno.fuentes_de_escena(self._gestor, escena),
            lambda fuentes: self._abrir_disenos(escena, fuentes))

    def _abrir_disenos(self, escena, fuentes):
        if not any(fuente.tipo != "chat" for fuente in fuentes):
            anunciar(_("La escena no tiene fuentes para un diseño."))
            return
        guardados = disenos_guardados.cargar()
        elegido = escena_disenos.pedir_diseno(self, fuentes, guardados)
        self.btn_diseno.SetFocus()
        if elegido is None:
            return
        nombre, diseno = elegido
        self._operaciones.en_hilo(
            lambda: aplicar_diseno.aplicar_diseno(
                self._gestor, self._registro, escena, diseno),
            lambda resultado: anunciar(disenos_fabrica.resumen(
                nombre, resultado[0], sin_mover=resultado[1])))

    def _restaurar(self, event):
        escena, fuente = self._destino()
        self._operaciones.en_hilo(
            lambda: consultas_transmision.restaurar(
                self._gestor, self._registro, escena, fuente),
            lambda snap: anunciar(_("Cambios deshechos")))
