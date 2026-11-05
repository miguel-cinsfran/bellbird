"""Fuentes de la pestaña Escena: la lista y las acciones sobre una fuente."""

from __future__ import annotations

import wx

from bellbird.core.idioma import _
from bellbird.obs import (
    aplicar_diseno, consultas_transmision, disenos_fabrica, disenos_guardados,
    obs_disposicion, tamano_relativo)
from bellbird.ui import (
    agregar_camara, escena_captura_ventana, escena_disenos, escena_menu_fuente,
    escena_tamano)
from bellbird.ui.accesibilidad import anunciar, nombre_accesible
from bellbird.ui.mover_con_flechas import MoverConFlechas
from bellbird.ui.preferencias_comun import (
    boton, fila_campo, nombre_de_etiqueta)


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
        self._mover = MoverConFlechas(
            ventana, self.btn_ajuste, gestor, operaciones, registro,
            self._destino, self._mostrar_snap)
        self.acciones = (
            self.btn_ajuste, self.btn_diseno, self.btn_agregar,
            self.btn_restaurar)
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
        self.btn_ajuste = boton(
            self, _("Mover con flec&has"),
            nombre_de_etiqueta(_("Mover con flec&has")))
        caja.Add(self.btn_ajuste, 0, wx.ALL, 8)
        self.btn_diseno = boton(
            self, _("&Aplicar diseño…"),
            nombre_de_etiqueta(_("&Aplicar diseño…")))
        caja.Add(self.btn_diseno, 0, wx.ALL, 8)
        self.btn_agregar = boton(
            self, _("Agregar f&uente…"),
            nombre_de_etiqueta(_("Agregar f&uente…")))
        caja.Add(self.btn_agregar, 0, wx.ALL, 8)
        self.btn_restaurar = boton(
            self, _("Deshacer cambi&os"),
            nombre_de_etiqueta(_("Deshacer cambi&os")))
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
            fila, self._mostrar, self._fijar, self._posicion_tamano,
            self._ordenar)
        ancla.PopupMenu(menu)
        menu.Destroy()

    def _ordenar(self, movimiento):
        if movimiento == "cima":
            self._frente()
        else:
            self._movimiento(movimiento)

    def _cambiar(self, escena, fuente, funcion, *argumentos):
        snap = consultas_transmision.cambiar_y_leer(
            self._gestor, self._registro, escena, fuente, funcion,
            *argumentos)
        return snap, consultas_transmision.leer_filas(self._gestor, escena)

    def _con_snap(self, datos, fuente):
        snap, filas = datos
        self.cargar(filas, fuente)
        self._anunciar_snap(snap)

    def _mostrar(self, visible):
        escena, fuente = self._destino()
        if not fuente or self._operaciones.en_vuelo:
            return
        self._operaciones.en_hilo(
            lambda: self._cambiar(escena, fuente, self._gestor.mostrar,
                                  visible),
            lambda datos: self._con_snap(datos, fuente))

    def _fijar(self, fijada):
        escena, fuente = self._destino()
        if not fuente or self._operaciones.en_vuelo:
            return
        self._operaciones.en_hilo(
            lambda: self._cambiar(escena, fuente, self._gestor.fijar,
                                  fijada),
            lambda datos: self._con_snap(datos, fuente))

    def _frente(self):
        escena, fuente = self._destino()
        if not fuente or self._operaciones.en_vuelo:
            return
        self._operaciones.en_hilo(
            lambda: self._cambiar(escena, fuente, self._gestor.al_frente),
            lambda datos: self._con_snap(datos, fuente))

    def _movimiento(self, movimiento):
        escena, fuente = self._destino()
        if not fuente or self._operaciones.en_vuelo:
            return
        datos = {}

        def mover(escena, movimiento, fuente):
            datos["movio"], datos["frase"] = self._gestor.mover_capa(
                escena, movimiento, fuente=fuente)

        self._operaciones.en_hilo(
            lambda: self._cambiar(escena, fuente, mover, movimiento),
            lambda datos_accion: self._movimiento_aplicado(
                datos_accion, datos, fuente))

    def _movimiento_aplicado(self, datos_accion, datos, fuente):
        snap, filas = datos_accion
        self.cargar(filas, fuente)
        texto = datos["frase"]
        if datos["movio"]:
            texto = f"{texto} {self._descripcion_corta(snap)}"
        anunciar(texto)

    def _posicion_tamano(self):
        escena, fuente = self._destino()
        if not fuente:
            anunciar(_("Sin selección"))
            return
        if self._operaciones.en_vuelo:
            return
        self._operaciones.en_hilo(
            lambda: self._gestor.instantanea(escena, fuente=fuente),
            lambda snap: self._abrir_posicion_tamano(escena, fuente, snap))

    def _abrir_posicion_tamano(self, escena, fuente, snap):
        elegido = self._pedir_tamano(snap, fuente)
        if elegido is None:
            return
        ancho, alto, anclaje = elegido
        self._operaciones.en_hilo(
            lambda: self._aplicar_posicion_tamano(
                escena, fuente, ancho, alto, anclaje),
            lambda datos: self._tamano_aplicado(datos, fuente))

    def _pedir_tamano(self, snap, fuente):
        porcentajes = tamano_relativo.porcentajes(
            snap.ancho, snap.alto, snap.lienzo_ancho, snap.lienzo_alto)
        if not all(porcentajes):
            anunciar(_("{fuente} todavía no informa su tamaño.").format(
                fuente=fuente))
            return None
        elegido = escena_tamano.pedir_tamano(self, *porcentajes)
        self.lst_fuentes.SetFocus()
        if elegido is None:
            return None
        pancho, palto, anclaje = elegido
        ancho, alto = tamano_relativo.a_pixeles(
            pancho, palto, snap.lienzo_ancho, snap.lienzo_alto,
            snap.ancho, snap.alto)
        return ancho, alto, anclaje

    def _aplicar_posicion_tamano(self, escena, fuente, ancho, alto, anclaje):
        datos = consultas_transmision.aplicar_posicion_y_tamano(
            self._gestor, self._registro, escena, fuente, ancho, alto,
            anclaje)
        return datos, consultas_transmision.leer_filas(self._gestor, escena)

    def _tamano_aplicado(self, datos, fuente):
        (snap, aplicado), filas = datos
        self.cargar(filas, fuente)
        if aplicado:
            self._anunciar_snap(snap)
        else:
            anunciar(_("{fuente} todavía no informa su tamaño.").format(
                fuente=fuente))

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
        menu = wx.Menu()
        captura = wx.NewIdRef()
        menu.Append(captura, _("Captura de &ventana…"))
        menu.Bind(wx.EVT_MENU, lambda _evento: self._capturar_ventana(),
                  id=captura)
        camara = wx.NewIdRef()
        menu.Append(camara, _("&Cámara…"))
        menu.Bind(wx.EVT_MENU, lambda _evento: self._agregar_camara(),
                  id=camara)
        self.btn_agregar.PopupMenu(menu)
        menu.Destroy()

    def _capturar_ventana(self):
        escena = self._escena()
        if not escena:
            anunciar(_("Sin selección"))
            return
        if self._operaciones.en_vuelo:
            return
        escena_captura_ventana.pedir_ventana(
            self._ventana, self._gestor, self._operaciones, escena,
            lambda datos: self._ventana_aplicada(escena, datos),
            self.lst_fuentes.SetFocus)

    def _ventana_aplicada(self, escena, datos):
        anunciar(datos.frase)
        self._releer_filas(escena, datos.fuente)

    def _agregar_camara(self):
        agregar_camara.agregar(self._ventana, self._camara_agregada)

    def _camara_agregada(self, _fuentes):
        escena = self._escena()
        if escena:
            self._releer_filas(escena, "")

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
