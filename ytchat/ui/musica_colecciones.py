"""Lista de colecciones de la ventana de música.

La mezcla guarda la fuente elegida (la carpeta o una lista propia) y carga
sus temas en la lista que arma `VentanaMusica`. «Biblioteca» es la carpeta;
debajo va una fila por lista propia. Intro reproduce la colección entera y
Suprimir borra la lista, previa confirmación.
"""

from __future__ import annotations

import wx

from ytchat.core import diagnostico
from ytchat.music import anuncios, listas, vista
from ytchat.ui import musica_editor_lista, musica_menus
from ytchat.ui import musica_ventana_acciones as _acciones

logger = diagnostico.obtener_logger(__name__)

TEXTO_CARGANDO = "Cargando la carpeta…"
TEXTO_SIN_CARPETA = "No hay carpeta de música"


def _anunciar_ventana(texto) -> None:
    """Anuncia por la ventana, no por este módulo.

    El import es perezoso porque musica_ventana importa este módulo.
    """
    from ytchat.ui import musica_ventana
    musica_ventana.anunciar(texto)


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
        self.lb_colecciones.Set(self._refrescar_cantidades_colecciones())
        indice = 0
        if preferir:
            buscado = str(preferir).casefold()
            for posicion, nombre in enumerate(nombres, start=1):
                if nombre.casefold() == buscado:
                    indice = posicion
                    break
        self.lb_colecciones.SetSelection(indice)
        self._fuente = self._coleccion_elegida()

    def _refrescar_cantidades_colecciones(self):
        nombres = self._nombres_listas or []
        cantidad = getattr(self, "_cantidad_biblioteca", None)
        try:
            carpeta = self._control.carpeta_listas()
        except Exception as exc:
            logger.debug("No se pudieron leer las listas de música: %s", exc)
            carpeta = None
        if carpeta is None:
            cantidades = {}
        else:
            cantidades = {n: listas.cantidad(carpeta, n) for n in nombres}
        filas = vista.filas_colecciones(nombres, cantidad, cantidades)
        actuales = self.lb_colecciones.GetStrings()
        for indice, texto in enumerate(filas):
            if indice < len(actuales) and texto != actuales[indice]:
                self.lb_colecciones.SetString(indice, texto)
        return filas

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
        self.filtros.refrescar_artistas(self._temas_fuente)
        self._aplicar_filtro()
        self._estado_listo()
        indice = vista.indice_seleccion_tras_refrescar(
            seleccion, len(self._temas_filtrados))
        if indice >= 0:
            self.lb_temas.SetSelection(indice)

    def _al_biblioteca(self, biblioteca, generacion):
        if not self or generacion != self._generacion or self._fuente is not None:
            return
        if biblioteca is None:
            self._cantidad_biblioteca = None
            self._temas_fuente = self._temas_filtrados = ()
            self._cambiar_estado(TEXTO_SIN_CARPETA)
            return
        self._biblioteca = biblioteca
        self._cantidad_biblioteca = len(biblioteca.temas())
        self._temas_fuente = tuple(biblioteca.temas())
        self._cargando = False
        self.filtros.refrescar_artistas(self._temas_fuente)
        self._aplicar_filtro()
        self._estado_listo()
        self._resumir_y_preguntar(biblioteca)

    def _resumir_y_preguntar(self, biblioteca):
        """Resume la carpeta al abrirla y pregunta por igualar el volumen."""
        if self._primera_carga:
            self._primera_carga = False
            _anunciar_ventana(vista.texto_resumen(
                len(self._temas_fuente), len(self._temas_filtrados), False))
        self._refrescar_cantidades_colecciones()
        self.preguntar_igualacion(biblioteca)

    def refrescar_por_vigia(self):
        """Pone al día la lista con lo que vio el vigía, si muestra la carpeta.

        Vuelve a tomar los temas de la biblioteca y reaplica el filtro de
        Buscar, conservando el tema elegido si sigue estando (si no, el
        índice más cercano). Actualiza la cantidad de «Colecciones». No
        mueve el foco. Con una lista propia, no hace nada.
        """
        if (not self or self._fuente is not None
                or self._biblioteca is None):
            return
        elegido = self._origen_elegido()
        self._temas_fuente = tuple(self._biblioteca.temas())
        self._cantidad_biblioteca = len(self._temas_fuente)
        self.filtros.refrescar_artistas(self._temas_fuente)
        self._aplicar_filtro()
        self._seleccionar_origen(elegido)
        self._refrescar_cantidades_colecciones()

    def _seleccionar_origen(self, elegido):
        """Deja elegido el tema con ese origen, si sigue estando."""
        if elegido is None:
            return
        for indice, candidato in enumerate(self._temas_filtrados):
            if candidato.origen == elegido:
                self.lb_temas.SetSelection(indice)
                return

    def _origen_elegido(self):
        """El origen del tema elegido, o None sin selección."""
        seleccion = self.lb_temas.GetSelection()
        if 0 <= seleccion < len(self._temas_filtrados):
            return self._temas_filtrados[seleccion].origen
        return None

    def examinar_carpeta(self) -> None:
        """Vuelve a examinar la carpeta en un hilo y anuncia el resultado.

        Mientras examina, otra pulsación no lanza otro hilo.
        """
        if getattr(self, "_examinando", False):
            return
        if not self._control._carpeta():
            _anunciar_ventana(anuncios.TEXTO_SIN_CARPETA)
            return
        self._examinando = True
        self._control.reexaminar_carpeta(self._al_examinar)

    def _al_examinar(self, biblioteca, nuevas, quitadas) -> None:
        """Refresca la lista y anuncia lo que encontró el examen."""
        if not self:
            return
        self._examinando = False
        if biblioteca is None:
            _anunciar_ventana(anuncios.TEXTO_SIN_CARPETA)
            return
        if biblioteca is not self._biblioteca:
            return
        if self._fuente is None:
            self.refrescar_por_vigia()
        _anunciar_ventana(vista.texto_carpeta_examinada(nuevas, quitadas))

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
