"""Caché en disco de las etiquetas de la música local, sin interfaz.

La música local se indexa solo por nombre de archivo, que es instantáneo, y
un hilo en segundo plano lee después las etiquetas con libVLC. Esta caché
guarda lo ya leído para que la segunda vez todo salga con etiquetas desde el
principio. Módulo puro, sin wx ni VLC, para poder probarlo solo.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from bellbird.core import archivos
from bellbird.core import diagnostico
from bellbird.music.modelo import normalizar_duracion

logger = diagnostico.obtener_logger(__name__)

VERSION = 2


class CacheEtiquetas:
    """Etiquetas ya leídas, en memoria y en un JSON en disco.

    La clave es el `origen` del tema (la ruta resuelta, como la da
    `Biblioteca._tema`). Cada entrada guarda `mtime_ns` y `tamano`: si el
    archivo cambió, la entrada no vale y hay que releerlo. Un archivo leído
    y sin etiquetas también se guarda, para no releerlo cada vez, siempre
    que traiga duración mayor que cero: una entrada con duración 0 es una
    lectura fallida y no vale.
    """

    def __init__(self, ruta):
        self._ruta = Path(ruta)
        self._lock = threading.Lock()
        self._datos: dict[str, dict] = {}
        self._cargar()

    def buscar(self, origen, mtime_ns, tamano) -> dict | None:
        """Las etiquetas de ese archivo, o None si no hay entrada válida.

        Solo vale si `mtime_ns` y `tamano` coinciden con lo guardado: si el
        archivo cambió, None aunque la ruta sea la misma. Una entrada con
        duración 0 es una lectura fallida y da None, para releerla.
        """
        with self._lock:
            entrada = self._datos.get(origen)
            if entrada is None:
                return None
            if entrada.get("mtime_ns") != mtime_ns or entrada.get("tamano") != tamano:
                return None
            duracion = normalizar_duracion(entrada.get("duracion_ms"))
            if duracion <= 0:
                return None
            return {
                "titulo": entrada.get("titulo", ""),
                "artista": entrada.get("artista", ""),
                "album": entrada.get("album", ""),
                "duracion_ms": duracion,
            }

    def poner(self, origen, mtime_ns, tamano, datos) -> None:
        """Guarda en memoria las etiquetas de ese archivo.

        Un `datos` vacío también se guarda: es un archivo ya leído y sin
        etiquetas, y no se vuelve a leer cada vez.
        """
        if not isinstance(datos, dict):
            datos = {}
        entrada = {
            "mtime_ns": mtime_ns,
            "tamano": tamano,
            "titulo": str(datos.get("titulo") or ""),
            "artista": str(datos.get("artista") or ""),
            "album": str(datos.get("album") or ""),
            "duracion_ms": normalizar_duracion(datos.get("duracion_ms")),
        }
        with self._lock:
            self._datos[origen] = entrada

    def guardar(self) -> bool:
        """Escribe la caché en disco, de forma atómica. Nunca lanza.

        Crea la carpeta si falta y descarta las entradas cuyo archivo ya no
        existe. Devuelve verdadero si se guardó, falso si no se pudo.
        """
        try:
            with self._lock:
                vigentes = {
                    origen: dict(entrada)
                    for origen, entrada in self._datos.items()
                    if os.path.exists(origen)
                }
                self._datos = vigentes
                contenido = {"version": VERSION, "etiquetas": vigentes}
            ruta = Path(self._ruta)
            ruta.parent.mkdir(parents=True, exist_ok=True)
            archivos.escribir_json_atomico(ruta, contenido)
        except Exception as exc:
            logger.debug("No se pudo guardar la caché de etiquetas: %s", exc)
            return False
        return True

    def _cargar(self) -> None:
        """Lee el JSON a memoria. Un archivo ausente, vacío, corrupto o con
        forma inesperada deja la caché vacía, sin lanzar."""
        try:
            texto = Path(self._ruta).read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        except OSError as exc:
            logger.debug("No se pudo leer la caché de etiquetas: %s", exc)
            return
        if not texto.strip():
            return
        try:
            crudo = json.loads(texto)
        except ValueError as exc:
            logger.debug("No se pudo leer la caché de etiquetas: %s", exc)
            return
        if not isinstance(crudo, dict) or crudo.get("version") != VERSION:
            logger.debug("No se pudo leer la caché de etiquetas: forma inesperada")
            return
        etiquetas = crudo.get("etiquetas")
        if not isinstance(etiquetas, dict):
            logger.debug("No se pudo leer la caché de etiquetas: forma inesperada")
            return
        datos = {}
        for origen, entrada in etiquetas.items():
            normalizada = self._entrada_valida(origen, entrada)
            if normalizada is not None:
                datos[origen] = normalizada
        with self._lock:
            self._datos = datos

    @staticmethod
    def _entrada_valida(origen, entrada) -> dict | None:
        """La entrada normalizada, o None si no sirve."""
        if not isinstance(origen, str) or not origen:
            return None
        if not isinstance(entrada, dict):
            return None
        mtime_ns = entrada.get("mtime_ns")
        tamano = entrada.get("tamano")
        if (isinstance(mtime_ns, bool) or not isinstance(mtime_ns, int)
                or isinstance(tamano, bool) or not isinstance(tamano, int)):
            return None
        return {
            "mtime_ns": mtime_ns,
            "tamano": tamano,
            "titulo": entrada.get("titulo") if isinstance(entrada.get("titulo"), str) else "",
            "artista": entrada.get("artista") if isinstance(entrada.get("artista"), str) else "",
            "album": entrada.get("album") if isinstance(entrada.get("album"), str) else "",
            "duracion_ms": normalizar_duracion(entrada.get("duracion_ms")),
        }


def _trae_duracion(datos) -> bool:
    """Verdadero si `datos` trae duración mayor que cero."""
    return isinstance(datos, dict) and normalizar_duracion(datos.get("duracion_ms")) > 0


def leer_con_reintento(leer, ruta) -> dict:
    """Lee las etiquetas con un reintento ante un fallo.

    Llama a `leer(ruta)`; si lo que vuelve no trae duración mayor que
    cero, llama otra vez con `leer(ruta, plazo_ms=5000)`. Si alguna trae
    duración, devuelve esa. Si ninguna trae duración, devuelve lo leído
    para mostrarlo: la segunda si no está vacía y, si no, la primera
    (o `{}` si las dos están vacías). Lo leído sin duración no se guarda
    en la caché y se vuelve a leer en la próxima apertura.
    """
    primero = leer(ruta)
    if _trae_duracion(primero):
        return primero
    segundo = leer(ruta, plazo_ms=5000)
    if _trae_duracion(segundo):
        return segundo
    if isinstance(segundo, dict) and segundo:
        return segundo
    if isinstance(primero, dict):
        return primero
    return {}
