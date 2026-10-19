"""Índice en memoria de una carpeta de audio y lectura de listas .m3u8."""

from __future__ import annotations

import os
import re
import threading
import unicodedata
from pathlib import Path

from ytchat.music import enlaces
from ytchat.music.modelo import Tema, normalizar_duracion


EXTENSIONES = {
    ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wav", ".wma",
}

_URL_CON_ESQUEMA = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


class ErrorBiblioteca(ValueError):
    """Carpeta, lista o entrada de lista inválida."""


def _plegar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar búsquedas."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return sin_tildes.casefold()


def _leer_extinf(entrada: str) -> tuple[int, str]:
    """Los milisegundos y el título de una línea #EXTINF.

    Segundos no positivos (el -1 de «no se sabe») dan duración 0.
    """
    segundos, separador, titulo = entrada[len("#EXTINF:"):].partition(",")
    try:
        milisegundos = int(segundos.strip()) * 1000
    except ValueError:
        milisegundos = 0
    return (milisegundos if milisegundos > 0 else 0,
            titulo.strip() if separador else "")


class Biblioteca:
    """Índice de una carpeta de audio más lectura de listas de reproducción."""

    def __init__(self, carpeta, leer_etiquetas=None, cache=None):
        self._carpeta = carpeta
        self._leer_etiquetas = leer_etiquetas
        self._cache = cache
        self._lock = threading.Lock()
        self._temas: tuple[Tema, ...] = ()

    def indexar(self) -> int:
        """Recorre la carpeta una vez, guarda los temas y devuelve cuántos son."""
        base = Path(self._carpeta)
        if not base.is_dir():
            raise ErrorBiblioteca(f"La carpeta no existe o no es una carpeta: {base}")
        encontrados = []
        for raiz, subcarpetas, archivos in os.walk(base, followlinks=False):
            subcarpetas.sort(key=str.lower)
            for nombre in sorted(archivos, key=str.lower):
                ruta = Path(raiz) / nombre
                if ruta.suffix.lower() not in EXTENSIONES:
                    continue
                try:
                    encontrados.append(self._tema(ruta))
                except OSError:
                    continue
        encontrados.sort(key=lambda tema: tema.origen.lower())
        with self._lock:
            self._temas = tuple(encontrados)
        return len(self._temas)

    def temas(self) -> tuple[Tema, ...]:
        """El índice actual, vacío si todavía no se indexó."""
        with self._lock:
            return self._temas

    def pendientes(self) -> tuple[Tema, ...]:
        """Los temas del índice sin entrada válida en la caché, en orden.

        Sin caché, todos. Un tema vale si la caché tiene su origen con el
        `mtime_ns` y el tamaño actuales del archivo.
        """
        with self._lock:
            actuales = self._temas
        if self._cache is None:
            return actuales
        faltan = []
        for tema in actuales:
            if tema.es_enlace:
                continue
            try:
                info = os.stat(tema.origen)
            except OSError:
                faltan.append(tema)
                continue
            if self._cache.buscar(tema.origen, info.st_mtime_ns, info.st_size) is None:
                faltan.append(tema)
        return tuple(faltan)

    def actualizar(self, temas_nuevos) -> int:
        """Reemplaza en el índice los temas con el mismo `origen`.

        Ni el orden ni la cantidad cambian: lo que no está en el índice se
        ignora. Es lo que usa el hilo de etiquetas para poner al día lo ya
        indexado. Devuelve cuántos reemplazó.
        """
        mapa = {tema.origen: tema for tema in temas_nuevos}
        if not mapa:
            return 0
        with self._lock:
            nuevos = tuple(mapa.get(tema.origen, tema) for tema in self._temas)
            puestos = sum(1 for viejo, nuevo in zip(self._temas, nuevos)
                          if nuevo is not viejo)
            self._temas = nuevos
        return puestos

    def buscar(self, texto) -> tuple[Tema, ...]:
        """Busca en el índice por nombre, título, artista y álbum, sin tocar el disco."""
        if not texto or not texto.strip():
            return ()
        aguja = _plegar(texto)
        with self._lock:
            actuales = self._temas
        resultados = []
        for tema in actuales:
            campos = (
                _plegar(Path(tema.origen).name),
                _plegar(tema.titulo),
                _plegar(tema.artista),
                _plegar(tema.album),
            )
            if any(aguja in campo for campo in campos):
                resultados.append(tema)
        return tuple(resultados)

    def cargar_m3u8(self, ruta) -> tuple[tuple[Tema, ...], int]:
        """Lee una lista .m3u8 y devuelve los temas y cuántas líneas se saltaron."""
        archivo = Path(ruta)
        if archivo.suffix.lower() != ".m3u8" or not archivo.is_file():
            raise ErrorBiblioteca(f"La ruta no es una lista .m3u8: {archivo}")
        try:
            lineas = archivo.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError) as exc:
            raise ErrorBiblioteca(f"No se puede leer la lista: {exc}") from exc
        temas = []
        saltadas = 0
        pendiente = (0, "")
        for linea in lineas:
            entrada = linea.strip()
            if not entrada:
                continue
            if entrada.startswith("#EXTINF:"):
                pendiente = _leer_extinf(entrada)
                continue
            if entrada.startswith("#"):
                continue
            tema = self._tema_de_linea(archivo, entrada, pendiente)
            if tema is None:
                saltadas += 1
                pendiente = (0, "")
                continue
            temas.append(tema)
            pendiente = (0, "")
        return tuple(temas), saltadas

    def _tema_de_linea(self, archivo: Path, entrada: str,
                       pendiente: tuple) -> Tema | None:
        duracion_ms, titulo = pendiente
        if _URL_CON_ESQUEMA.match(entrada):
            if enlaces.es_enlace_youtube(entrada):
                return Tema(entrada, titulo or entrada, duracion_ms=duracion_ms)
            return None
        ruta = Path(entrada)
        if not ruta.is_absolute():
            ruta = archivo.parent / ruta
        if not ruta.is_file() or ruta.suffix.lower() not in EXTENSIONES:
            return None
        try:
            tema = self._tema(ruta)
        except OSError:
            return None
        duracion = duracion_ms or tema.duracion_ms
        return Tema(tema.origen, titulo or tema.titulo, tema.artista,
                    tema.album, duracion)

    def _tema(self, ruta: Path) -> Tema:
        titulo = artista = album = ""
        duracion_ms = 0
        if self._cache is not None:
            datos = self._etiquetas_de_cache(ruta)
            if isinstance(datos, dict):
                titulo = str(datos.get("titulo") or "")
                artista = str(datos.get("artista") or "")
                album = str(datos.get("album") or "")
                duracion_ms = normalizar_duracion(datos.get("duracion_ms"))
        if not titulo and self._leer_etiquetas is not None:
            # Sin mutagen, las etiquetas las va a leer libVLC en otro encargo.
            # Si el invocable falla, el tema no se pierde: cae al nombre del archivo.
            try:
                datos = self._leer_etiquetas(str(ruta))
            except Exception:
                datos = {}
            if isinstance(datos, dict):
                titulo = str(datos.get("titulo") or "")
                artista = str(datos.get("artista") or "")
                album = str(datos.get("album") or "")
                duracion_ms = normalizar_duracion(datos.get("duracion_ms"))
        if not titulo:
            titulo = ruta.stem
        return Tema(str(ruta.resolve()), titulo, artista, album, duracion_ms)

    def _etiquetas_de_cache(self, ruta: Path) -> dict | None:
        """Las etiquetas de la caché para ese archivo, o None si no valen.

        None si el archivo cambió, si no hay entrada o si no se pudo leer
        sus datos en disco. Nunca lanza.
        """
        try:
            info = ruta.stat()
            return self._cache.buscar(
                str(ruta.resolve()), info.st_mtime_ns, info.st_size)
        except OSError:
            return None
