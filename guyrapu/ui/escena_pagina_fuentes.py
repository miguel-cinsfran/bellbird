"""Fuentes de la pestaña Escena: la lista y las acciones sobre una fuente."""

from __future__ import annotations

import wx

from guyrapu.core.idioma import _
from guyrapu.obs import (
    aplicar_diseno, consultas_transmision, disenos_fabrica, disenos_guardados,
    obs_disposicion)
from guyrapu.ui import (
    escena_acciones_fuente, escena_agregar_fuente, escena_disenos,
    escena_menu_fuente)
from guyrapu.ui.accesibilidad import anunciar, nombre_accesible
from guyrapu.ui.preferencias_comun import boton, fila_campo, nombre_de_etiqueta


class PaginaFuentes(wx.Panel):

    def __init__(self, parent, ventana, gestor, operaciones, registro,
                 escena_elegida):
        super().__init__(parent, name="PaginaFuentes")
        self._ventana = ventana
        self._gestor = gestor
        self._operaciones = operaciones
        self._registro = registro
        self._escena_elegida = escena_elegida
        self._filas = ()
        self._crear_controles()
        self.acciones_fuente = escena_acciones_fuente.AccionesFuente(self)
        self._mover = self.acciones_fuente.mover
        self.acciones = (self.btn_diseno, self.btn_agregar, self.btn_restaurar)
        self._enlazar_eventos()

    @property
    def en_ajuste(self):
        return self._mover.en_curso

    def _crear_controles(self):
        caja = wx.BoxSizer(wx.VERTICAL)
        self._crear_lista(caja)
        self._crear_botones(caja)
        self.SetSizer(caja)

    def _crear_lista(self, caja):
        rotulo_fuentes = wx.StaticText(self, label=_("&Fuentes:"))
        self.lst_fuentes = wx.ListBox(
            self, name=nombre_de_etiqueta(_("&Fuentes:")))
        nombre_accesible(self.lst_fuentes, self.lst_fuentes.GetName())
        self.lst_fuentes.SetMinSize((-1, 120))
        fila_campo(caja, rotulo_fuentes, self.lst_fuentes)

    def _crear_botones(self, caja):
        self.btn_diseno = boton(
            self, _("&Aplicar diseño…"),
            nombre_de_etiqueta(_("&Aplicar diseño…")))
        caja.Add(self.btn_diseno, 0, wx.ALL, 8)
        self.btn_agregar = boton(
            self, _("Agregar f&uente…"),
            nombre_de_etiqueta(_("Agregar f&uente…")))
        caja.Add(self.btn_agregar, 0, wx.ALL, 8)
        self.btn_restaurar = boton(
            self, _("Deshacer todos los cambi&os"),
            nombre_de_etiqueta(_("Deshacer todos los cambi&os")))
        caja.Add(self.btn_restaurar, 0, wx.ALL, 8)

    def _enlazar_eventos(self):
        self.lst_fuentes.Bind(wx.EVT_KEY_DOWN, self._tecla_fuente)
        self.lst_fuentes.Bind(wx.EVT_CONTEXT_MENU, self._menu_contextual)
        self.btn_diseno.Bind(wx.EVT_BUTTON, self._aplicar_diseno)
        self.btn_agregar.Bind(wx.EVT_BUTTON, self._agregar_fuente)
        self.btn_restaurar.Bind(wx.EVT_BUTTON, self._restaurar)

    def cargar(self, filas, fuente):
        self._filas = tuple(filas or ())
        self.lst_fuentes.Set([fila.texto for fila in self._filas])
        indice = next((i for i, fila in enumerate(self._filas)
                       if fila.nombre == fuente), wx.NOT_FOUND)
        self.lst_fuentes.SetSelection(indice)

    def fuente(self):
        indice = self.lst_fuentes.GetSelection()
        if 0 <= indice < len(self._filas):
            return self._filas[indice].nombre
        return ""

    def _fila(self):
        indice = self.lst_fuentes.GetSelection()
        if 0 <= indice < len(self._filas):
            return self._filas[indice]
        return None

    def _escena(self):
        return self._escena_elegida()

    def _destino(self):
        return self._escena(), self.fuente()

    def _tecla_fuente(self, event):
        if self.acciones_fuente.tecla(event):
            return
        tecla = event.GetKeyCode()
        if (tecla == wx.WXK_WINDOWS_MENU
                or (tecla == wx.WXK_F10 and event.ShiftDown())):
            self._mostrar_menu_fuente(self.lst_fuentes)
            return
        event.Skip()

    def _menu_contextual(self, _event):
        self._mostrar_menu_fuente(self.lst_fuentes)

    def _mostrar_menu_fuente(self, ancla):
        fila = self._fila()
        if fila is None:
            anunciar(_("Sin selección"))
            return
        menu = escena_menu_fuente.menu_de_fuente(
            fila, self.acciones_fuente)
        ancla.PopupMenu(menu)
        menu.Destroy()

    def _posicion_tamano(self):
        self.acciones_fuente.posicion_tamano()

    def _ordenar(self, movimiento):
        self.acciones_fuente.ordenar(
            "frente" if movimiento == "cima" else movimiento)

    def _mostrar_snap(self, snap, filas=None):
        if filas is not None:
            self.cargar(filas, self.fuente())

    def _anunciar_snap(self, snap):
        anunciar(self._descripcion_corta(snap))

    def _descripcion_corta(self, snap):
        return obs_disposicion.describir_fuente(
            self.fuente(), snap, obs_disposicion.ACTIVOS_DEFECTO)

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
            lambda: self._aplicar_diseno_elegido(escena, diseno),
            lambda datos: self._diseno_aplicado(nombre, datos))

    def _aplicar_diseno_elegido(self, escena, diseno):
        resultado = aplicar_diseno.aplicar_diseno(
            self._gestor, self._registro, escena, diseno)
        return resultado, consultas_transmision.leer_filas(
            self._gestor, escena)

    def _diseno_aplicado(self, nombre, datos):
        resultado, filas = datos
        self.cargar(filas, self.fuente())
        anunciar(disenos_fabrica.resumen(
            nombre, resultado[0], sin_mover=resultado[1]))

    def _agregar_fuente(self, _event):
        escena_agregar_fuente.mostrar_menu(self, self.btn_agregar)

    def _releer_filas(self, escena, fuente):
        self._operaciones.en_hilo(
            lambda: consultas_transmision.leer_filas(self._gestor, escena),
            lambda filas: self._cargar_filas(filas, fuente))

    def _cargar_filas(self, filas, fuente):
        nombres = [fila.nombre for fila in filas]
        if fuente in nombres:
            self.cargar(filas, fuente)
        else:
            self.cargar(filas, nombres[0] if nombres else "")

    def _restaurar(self, event):
        escena, fuente = self._destino()
        if self._operaciones.en_vuelo:
            return
        self._operaciones.en_hilo(
            lambda: self._restaurar_y_leer(escena, fuente),
            lambda datos: self._restaurado(datos, fuente))

    def _restaurar_y_leer(self, escena, fuente):
        snap = consultas_transmision.restaurar(
            self._gestor, self._registro, escena, fuente)
        return snap, consultas_transmision.leer_filas(self._gestor, escena)

    def _restaurado(self, datos, fuente):
        _snap, filas = datos
        self.cargar(filas, fuente)
        anunciar(_("Cambios deshechos"))
