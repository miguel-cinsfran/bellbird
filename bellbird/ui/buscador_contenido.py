"""Vista de contenido de una lista o un canal de la búsqueda.

Razón del módulo: entrar a ver los vídeos de una lista o un canal con
la misma lista y los mismos detalles, y volver a lo guardado. No abre
otra ventana.
"""

from __future__ import annotations

import time

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.downloads.busqueda_youtube import contenido
from bellbird.downloads.textos_busqueda import (
    texto_duracion, texto_fecha, texto_vistas)
from bellbird.ui import buscador_tandas
from bellbird.ui.buscador_tandas import anunciar_tanda
from bellbird.ui.accesibilidad import anunciar
from bellbird.voice import sound_player as _snd

logger = diagnostico.obtener_logger(__name__)


def agregar_filas(lista, nuevos) -> None:
    """Agrega esas filas a la lista: título, canal, duración, vistas y fecha."""
    ahora = time.time()
    for resultado in nuevos:
        i = lista.InsertItem(lista.GetItemCount(), resultado.titulo)
        lista.SetItem(i, 1, resultado.canal)
        lista.SetItem(i, 2, texto_duracion(resultado.duracion))
        lista.SetItem(i, 3, texto_vistas(resultado.vistas))
        lista.SetItem(i, 4, texto_fecha(resultado.marca_tiempo, ahora))


def enfocar_fila(lista, indice) -> None:
    """Selecciona y enfoca esa fila; sin filas válidas, enfoca la lista."""
    if 0 <= indice < lista.GetItemCount():
        lista.Select(indice)
        lista.Focus(indice)
        lista.EnsureVisible(indice)
    else:
        lista.SetFocus()


def _sonar_error() -> None:
    try:
        _snd.reproducir("error")
    except Exception as error:
        logger.debug("sin sonido de error: %s", error)


class VistaContenido:
    """El contenido de una lista o un canal dentro de la misma lista.

    Recibe la página para usar sus controles públicos, más cuatro
    funciones: `al_sincronizar(todos, nuevos, mas)` deja los vídeos en
    la página, `al_restaurar(guardados, error)` reconstruye lo guardado,
    `al_agregar(urls)` encola y devuelve cuántos entraron, y
    `leer_cantidad()` dice la tanda elegida.
    """

    def __init__(self, pagina, al_sincronizar, al_restaurar, al_agregar,
                 leer_cantidad):
        self._pagina = pagina
        self._al_sincronizar = al_sincronizar
        self._al_restaurar = al_restaurar
        self._al_agregar = al_agregar
        self._leer_cantidad = leer_cantidad
        self._tandas = buscador_tandas.Tandas(pagina.lista, pagina.btn_mas)
        self._activa = False
        self._url = ""
        self._titulo = ""
        self._total = 0
        self._es_canal = False
        self._con_retorno = True
        self._guardados = None

    @property
    def activa(self) -> bool:
        return self._activa

    def mostrar(self, url, guardados, con_retorno=True, es_canal=False) -> None:
        """Entra a ver el contenido de esa URL y trae la primera tanda."""
        pagina = self._pagina
        self._activa = True
        self._url = url
        self._titulo = ""
        self._total = 0
        self._es_canal = es_canal
        self._con_retorno = con_retorno
        self._guardados = guardados
        pagina.txt_detalles.SetValue("")
        pagina.btn_volver.Show(con_retorno)
        pagina.btn_todo.Show(not es_canal)
        pagina.Layout()
        self._al_sincronizar([], [], False)
        self._tandas.pedir(
            lambda inicio, cantidad: contenido(self._url, inicio, cantidad),
            self._leer_cantidad(), self._al_tanda, nombre="ContenidoLista")
        anunciar(_("Buscando"))

    def mas(self) -> None:
        """Trae la tanda siguiente del contenido."""
        if self._activa:
            self._tandas.pedir(
                lambda inicio, cantidad: contenido(self._url, inicio, cantidad),
                self._leer_cantidad(), self._al_tanda, mas=True,
                nombre="ContenidoLista")

    def volver(self, _event=None):
        """Sale de la vista y reconstruye lo guardado."""
        pagina = self._pagina
        if wx.Window.FindFocus() in (pagina.btn_volver, pagina.btn_todo):
            pagina.lista.SetFocus()
        guardados = self._cerrar_sin_reconstruir()
        self._al_restaurar(guardados)

    def cerrar(self) -> None:
        """Cierra la vista sin reconstruir: la usa una búsqueda nueva."""
        self._cerrar_sin_reconstruir()

    def todo(self, _event=None) -> None:
        """Encola la lista entera."""
        if self._activa:
            self._al_agregar([self._url])

    def _al_tanda(self, nuevos, mas, respuesta, foco_en_mas):
        pagina = self._pagina
        if not pagina or not self._activa:
            return
        if respuesta.error:
            pagina.txt_detalles.SetValue(respuesta.error)
            _sonar_error()
            anunciar(respuesta.error)
            self._al_restaurar(self._cerrar_sin_reconstruir())
            if foco_en_mas:
                pagina.lista.SetFocus()
            return
        if mas:
            self._volver_mas(nuevos, foco_en_mas)
        else:
            self._volver_primera(nuevos, respuesta)

    def _cerrar_sin_reconstruir(self):
        pagina = self._pagina
        pagina.btn_volver.Show(False)
        pagina.btn_todo.Show(False)
        pagina.Layout()
        self._activa = False
        guardados = self._guardados
        self._guardados = None
        return guardados

    def _volver_primera(self, nuevos, respuesta) -> None:
        pagina = self._pagina
        self._titulo, self._total = respuesta.titulo, respuesta.total
        self._al_sincronizar(self._tandas.acumulado, list(nuevos), False)
        enfocar_fila(pagina.lista, 0)
        if self._total:
            anunciar(_("{titulo}: {total} vídeos").format(
                titulo=self._titulo, total=self._total))
        elif self._titulo:
            anunciar(self._titulo)

    def _volver_mas(self, nuevos, foco_en_mas) -> None:
        pagina = self._pagina
        if not nuevos:
            anunciar(_("No hay más resultados"))
            if foco_en_mas:
                pagina.lista.SetFocus()
            return
        self._al_sincronizar(self._tandas.acumulado, list(nuevos), True)
        enfocar_fila(pagina.lista, len(self._tandas.acumulado) - len(nuevos))
        if foco_en_mas:
            pagina.lista.SetFocus()
        anunciar_tanda(len(nuevos), True)
