"""Índice en memoria de una carpeta de audio y lectura de listas .m3u8."""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

from ytchat.music import enlaces
from ytchat.music.modelo import Tema


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


class Biblioteca:
    """Índice de una carpeta de audio más lectura de listas de reproducción."""

    def __init__(self, carpeta, leer_etiquetas=None):
        self._carpeta = carpeta
        self._leer_etiquetas = leer_etiquetas
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
        self._temas = tuple(encontrados)
        return len(self._temas)

    def temas(self) -> tuple[Tema, ...]:
        """El índice actual, vacío si todavía no se indexó."""
        return self._temas

    def buscar(self, texto) -> tuple[Tema, ...]:
        """Busca en el índice por nombre, título, artista y álbum, sin tocar el disco."""
        if not texto or not texto.strip():
            return ()
        aguja = _plegar(texto)
        resultados = []
        for tema in self._temas:
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
        titulo_pendiente = ""
        for linea in lineas:
            entrada = linea.strip()
            if not entrada:
                continue
            if entrada.startswith("#EXTINF:"):
                titulo_pendiente = entrada.split(",", 1)[1].strip() if "," in entrada else ""
                continue
            if entrada.startswith("#"):
                continue
            tema = self._tema_de_linea(archivo, entrada, titulo_pendiente)
            if tema is None:
                saltadas += 1
                titulo_pendiente = ""
                continue
            temas.append(tema)
            titulo_pendiente = ""
        return tuple(temas), saltadas

    def _tema_de_linea(self, archivo: Path, entrada: str, titulo: str) -> Tema | None:
        if _URL_CON_ESQUEMA.match(entrada):
            if enlaces.es_enlace_youtube(entrada):
                return Tema(entrada, titulo or entrada)
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
        if titulo:
            tema = Tema(tema.origen, titulo, tema.artista, tema.album)
        return tema

    def _tema(self, ruta: Path) -> Tema:
        titulo = artista = album = ""
        if self._leer_etiquetas is not None:
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
        if not titulo:
            titulo = ruta.stem
        return Tema(str(ruta.resolve()), titulo, artista, album)
