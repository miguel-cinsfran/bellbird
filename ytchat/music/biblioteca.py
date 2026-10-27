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
    ".aiff", ".aif", ".mka", ".webm",
}

_URL_CON_ESQUEMA = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


class ErrorBiblioteca(ValueError):
    """Carpeta, lista o entrada de lista inválida."""


def _plegar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar búsquedas."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return sin_tildes.casefold()


def _fecha_de_llegada(ruta: Path) -> int:
    """Cuándo llegó el archivo a la carpeta; 0 si no se puede leer."""
    try:
        return ruta.stat().st_ctime_ns
    except OSError:
        return 0


_PALABRAS = re.compile(r"[^\W_]+")


def coincide_por_palabras(texto, campos) -> bool:
    """Si cada palabra buscada es el comienzo de alguna palabra de los campos.

    Las palabras se separan por todo lo que no sea letra o número, así
    «ac/dc» busca «ac» y «dc». Sin palabras buscadas coincide todo.
    """
    buscadas = _PALABRAS.findall(_plegar(str(texto or "")))
    if not buscadas:
        return True
    palabras = []
    for campo in campos:
        palabras.extend(_PALABRAS.findall(_plegar(str(campo or ""))))
    return all(any(palabra.startswith(buscada) for palabra in palabras)
               for buscada in buscadas)


def _nombre_de_faltante(entrada: str, titulo: str) -> str:
    """El nombre que se anuncia de una entrada que no se pudo cargar."""
    if titulo:
        return titulo
    nombre = Path(entrada).stem
    return nombre or entrada


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
        encontrados = self._recorrer()
        with self._lock:
            self._temas = tuple(encontrados)
        return len(self._temas)

    def _recorrer(self) -> list:
        """Los temas de la carpeta, ordenados, sin guardarlos en el índice."""
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
        return encontrados

    def aplicar_cambios(self, agregadas, quitadas) -> tuple[int, int]:
        """Pone al día el índice con rutas de archivo, sin recorrer la carpeta.

        Quita todo tema cuyo `origen` sea una quitada o esté debajo de una
        carpeta quitada; agrega (o reemplaza si ya estaba) cada agregada que
        exista, sea archivo y tenga extensión de `EXTENSIONES`, armada con
        `_tema`. Deja el índice ordenado como `indexar`. Con el lock, como
        `actualizar`. Compara sin distinguir mayúsculas. Devuelve cuántos
        temas agregó (los nuevos, no los reemplazos) y cuántos quitó.
        """
        with self._lock:
            kept, quitados = self._quitar_rutas(tuple(self._temas), quitadas)
            nuevos = self._sumar_rutas(kept, agregadas)
            kept.sort(key=lambda tema: tema.origen.lower())
            self._temas = tuple(kept)
            return nuevos, quitados

    def _quitar_rutas(self, temas, quitadas) -> tuple[list, int]:
        """Saca los temas bajo una quitada. Sin el lock: lo llama quien lo tiene."""
        claves = {os.path.normcase(os.path.realpath(str(q)))
                  for q in quitadas}

        def _quitada(origen: str) -> bool:
            return any(origen == q or origen.startswith(q + os.sep)
                       for q in claves)

        kept = [t for t in temas
                if not _quitada(os.path.normcase(t.origen))]
        return kept, len(temas) - len(kept)

    def _sumar_rutas(self, kept, agregadas) -> int:
        """Agrega o reemplaza temas en la lista. Sin el lock: lo llama quien lo tiene."""
        posiciones = {os.path.normcase(t.origen): i
                      for i, t in enumerate(kept)}
        nuevos = 0
        for ruta in agregadas:
            camino = Path(ruta)
            if camino.suffix.lower() not in EXTENSIONES:
                continue
            try:
                if not camino.is_file():
                    continue
                tema = self._tema(camino)
            except OSError:
                continue
            clave = os.path.normcase(tema.origen)
            if clave in posiciones:
                kept[posiciones[clave]] = tema
            else:
                posiciones[clave] = len(kept)
                kept.append(tema)
                nuevos += 1
        return nuevos

    def reexaminar(self) -> tuple[int, int]:
        """Vuelve a recorrer la carpeta y deja el índice al día.

        Como `indexar`, y devuelve (nuevas, quitadas) comparando con el
        índice anterior, sin distinguir mayúsculas. Sin la carpeta, lanza
        `ErrorBiblioteca` como `indexar`.
        """
        nuevos = self._recorrer()
        claves_nuevas = {os.path.normcase(t.origen) for t in nuevos}
        with self._lock:
            claves_viejas = {os.path.normcase(t.origen) for t in self._temas}
            nuevas = [t for t in nuevos
                      if os.path.normcase(t.origen) not in claves_viejas]
            quitadas = sum(1 for clave in claves_viejas
                           if clave not in claves_nuevas)
            self._temas = tuple(nuevos)
        return len(nuevas), quitadas

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
        with self._lock:
            actuales = self._temas
        resultados = []
        for tema in actuales:
            campos = (
                Path(tema.origen).stem,
                tema.titulo,
                tema.artista,
                tema.album,
            )
            if coincide_por_palabras(texto, campos):
                resultados.append(tema)
        return tuple(resultados)

    def cargar_m3u8(self, ruta) -> tuple[tuple[Tema, ...], tuple[str, ...]]:
        """Lee una lista .m3u8 y devuelve los temas y los nombres que faltan."""
        archivo = Path(ruta)
        if archivo.suffix.lower() != ".m3u8" or not archivo.is_file():
            raise ErrorBiblioteca(f"La ruta no es una lista .m3u8: {archivo}")
        try:
            lineas = archivo.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError) as exc:
            raise ErrorBiblioteca(f"No se puede leer la lista: {exc}") from exc
        temas = []
        faltantes = []
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
                faltantes.append(_nombre_de_faltante(entrada, pendiente[1]))
                pendiente = (0, "")
                continue
            temas.append(tema)
            pendiente = (0, "")
        return tuple(temas), tuple(faltantes)

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
            # Lector opcional: la app lee las etiquetas con libVLC desde musica_indice.
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
        return Tema(str(ruta.resolve()), titulo, artista, album, duracion_ms,
                    _fecha_de_llegada(ruta))

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
