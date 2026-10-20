"""Igualación de volumen enchufada al control de música, sin interfaz.

Mezcla de `ControlMusica`: da la ganancia de cada tema desde la caché de
sonoridad y mide en segundo plano lo que falta, de a una canción por vez.
Trabajo silencioso: nada se anuncia y nada suena.
"""

from __future__ import annotations

import os

from ytchat.core import diagnostico
from ytchat.core import paths
from ytchat.downloads import ffmpeg_bin
from ytchat.music import sonoridad


logger = diagnostico.obtener_logger(__name__)


class SonoridadMusica:
    """Ganancia por tema y medición de fondo de la música local."""

    _cache_sonoridad = None
    _progreso_sonoridad = None
    _midiendo_sonoridad = False

    def _ganancia_de(self, tema) -> float:
        """La ganancia en dB de ese tema, o 0.0 si no hay que corregir.

        0.0 para los enlaces, sin caché todavía o si el archivo no se pudo
        leer o no está medido. Nunca lanza: lo llama el envoltorio al
        cargar cada tema.
        """
        try:
            if tema.es_enlace:
                return 0.0
            cache = self._cache_sonoridad
            if cache is None:
                return 0.0
            info = os.stat(tema.origen)
        except Exception:
            return 0.0
        try:
            return cache.buscar(
                tema.origen, info.st_mtime_ns, info.st_size) or 0.0
        except Exception:
            return 0.0

    def _aplicar_sonoridad(self) -> None:
        """Aplica la opción de igualar el volumen en caliente.

        Apagada, desactiva el envoltorio y el hilo en curso sale antes de
        la canción siguiente. Encendida, lo activa y, si hay biblioteca,
        mide lo que falte.
        """
        normalizar = bool(self._config.get("musica_normalizar", True))
        if self._adaptador is not None:
            self._adaptador.fijar_activo(normalizar)
        if normalizar and self._biblioteca is not None:
            self._arrancar_sonoridad(
                self._biblioteca, self._generacion_etiquetas)

    def _arrancar_sonoridad(self, biblioteca, generacion) -> None:
        """Mide en segundo plano las canciones sin ganancia guardada.

        Sin la opción, sin ffmpeg o sin pendientes no hace nada. La caché
        nace perezosa, como la de etiquetas. Nunca lanza.
        """
        try:
            if self._midiendo_sonoridad:
                return
            if not bool(self._config.get("musica_normalizar", True)):
                return
            if ffmpeg_bin.ruta_ffmpeg() is None:
                return
            if self._cache_sonoridad is None:
                self._cache_sonoridad = sonoridad.CacheSonoridad(
                    paths.cache_sonoridad_musica())
            pendientes = self._pendientes_sonoridad(biblioteca)
            if not pendientes:
                return
            hilo = diagnostico.crear_hilo(
                self._medir_sonoridad_fondo, "musica-sonoridad",
                args=(pendientes, generacion))
            self._midiendo_sonoridad = True
            try:
                hilo.start()
            except Exception:
                self._midiendo_sonoridad = False
                raise
        except Exception:
            logger.exception("No se pudo arrancar la medición de sonoridad")

    def _pendientes_sonoridad(self, biblioteca) -> tuple:
        """Las canciones locales sin ganancia válida en la caché, en orden."""
        pendientes = []
        for tema in biblioteca.temas():
            if tema.es_enlace:
                continue
            try:
                info = os.stat(tema.origen)
            except OSError:
                continue
            try:
                medido = self._cache_sonoridad.buscar(
                    tema.origen, info.st_mtime_ns, info.st_size)
            except Exception:
                continue
            if medido is None:
                pendientes.append(tema)
        return tuple(pendientes)

    def _medir_sonoridad_fondo(self, pendientes, generacion) -> None:
        """Mide las pendientes de a una y guarda cada ganancia en la caché.

        Corre en el hilo «musica-sonoridad». Antes de cada canción sale si
        cambió la generación, si se cerró o si se apagó la opción. Lo que
        dio None no se guarda: se reintenta en la próxima apertura. Guarda
        en disco cada 20 y al final. Deja el progreso en
        `self._progreso_sonoridad` mientras trabaja y None al salir.
        """
        total = len(pendientes)
        hechas = intentadas = 0
        try:
            ruta = ffmpeg_bin.ruta_ffmpeg()
            if ruta is None:
                return
            for tema in pendientes:
                if (generacion != self._generacion_etiquetas
                        or self._cerrado
                        or not bool(self._config.get(
                            "musica_normalizar", True))):
                    return
                self._progreso_sonoridad = (intentadas, total)
                intentadas += 1
                try:
                    info = os.stat(tema.origen)
                except OSError:
                    continue
                try:
                    ganancia = sonoridad.medir(ruta, tema.origen)
                except Exception:
                    logger.exception("No se pudo medir %s", tema.origen)
                    continue
                if ganancia is None:
                    continue
                try:
                    self._cache_sonoridad.poner(
                        tema.origen, info.st_mtime_ns, info.st_size,
                        ganancia)
                except Exception:
                    logger.exception("No se pudo guardar %s", tema.origen)
                    continue
                hechas += 1
                if hechas % 20 == 0:
                    self._guardar_sonoridad()
            self._guardar_sonoridad()
        finally:
            self._midiendo_sonoridad = False
            self._progreso_sonoridad = None

    def _guardar_sonoridad(self) -> None:
        """Escribe la caché de sonoridad en disco. Nunca lanza."""
        try:
            if self._cache_sonoridad is not None:
                self._cache_sonoridad.guardar()
        except Exception:
            logger.exception("No se pudo guardar la caché de sonoridad")
