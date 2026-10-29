"""Vigía de la carpeta de música: avisa cuando cambia, sin recorrerla.

Un Observer de watchdog junta los eventos y, cuando pasan `espera_s` sin
eventos nuevos, llama una sola vez a `al_cambiar(agregadas, quitadas)` con
conjuntos de rutas, desde su hilo. Archivo creado o modificado: agregada.
Archivo borrado: quitada. Movido: origen quitado y destino agregado.
Carpeta creada o movida adentro: se recorre y sus audios van como
agregadas. Carpeta borrada o movida afuera: quitada. Lo que no tiene
extensión de audio y no es carpeta se ignora. Un archivo que entra y sale
en la misma tanda no aparece en ninguna. Sin wx: lo usa el control.
"""

from __future__ import annotations

import os
import threading
import time

from bellbird.core import diagnostico
from bellbird.music.biblioteca import EXTENSIONES


logger = diagnostico.obtener_logger(__name__)


def _es_audio(ruta: str) -> bool:
    return os.path.splitext(ruta)[1].lower() in EXTENSIONES


def _neto(agregadas: set, quitadas: set) -> tuple[set, set]:
    """Saca de las dos tandas lo que entra y sale, sin distinguir mayúsculas."""
    en_ambas = {os.path.normcase(a) for a in agregadas} & {
        os.path.normcase(q) for q in quitadas}
    return ({a for a in agregadas if os.path.normcase(a) not in en_ambas},
            {q for q in quitadas if os.path.normcase(q) not in en_ambas})


class VigiaCarpeta:
    """Un Observer de watchdog sobre la carpeta, con espera anti-rebote.

    De un solo uso: `arrancar` empieza a vigilar y `parar` lo deja. Los
    dos nunca lanzan; si la carpeta no existe o watchdog falla, queda sin
    vigilar y se registra con `logger.warning`.
    """

    def __init__(self, carpeta, al_cambiar, espera_s=2.0):
        self._carpeta = os.path.abspath(str(carpeta))
        self._al_cambiar = al_cambiar
        self._espera_s = max(0.0, float(espera_s))
        self._bloqueo = threading.Lock()
        self._agregadas = set()
        self._quitadas = set()
        self._ultimo = 0.0
        self._hilo_vivo = False
        self._apagado = False
        self._observador = None

    def arrancar(self) -> None:
        """Empieza a vigilar la carpeta. Nunca lanza."""
        try:
            with self._bloqueo:
                if self._observador is not None:
                    return
                self._apagado = False
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
            if not os.path.isdir(self._carpeta):
                logger.warning(
                    "Sin vigía de música: la carpeta no existe: %s",
                    self._carpeta)
                return
            vigia = self

            class _Manejador(FileSystemEventHandler):
                def on_created(self, evento):
                    vigia._creado(evento.src_path, evento.is_directory)

                def on_modified(self, evento):
                    vigia._modificado(evento.src_path, evento.is_directory)

                def on_deleted(self, evento):
                    vigia._borrado(evento.src_path)

                def on_moved(self, evento):
                    vigia._movido(evento.src_path, evento.dest_path,
                                  evento.is_directory)

            observador = Observer()
            observador.schedule(_Manejador(), self._carpeta, recursive=True)
            observador.start()
            with self._bloqueo:
                self._observador = observador
        except Exception as exc:
            logger.warning("Sin vigía de música: no se pudo arrancar: %s", exc)

    def parar(self) -> None:
        """Deja de vigilar y espera al hilo como mucho 2 s. Nunca lanza."""
        with self._bloqueo:
            self._apagado = True
            observador = self._observador
            self._observador = None
        if observador is None:
            return
        try:
            observador.stop()
            observador.join(timeout=2)
        except Exception as exc:
            logger.warning("No se pudo parar el vigía de música: %s", exc)

    def _adentro(self, ruta: str) -> bool:
        normal = os.path.normcase(os.path.abspath(str(ruta)))
        base = os.path.normcase(self._carpeta)
        return normal == base or normal.startswith(base + os.sep)

    def _creado(self, ruta, es_carpeta) -> None:
        if not self._adentro(ruta):
            return
        if es_carpeta or os.path.isdir(ruta):
            self._agregar_carpeta(ruta)
        elif _es_audio(ruta):
            self._anotar_agregada(ruta)

    def _modificado(self, ruta, es_carpeta) -> None:
        if es_carpeta or not self._adentro(ruta):
            return
        if _es_audio(ruta):
            self._anotar_agregada(ruta)

    def _borrado(self, ruta) -> None:
        if self._adentro(ruta):
            self._anotar_quitada(ruta)

    def _movido(self, origen, destino, es_carpeta) -> None:
        if self._adentro(origen):
            self._anotar_quitada(origen)
        if not self._adentro(destino):
            return
        if es_carpeta or os.path.isdir(destino):
            self._agregar_carpeta(destino)
        elif _es_audio(destino):
            self._anotar_agregada(destino)

    def _agregar_carpeta(self, ruta) -> None:
        try:
            paseo = os.walk(ruta)
            audios = [os.path.join(raiz, nombre)
                      for raiz, _subcarpetas, archivos in paseo
                      for nombre in archivos if _es_audio(nombre)]
        except OSError as exc:
            logger.debug("No se pudo recorrer %s para el vigía: %s", ruta, exc)
            return
        for audio in audios:
            self._anotar_agregada(audio)

    def _anotar_agregada(self, ruta) -> None:
        with self._bloqueo:
            if self._apagado:
                return
            self._agregadas.add(os.path.abspath(ruta))
            self._programar_bloqueado()

    def _anotar_quitada(self, ruta) -> None:
        with self._bloqueo:
            if self._apagado:
                return
            self._quitadas.add(os.path.abspath(ruta))
            self._programar_bloqueado()

    def _programar_bloqueado(self) -> None:
        """Marca el último evento y arranca la espera, con el lock tomado."""
        self._ultimo = time.monotonic()
        if self._hilo_vivo:
            return
        self._hilo_vivo = True
        diagnostico.crear_hilo(self._tanda, "musica-vigia").start()

    def _tanda(self) -> None:
        """Espera la quietud y avisa una sola vez, en el hilo musica-vigia."""
        try:
            while True:
                time.sleep(0.05)
                with self._bloqueo:
                    if self._apagado:
                        return
                    if time.monotonic() - self._ultimo < self._espera_s:
                        continue
                    marca = self._ultimo
                    agregadas = set(self._agregadas)
                    quitadas = set(self._quitadas)
                    self._agregadas.clear()
                    self._quitadas.clear()
                agregadas, quitadas = _neto(agregadas, quitadas)
                if agregadas or quitadas:
                    try:
                        self._al_cambiar(agregadas, quitadas)
                    except Exception as exc:
                        logger.warning("El aviso del vigía falló: %s", exc)
                with self._bloqueo:
                    if self._apagado or self._ultimo == marca:
                        return
        finally:
            with self._bloqueo:
                self._hilo_vivo = False
