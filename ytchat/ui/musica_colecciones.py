"""Lista de colecciones de la ventana de música.

La mezcla guarda la fuente elegida (la carpeta o una lista propia) y carga
sus temas en la lista que arma `VentanaMusica`. «Biblioteca» es la carpeta;
debajo va una fila por lista propia. Intro reproduce la colección entera y
Suprimir borra la lista, previa confirmación.
"""

from __future__ import annotations

import wx

from ytchat.core import diagnostico
from ytchat.music import vista
from ytchat.ui import musica_editor_lista, musica_menus
from ytchat.ui import musica_ventana_acciones as _acciones
from ytchat.ui.gui import anunciar

logger = diagnostico.obtener_logger(__name__)

TEXTO_CARGANDO = "Cargando la carpeta…"
TEXTO_SIN_CARPETA = "No hay carpeta de música"


class ColeccionesVentanaMusica:
    """La lista «Colecciones» y la fuente que muestra la lista de temas."""

    def _inicio(self):
        estado = self._control.estado()
        posicion = None
        if estado is not None and not estado.terminado:
            posicion = estado.posicion
        self.refrescar_cola(seleccion=posicion)
        if self._abrir_listas and self._nombres_listas:
            self.lb_colecciones.SetSelection(1)
            self._fuente = self._nombres_listas[0]
            self._cargar_lista()
        else:
            self.lb_colecciones.SetSelection(0)
            self._fuente = None
            self._cargar_carpeta()
        self.enfocar_primer_control()

    def enfocar_primer_control(self):
        if self._abrir_listas and self._nombres_listas:
            self.lb_colecciones.SetFocus()
        else:
            self.txt_buscar.SetFocus()

    def _reload_colecciones(self, preferir=None):
        nombres = self._leer_nombres()
        self._nombres_listas = nombres
        self.lb_colecciones.Set(vista.filas_colecciones(nombres))
        indice = 0
        if preferir:
            buscado = str(preferir).casefold()
            for posicion, nombre in enumerate(nombres, start=1):
                if nombre.casefold() == buscado:
                    indice = posicion
                    break
        self.lb_colecciones.SetSelection(indice)
        self._fuente = self._coleccion_elegida()

    def _coleccion_elegida(self):
        indice = self.lb_colecciones.GetSelection()
        if indice <= 0 or indice > len(self._nombres_listas):
            return None
        return self._nombres_listas[indice - 1]

    def _cambiar_coleccion(self, evento):
        self._cargar_fuente()
        evento.Skip()

    def _cargar_fuente(self):
        self._generacion += 1
        self.txt_buscar.ChangeValue("")
        self._cancelar_temporizador()
        self._fuente = self._coleccion_elegida()
        if self._fuente is None:
            self._cargar_carpeta()
        else:
            self._biblioteca = None
            self._cargar_lista()

    def _cargar_carpeta(self):
        self._biblioteca = None
        self._primera_carga = True
        self.txt_buscar.ChangeValue("")
        self._cambiar_estado(TEXTO_CARGANDO)
        generacion = self._generacion
        self._control.biblioteca(
            lambda biblioteca: self._al_biblioteca(biblioteca, generacion))

    def _cargar_lista(self, seleccion=None):
        nombre = self._fuente
        generacion = self._generacion
        if seleccion is None:
            seleccion = self.lb_temas.GetSelection()
        self._cambiar_estado(TEXTO_CARGANDO)
        temas = tuple(self._control.temas_de_lista(nombre) or ())
        if generacion != self._generacion or self._fuente != nombre:
            return
        self._temas_fuente = temas
        self._cargando = False
        self._aplicar_filtro()
        self._estado_listo()
        indice = vista.indice_seleccion_tras_refrescar(
            seleccion, len(self._temas_filtrados))
        if indice >= 0:
            self.lb_temas.SetSelection(indice)

    def _al_biblioteca(self, biblioteca, generacion):
        if not self or generacion != self._generacion \
                or self._fuente is not None:
            return
        if biblioteca is None:
            self._temas_fuente = ()
            self._temas_filtrados = ()
            self._cambiar_estado(TEXTO_SIN_CARPETA)
            self.btn_carpeta.Enable(True)
            return
        self._biblioteca = biblioteca
        self._temas_fuente = tuple(biblioteca.temas())
        self._cargando = False
        self._aplicar_filtro()
        self._estado_listo()
        if self._primera_carga:
            self._primera_carga = False
            anunciar(vista.texto_resumen(
                len(self._temas_fuente), len(self._temas_filtrados), False))

    def _tecla_colecciones(self, evento):
        codigo = evento.GetKeyCode()
        modificadores = evento.GetModifiers()
        if codigo in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._reproducir_coleccion()
            return
        if codigo in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            if self._coleccion_elegida() is not None:
                self._borrar_lista()
            return
        if codigo == wx.WXK_WINDOWS_MENU or (
                codigo == wx.WXK_F10 and modificadores & wx.MOD_SHIFT):
            self._menu_colecciones()
            return
        evento.Skip()

    def _reproducir_coleccion(self):
        nombre = self._coleccion_elegida()
        if nombre is not None:
            self._control.reproducir_lista_guardada(nombre)
            return
        if self._cargando or not self._temas_fuente:
            return
        self._control.reproducir_desde_aqui(self._temas_fuente, 0)

    def _agregar_coleccion_a_cola(self):
        nombre = self._coleccion_elegida()
        if nombre is not None:
            temas = tuple(self._control.temas_de_lista(nombre) or ())
        else:
            temas = tuple(self._temas_fuente)
        if temas:
            self._control.agregar_al_final(list(temas))

    def _accion_coleccion(self, accion):
        if accion == musica_menus.ACCION_REPRODUCIR_COLECCION:
            self._reproducir_coleccion()
        elif accion == musica_menus.ACCION_AGREGAR_COLECCION:
            self._agregar_coleccion_a_cola()
        elif accion == musica_menus.ACCION_EDITAR_LISTA:
            self._editar_lista()
        elif accion == musica_menus.ACCION_RENOMBRAR_LISTA:
            self._renombrar_lista()
        elif accion == musica_menus.ACCION_BORRAR_LISTA:
            self._borrar_lista()
        elif accion == musica_menus.ACCION_NUEVA_LISTA:
            self._nueva_lista()

    def _nueva_lista(self, tema_marcado=None):
        self._editar_lista_guardada(None, tema_marcado)

    def _editar_lista(self):
        nombre = self._coleccion_elegida()
        if nombre is not None:
            self._editar_lista_guardada(nombre)

    def _editar_lista_guardada(self, viejo, tema_marcado=None):
        if viejo is None:
            temas_lista = (tema_marcado,) if tema_marcado is not None else ()
        else:
            temas_lista = tuple(self._control.temas_de_lista(viejo) or ())
        temas_carpeta = tuple(self._biblioteca.temas()) \
            if self._biblioteca is not None else ()
        datos = musica_editor_lista.pedir_lista(
            self, viejo or "", temas_carpeta, temas_lista)
        if datos is None:
            return
        nombre, temas = datos
        self._control.guardar_lista(nombre, list(temas), viejo)
        self._reload_colecciones(preferir=nombre)
        self._cargar_fuente()

    def _menu_colecciones(self):
        musica_menus.mostrar_menu(
            self.lb_colecciones,
            musica_menus.entradas_colecciones(
                self._coleccion_elegida() is not None),
            self._accion_coleccion)

    def _renombrar_lista(self):
        viejo = self._coleccion_elegida()
        if viejo is None:
            return
        nombre = _acciones._pedir_nombre(
            self, _acciones.TITULO_RENOMBRAR, viejo)
        if nombre is None:
            return
        limpio = _acciones._validar_nombre(nombre)
        if limpio is None:
            self._control.renombrar_lista(viejo, nombre)
            return
        self._control.renombrar_lista(viejo, limpio)
        self._reload_colecciones(preferir=limpio)
        self._fuente = self._coleccion_elegida()

    def _borrar_lista(self):
        nombre = self._coleccion_elegida()
        if nombre is None or not _acciones._confirmar_borrar(self, nombre):
            return
        self._control.borrar_lista(nombre)
        self._reload_colecciones()
        self._cargar_fuente()
