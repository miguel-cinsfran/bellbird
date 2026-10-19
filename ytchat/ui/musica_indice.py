"""Índice compartido de la carpeta de música y lectura de etiquetas."""

from __future__ import annotations

import os
from pathlib import Path

import wx

from ytchat.core import config as cfg
from ytchat.core import diagnostico
from ytchat.core import paths
from ytchat.music import anuncios
from ytchat.music.adaptador_vlc import leer_etiquetas_vlc
from ytchat.music.biblioteca import Biblioteca, ErrorBiblioteca
from ytchat.music.etiquetas import CacheEtiquetas
from ytchat.music.modelo import Tema, normalizar_duracion
from ytchat.player import motor_vlc


logger = diagnostico.obtener_logger(__name__)

TEXTO_CARPETA_INEXISTENTE = (
    "No se encontró la carpeta de música. Elige otra en Preferencias, "
    "página Música")


class IndiceMusica:
    """Índice de la carpeta de música y etiquetas leídas en segundo plano."""

    def biblioteca(self, al_lista) -> None:
        """Entrega la biblioteca indexada a `al_lista`.

        Sin índice todavía, o con la carpeta cambiada, indexa en un hilo y
        llama `al_lista(biblioteca)` con wx.CallAfter. Si ya estaba indexada,
        llama a `al_lista` enseguida. Si el índice no se pudo armar, entrega
        None.
        """
        if self._biblioteca is not None:
            al_lista(self._biblioteca)
            return
        carpeta = self._carpeta()
        if not carpeta:
            al_lista(None)
            return
        diagnostico.crear_hilo(
            self._indexar, "musica-indice", args=(carpeta, al_lista)).start()

    def cambiar_carpeta(self, ruta) -> None:
        """Guarda la carpeta nueva e invalida el índice compartido."""
        ruta = (ruta or "").strip()
        self._config["musica_carpeta"] = ruta
        self._biblioteca = None
        self._generacion_etiquetas += 1
        self._guardar("carpeta", cfg.codificar_texto_ini(ruta))

    def _reproducir_carpeta(self) -> None:
        self.biblioteca(self._reproducir_indexado)

    def _indexar(self, carpeta, al_lista) -> None:
        try:
            if self._cache_etiquetas is None:
                self._cache_etiquetas = CacheEtiquetas(
                    paths.cache_etiquetas_musica())
            biblioteca = Biblioteca(carpeta, cache=self._cache_etiquetas)
            biblioteca.indexar()
        except ErrorBiblioteca:
            wx.CallAfter(al_lista, None)
            return
        except Exception:
            logger.exception("No se pudo indexar la carpeta de música")
            wx.CallAfter(al_lista, None)
            return
        self._biblioteca = biblioteca
        self._generacion_etiquetas += 1
        generacion = self._generacion_etiquetas
        wx.CallAfter(al_lista, biblioteca)
        self._arrancar_etiquetas(biblioteca, generacion)

    def _arrancar_etiquetas(self, biblioteca, generacion) -> None:
        """Lee en segundo plano las etiquetas que faltan, sin bloquear.

        El hilo usa la caché: lo ya leído sale desde el principio y solo se
        lee con libVLC lo pendiente. Sin motor no arranca, porque todo daría
        vacío y quedaría cacheado como «sin etiquetas».
        """
        try:
            pendientes = biblioteca.pendientes()
        except Exception:
            logger.debug("No se pudieron calcular las etiquetas pendientes")
            return
        if not pendientes:
            return
        if not motor_vlc.disponible():
            return
        diagnostico.crear_hilo(
            self._leer_etiquetas_fondo, "musica-etiquetas",
            args=(biblioteca, tuple(pendientes), generacion)).start()

    def _leer_etiquetas_fondo(self, biblioteca, pendientes, generacion) -> None:
        """Lee las etiquetas pendientes y aplica cada lote en la interfaz.

        Corre en el hilo «musica-etiquetas», nunca en el de wx ni en un
        callback de VLC. Trabajo silencioso: nada se anuncia y nada suena.
        Si la carpeta cambió a mitad, termina sin hacer nada más.
        """
        lote: dict[str, Tema] = {}
        for indice, tema in enumerate(tuple(pendientes), 1):
            if generacion != self._generacion_etiquetas or self._cerrado:
                return
            origen = tema.origen
            try:
                info = os.stat(origen)
            except OSError:
                continue
            datos = leer_etiquetas_vlc(origen)
            datos = datos if isinstance(datos, dict) else {}
            self._cache_etiquetas.poner(
                origen, info.st_mtime_ns, info.st_size, datos)
            titulo = str(datos.get("titulo") or "") or Path(origen).stem
            lote[origen] = Tema(
                origen, titulo,
                str(datos.get("artista") or ""),
                str(datos.get("album") or ""),
                normalizar_duracion(datos.get("duracion_ms")))
            if indice % 50 == 0:
                self._cache_etiquetas.guardar()
                wx.CallAfter(self._aplicar_lote_etiquetas, dict(lote), generacion)
                lote.clear()
        self._cache_etiquetas.guardar()
        if lote:
            wx.CallAfter(self._aplicar_lote_etiquetas, dict(lote), generacion)

    def _aplicar_lote_etiquetas(self, mapa, generacion) -> None:
        """Pone al día biblioteca, cola y ventana con un lote de etiquetas.

        Corre en el hilo de la interfaz vía `wx.CallAfter`. Silencioso: no
        anuncia ni suena. Si la carpeta cambió a mitad, no aplica nada.
        """
        if generacion != self._generacion_etiquetas or self._cerrado:
            return
        biblioteca = self._biblioteca
        if biblioteca is None or not mapa:
            return
        biblioteca.actualizar(tuple(mapa.values()))
        if self._coordinador is not None:
            self._coordinador.actualizar_temas(mapa)
        ventana = self._ventanas.get("musica")
        if ventana is not None:
            try:
                ventana.actualizar_nombres(mapa)
            except Exception:
                logger.debug("No se pudo actualizar la ventana de música")

    def _reproducir_indexado(self, biblioteca) -> None:
        if biblioteca is None:
            self._avisar(anuncios.Aviso(
                TEXTO_CARPETA_INEXISTENTE, anuncios.SONIDO_ERROR))
            return
        if self._coordinador is None:
            return
        resultado = self._coordinador.reproducir_lista(biblioteca.temas())
        self._avisar(anuncios.aviso_accion(
            "reproducir", resultado, self._incluir_artista()))
        self._guardar_memoria()
