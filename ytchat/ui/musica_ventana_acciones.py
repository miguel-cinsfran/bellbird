"""Acciones de las listas de la ventana de música y sus diálogos.

La mezcla no guarda estado propio: usa la fuente y los controles que arma
`VentanaMusica`. Cada operación la hace `ControlMusica`, que es quien
anuncia; acá solo se pide, se elige y se refresca lo que se ve.
"""

from __future__ import annotations

import wx

from ytchat.core import diagnostico
from ytchat.music import anuncios, listas, vista
from ytchat.ui import musica_dialogo_enlace, musica_menus

logger = diagnostico.obtener_logger(__name__)

TITULO = "Música"
TITULO_NUEVA = "Nueva lista"
TITULO_RENOMBRAR = "Renombrar lista"
TEXTO_NOMBRE = "Nombre de la lista:"


def _validar_nombre(nombre):
    """El nombre limpio, o None si no sirve y el control dirá por qué."""
    try:
        return listas.validar_nombre(nombre)
    except listas.ErrorListas:
        return None


def _pedir_nombre(parent, titulo, valor=""):
    with wx.TextEntryDialog(parent, TEXTO_NOMBRE, titulo, valor) as dialogo:
        if dialogo.ShowModal() != wx.ID_OK:
            return None
        return dialogo.GetValue()


def _confirmar_borrar(parent, nombre):
    pregunta = anuncios.TEXTO_CONFIRMAR_BORRAR_LISTA.format(nombre=nombre)
    dialogo = wx.MessageDialog(
        parent, pregunta, TITULO, wx.YES_NO | wx.ICON_QUESTION)
    try:
        boton = dialogo.FindWindow(wx.ID_NO)
        if boton is not None:
            dialogo.SetDefaultItem(boton)
    except Exception as exc:
        logger.debug("No se pudo dejar No por defecto: %s", exc)
    try:
        return dialogo.ShowModal() == wx.ID_YES
    finally:
        dialogo.Destroy()


class AccionesVentanaMusica:
    """Acciones de la Biblioteca, la Cola y las listas propias."""

    def _accion_biblioteca(self, accion):
        tema, indice = self._con_tema()
        if tema is None:
            return
        if isinstance(accion, tuple):
            self._control.agregar_a_lista(accion[1], [tema])
            return
        funcion = self._acciones_biblioteca(tema, indice).get(accion)
        if funcion is not None:
            funcion()

    def _acciones_biblioteca(self, tema, indice):
        control = self._control
        return {
            musica_menus.ACCION_AHORA:
                lambda: control.reproducir_ahora([tema]),
            musica_menus.ACCION_CONTINUACION:
                lambda: control.poner_a_continuacion([tema]),
            musica_menus.ACCION_AGREGAR:
                lambda: control.agregar_al_final([tema]),
            musica_menus.ACCION_TODO_DESDE_AQUI:
                lambda: control.reproducir_desde_aqui(
                    self._temas_filtrados, indice),
            musica_menus.ACCION_NUEVA_LISTA_CON_TEMA:
                lambda: self._nueva_lista(tema),
            musica_menus.ACCION_QUITAR_DE_LISTA:
                lambda: self._quitar_lista(tema),
            musica_menus.ACCION_RENOMBRAR_LISTA: self._renombrar_lista,
            musica_menus.ACCION_BORRAR_LISTA: self._borrar_lista,
        }

    def _leer_nombres(self):
        try:
            return list(listas.nombres(self._control.carpeta_listas()))
        except Exception as exc:
            logger.debug("No se pudieron leer las listas de música: %s", exc)
            return []

    def _quitar_lista(self, tema):
        if self._fuente is None:
            return
        origen = self._indice_en_fuente(tema)
        if origen is not None:
            self._control.quitar_de_lista(self._fuente, origen)
            self._cargar_lista()

    def _indice_en_fuente(self, tema):
        for indice, candidato in enumerate(self._temas_fuente):
            if candidato is tema:
                return indice
        for indice, candidato in enumerate(self._temas_fuente):
            if candidato == tema:
                return indice
        return None

    def _accion_cola(self, accion):
        indice = self._indice_cola()
        if indice is None:
            return
        control = self._control
        acciones = {
            musica_menus.ACCION_REPRODUCIR:
                lambda: control.reproducir_desde(indice),
            musica_menus.ACCION_QUITAR:
                lambda: control.quitar_de_cola(indice),
            musica_menus.ACCION_SUBIR: lambda: self._mover_cola(indice, -1),
            musica_menus.ACCION_BAJAR: lambda: self._mover_cola(indice, 1),
            musica_menus.ACCION_IR_AL_QUE_SUENA: self._ir_al_que_suena,
            musica_menus.ACCION_MEZCLAR: control.mezclar_cola,
            musica_menus.ACCION_VACIAR: control.vaciar_cola,
            musica_menus.ACCION_GUARDAR_COLA: self._guardar_cola,
        }
        funcion = acciones.get(accion)
        if funcion is not None:
            funcion()

    def _mover_cola(self, indice, paso):
        self._control.mover_en_cola(indice, paso)
        estado = self._control.estado()
        total = len(estado.cola) if estado is not None else 0
        destino = max(0, min(total - 1, indice + paso)) if total else -1
        self.refrescar_cola(seleccion=destino)

    def _ir_al_que_suena(self):
        estado = self._control.estado()
        if estado is None or estado.terminado or estado.posicion is None:
            return
        self.lb_cola.SetSelection(estado.posicion)
        self.lb_cola.SetFocus()

    def refrescar_cola(self, seleccion=None):
        if not self:
            return
        anterior = (self.lb_cola.GetSelection()
                    if seleccion is None else seleccion)
        estado = self._control.estado()
        filas = (vista.filas_cola(estado)
                 if estado is not None else [])
        self.lb_cola.Set(filas)
        indice = vista.indice_seleccion_tras_refrescar(anterior, len(filas))
        if indice >= 0:
            self.lb_cola.SetSelection(indice)

    def _indice_cola(self):
        indice = self.lb_cola.GetSelection()
        return None if indice == wx.NOT_FOUND else indice

    def actualizar_nombres(self, mapa):
        if not self or not mapa:
            return
        self._temas_fuente = tuple(
            mapa.get(tema.origen, tema) for tema in self._temas_fuente)
        self._temas_filtrados = tuple(
            mapa.get(tema.origen, tema) for tema in self._temas_filtrados)
        filas = vista.filas_temas(self._temas_filtrados)
        for indice, tema in enumerate(self._temas_filtrados):
            if tema.origen in mapa:
                try:
                    self.lb_temas.SetString(indice, filas[indice])
                except Exception:
                    logger.debug("No se pudo actualizar la fila de un tema")
        estado = self._control.estado()
        if estado is None:
            return
        filas_cola = vista.filas_cola(estado)
        if self.lb_cola.GetCount() != len(filas_cola):
            self.refrescar_cola()
            return
        for indice, tema in enumerate(estado.cola):
            if tema.origen in mapa:
                try:
                    self.lb_cola.SetString(indice, filas_cola[indice])
                except Exception:
                    logger.debug("No se pudo actualizar la fila de la cola")

    def _menu_temas(self):
        if self._con_tema()[0] is not None:
            musica_menus.mostrar_menu(
                self.lb_temas,
                musica_menus.entradas_biblioteca(
                    self._fuente is not None, self._leer_nombres()),
                self._accion_biblioteca)

    def _menu_cola(self):
        if self._indice_cola() is not None:
            musica_menus.mostrar_menu(
                self.lb_cola, musica_menus.entradas_cola(), self._accion_cola)

    def _guardar_cola(self):
        if not (self._control.cola_actual() or ()):
            self._control.guardar_cola_como_lista("")
            return
        nombre = _pedir_nombre(self, TITULO_NUEVA)
        if nombre is None:
            return
        limpio = _validar_nombre(nombre)
        if limpio is None:
            self._control.guardar_cola_como_lista(nombre)
            return
        self._control.guardar_cola_como_lista(limpio)
        self._reload_colecciones(preferir=self._fuente)

    def _abrir_enlace(self):
        datos = musica_dialogo_enlace.pedir_enlace(self)
        if datos is not None:
            self._control.abrir_enlace(*datos)

    def _cambiar_carpeta(self):
        with wx.DirDialog(
                self, "Elige la carpeta de música",
                defaultPath=self._control._carpeta()) as dialogo:
            if dialogo.ShowModal() != wx.ID_OK:
                return
            ruta = dialogo.GetPath()
        self._control.cambiar_carpeta(ruta)
        self._reload_colecciones()
        self._cargar_fuente()

    def _cerrar(self):
        self._cancelar_temporizador()
        self.EndModal(wx.ID_CANCEL)
