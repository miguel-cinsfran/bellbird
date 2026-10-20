"""Igualación de volumen enchufada al control de música, sin interfaz.

Mezcla de `ControlMusica`: da la ganancia de cada tema desde la caché de
sonoridad y mide en segundo plano lo que falta, de a una canción por vez.
Trabajo silencioso salvo al empezar con 20 canciones o más por medir:
ahí avisa una vez, con sonido propio.
"""

from __future__ import annotations

import os
import threading

import wx

from ytchat.core import diagnostico
from ytchat.core import paths
from ytchat.downloads import ffmpeg_bin
from ytchat.music import anuncios
from ytchat.music import sonoridad


logger = diagnostico.obtener_logger(__name__)

_candado_sonoridad = threading.Lock()


class SonoridadMusica:
    """Ganancia por tema y medición de fondo de la música local."""

    _cache_sonoridad = None
    _progreso_sonoridad = None
    _midiendo_sonoridad = False

    def _cache_sonoridad_lista(self):
        """La caché de sonoridad, creada perezosa la primera vez.

        La crea con `paths.cache_sonoridad_musica()` y la guarda en
        `self._cache_sonoridad`. Protegida por un candado de módulo porque
        la piden el hilo del motor y el del índice. Nunca lanza: si no la
        puede crear, deja una línea en el registro y devuelve None.
        """
        try:
            cache = self._cache_sonoridad
            if cache is not None:
                return cache
            with _candado_sonoridad:
                cache = self._cache_sonoridad
                if cache is not None:
                    return cache
                nueva = sonoridad.CacheSonoridad(
                    paths.cache_sonoridad_musica())
                self._cache_sonoridad = nueva
                return nueva
        except Exception:
            logger.exception("No se pudo crear la caché de sonoridad")
            return None

    def _ganancia_de(self, tema) -> float:
        """La ganancia en dB de ese tema, o 0.0 si no hay que corregir.

        0.0 para los enlaces, con la opción apagada, si el archivo no se
        pudo leer o no está medido. Con la opción encendida la caché nace
        perezosa del disco, así la primera canción de la sesión ya iguala.
        Nunca lanza: lo llama el envoltorio al cargar cada tema.
        """
        try:
            if tema.es_enlace:
                return 0.0
            try:
                normalizar = bool(self._config.get(
                    "musica_normalizar", True))
            except Exception:
                normalizar = True
            if not normalizar:
                return 0.0
            cache = self._cache_sonoridad
            if cache is None:
                cache = self._cache_sonoridad_lista()
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
                if self._cache_sonoridad_lista() is None:
                    return
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
            if sonoridad.avisa_al_empezar(len(pendientes)):
                wx.CallAfter(self._avisar, anuncios.Aviso(
                    sonoridad.TEXTO_IGUALANDO.format(total=len(pendientes)),
                    "musica_igualando"))
        except Exception:
            logger.exception("No se pudo arrancar la medición de sonoridad")

    def texto_igualando(self) -> str:
        """El progreso de la igualación, para el componente de F2.

        Vacío si no se está midiendo. Función pura envuelta: la llama
        la GUI al armar el estado.
        """
        return sonoridad.texto_progreso(self._progreso_sonoridad)

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
