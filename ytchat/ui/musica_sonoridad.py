"""Igualación de volumen enchufada al control de música, sin interfaz.

Mezcla de `ControlMusica`: da la ganancia de cada tema desde la caché de
sonoridad y, cuando el usuario lo pide, mide de a una canción las que
faltan. La medición no arranca sola: la pide la ventana de música, con su
botón o con la pregunta que sale al abrirla.
"""

from __future__ import annotations

import os
import threading

import wx

from ytchat.core import diagnostico
from ytchat.core import paths
from ytchat.downloads import ffmpeg_bin
from ytchat.music import sonoridad


logger = diagnostico.obtener_logger(__name__)

_candado_sonoridad = threading.Lock()


class SonoridadMusica:
    """Ganancia por tema y medición de la música local."""

    _cache_sonoridad = None
    _progreso_sonoridad = None
    _midiendo_sonoridad = False
    _detener_sonoridad = False
    _total_sonoridad = 0
    _calculando_pendientes = False

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
        la canción siguiente. Encendida, lo activa. No mide nada: medir lo
        pide el usuario, desde la ventana de música.
        """
        normalizar = bool(self._config.get("musica_normalizar", True))
        if self._adaptador is not None:
            self._adaptador.fijar_activo(normalizar)

    def iniciar_igualacion(self, biblioteca) -> sonoridad.ResultadoIgualacion:
        """Mide las canciones pendientes, si se puede. Dice qué pasó.

        Calcula las pendientes en el acto: la ventana no la usa, que pide
        el cálculo en un hilo y arranca con `iniciar_medicion`. Nunca lanza.
        """
        pendientes, _total = self._pendientes_sonoridad(biblioteca)
        return self.iniciar_medicion(pendientes)

    def iniciar_medicion(self, pendientes) -> sonoridad.ResultadoIgualacion:
        """Mide esas pendientes ya calculadas, si se puede. Dice qué pasó.

        Es la entrada que usa la ventana, con lo que calculó en el hilo
        «musica-pendientes»: no vuelve a calcular nada. Con la opción
        apagada, sin ffmpeg o sin pendientes no mide nada. Nunca lanza.
        """
        if self._midiendo_sonoridad:
            return sonoridad.ResultadoIgualacion(
                sonoridad.YA_MIDIENDO, self._total_sonoridad)
        if not bool(self._config.get("musica_normalizar", True)):
            return sonoridad.ResultadoIgualacion(sonoridad.OPCION_APAGADA)
        if ffmpeg_bin.ruta_ffmpeg() is None:
            return sonoridad.ResultadoIgualacion(sonoridad.SIN_FFMPEG)
        if not pendientes:
            return sonoridad.ResultadoIgualacion(sonoridad.NADA_PENDIENTE)
        try:
            self._detener_sonoridad = False
            self._total_sonoridad = len(pendientes)
            hilo = diagnostico.crear_hilo(
                self._medir_sonoridad_fondo, "musica-sonoridad",
                args=(tuple(pendientes), self._generacion_etiquetas))
            self._midiendo_sonoridad = True
            try:
                hilo.start()
            except Exception:
                self._midiendo_sonoridad = False
                raise
        except Exception:
            logger.exception("No se pudo arrancar la medición de sonoridad")
            return sonoridad.ResultadoIgualacion(sonoridad.NADA_PENDIENTE)
        return sonoridad.ResultadoIgualacion(sonoridad.INICIO, len(pendientes))

    def pedir_pendientes(self, biblioteca, al_pendientes) -> None:
        """Calcula las pendientes en un hilo y las entrega con `al_pendientes`.

        La entrega llega con wx.CallAfter. Si ya se está calculando o
        midiendo, no hace nada: una segunda pulsación del botón no lanza
        otro cálculo. Nunca lanza.
        """
        try:
            if biblioteca is None:
                return
            if self._calculando_pendientes or self._midiendo_sonoridad:
                return
            self._calculando_pendientes = True
            hilo = diagnostico.crear_hilo(
                self._calcular_pendientes_fondo, "musica-pendientes",
                args=(biblioteca, al_pendientes))
            try:
                hilo.start()
            except Exception:
                self._calculando_pendientes = False
                raise
        except Exception:
            logger.exception("No se pudieron pedir las pendientes")

    def _calcular_pendientes_fondo(self, biblioteca, al_pendientes) -> None:
        """Calcula las pendientes y las entrega en la interfaz.

        Corre en el hilo «musica-pendientes». Nunca lanza.
        """
        try:
            pendientes, total = self._pendientes_sonoridad(biblioteca)
        except Exception:
            logger.exception("No se pudieron calcular las pendientes")
            pendientes, total = (), 0
        self._calculando_pendientes = False
        try:
            wx.CallAfter(al_pendientes, pendientes, total)
        except Exception:
            logger.exception("No se pudieron entregar las pendientes")

    def detener_igualacion(self) -> None:
        """Pide que la medición pare antes de la canción siguiente."""
        self._detener_sonoridad = True

    def midiendo_igualacion(self) -> bool:
        """Si hay una medición en curso."""
        return bool(self._midiendo_sonoridad)

    def datos_igualacion(self, biblioteca) -> tuple | None:
        """Cuántas canciones quedan sin medir y cuánto ocupan.

        Calcula las pendientes en el acto: la ventana no la usa, que pide
        el cálculo en un hilo y valida con `confirmar_pregunta`. None si
        no hay que preguntar.
        """
        if biblioteca is None:
            return None
        pendientes, total = self._pendientes_sonoridad(biblioteca)
        return self.confirmar_pregunta(pendientes, total)

    def confirmar_pregunta(self, pendientes, total) -> tuple | None:
        """Si hay que preguntar con esas pendientes ya calculadas.

        None si no hay que preguntar: sin la opción de igualar, sin la de
        preguntar, sin ffmpeg, midiendo ya o sin pendientes. Función pura
        envuelta: no toca el disco.
        """
        if not pendientes:
            return None
        if not bool(self._config.get("musica_normalizar", True)):
            return None
        if not bool(self._config.get("musica_preguntar_igualar", True)):
            return None
        if self._midiendo_sonoridad:
            return None
        if ffmpeg_bin.ruta_ffmpeg() is None:
            return None
        return (len(pendientes), total)

    def fijar_preguntar_igualar(self, valor) -> None:
        """Guarda si se pregunta al abrir la ventana de música.

        En memoria y en el config.ini, por el mismo camino que las demás
        opciones de música.
        """
        activar = bool(valor)
        self._config["musica_preguntar_igualar"] = activar
        self._guardar("preguntar_igualar", "true" if activar else "false")

    def texto_igualando(self) -> str:
        """El progreso de la igualación, para el componente de F2.

        Vacío si no se está midiendo. Función pura envuelta: la llama
        la GUI al armar el estado.
        """
        return sonoridad.texto_progreso(self._progreso_sonoridad)

    def _pendientes_sonoridad(self, biblioteca) -> tuple:
        """Las canciones locales sin ganancia válida en la caché, en orden.

        Devuelve también el tamaño que ocupan en disco, en la misma
        pasada: la suma no se calcula aparte.
        """
        if biblioteca is None:
            return ((), 0)
        cache = self._cache_sonoridad
        if cache is None:
            cache = self._cache_sonoridad_lista()
        if cache is None:
            return ((), 0)
        pendientes = []
        total = 0
        for tema in biblioteca.temas():
            if tema.es_enlace:
                continue
            try:
                info = os.stat(tema.origen)
            except OSError:
                continue
            try:
                medido = cache.buscar(
                    tema.origen, info.st_mtime_ns, info.st_size)
            except Exception:
                continue
            if medido is None:
                pendientes.append(tema)
                total += info.st_size
        return (tuple(pendientes), total)

    def _medir_sonoridad_fondo(self, pendientes, generacion) -> None:
        """Mide las pendientes de a una y guarda cada ganancia en la caché.

        Corre en el hilo «musica-sonoridad». Antes de cada canción sale si
        cambió la generación, si se cerró, si se apagó la opción o si se
        pidió detener. Lo que dio None no se guarda: se reintenta en la
        próxima apertura. Guarda en disco cada 20 y al final. Deja el
        progreso en `self._progreso_sonoridad` mientras trabaja y None al
        salir.
        """
        total = len(pendientes)
        hechas = intentadas = 0
        try:
            ruta = ffmpeg_bin.ruta_ffmpeg()
            if ruta is None:
                return
            for tema in pendientes:
                if not self._seguir_midiendo(generacion):
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

    def _seguir_midiendo(self, generacion) -> bool:
        """Si la medición puede seguir con la canción siguiente."""
        if generacion != self._generacion_etiquetas:
            return False
        if self._cerrado or self._detener_sonoridad:
            return False
        return bool(self._config.get("musica_normalizar", True))

    def _guardar_sonoridad(self) -> None:
        """Escribe la caché de sonoridad en disco. Nunca lanza."""
        try:
            if self._cache_sonoridad is not None:
                self._cache_sonoridad.guardar()
        except Exception:
            logger.exception("No se pudo guardar la caché de sonoridad")
