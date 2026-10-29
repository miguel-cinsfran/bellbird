"""Memoria de la música: la cola y el tema donde quedó, para retomar.

Módulo puro, sin wx ni VLC. Guarda un JSON con la cola y la posición, y lo
lee de vuelta corrigiendo lo que ya no sirve: los temas que eran archivos y
se borraron se quitan, y la posición se acomoda al tema que sigue sonando.
Nunca lanza: un fallo se registra y se sigue sin memoria.
"""

from __future__ import annotations

import os
from pathlib import Path

from bellbird.core import archivos
from bellbird.core import diagnostico
from bellbird.music.modelo import Tema

logger = diagnostico.obtener_logger(__name__)

VERSION = 1


def guardar(ruta, estado) -> None:
    """Guarda la cola y la posición. Sin cola o sin posición, borra el archivo.

    Sin cola no hay nada que retomar: dejar el archivo viejo retomaría algo
    que el usuario ya no tiene. Nunca lanza.
    """
    try:
        ruta = Path(ruta)
        if estado is None or not estado.cola or estado.posicion is None:
            _borrar(ruta)
            return
        datos = {
            "version": VERSION,
            "temas": [{"origen": t.origen, "titulo": t.titulo,
                       "artista": t.artista, "album": t.album}
                      for t in estado.cola],
            "posicion": estado.posicion,
        }
        archivos.escribir_json_atomico(ruta, datos)
    except Exception:
        logger.exception("No se pudo guardar la memoria de la música")


def leer(ruta):
    """Devuelve ``(temas, posicion)`` o None si no hay nada que retomar.

    None si falta el archivo, si no se puede leer como JSON, si la versión no
    es la esperada, si no hay temas o si la posición no es un índice válido.
    Quita los temas que eran archivos y ya no existen; la posición se corrige
    al mismo tema si sigue, o a 0 si no. Nunca lanza.
    """
    try:
        ruta = Path(ruta)
        datos = archivos.leer_json(ruta, None)
        if not isinstance(datos, dict) or datos.get("version") != VERSION:
            return None
        crudos = datos.get("temas")
        posicion = datos.get("posicion")
        if (not isinstance(crudos, list) or not crudos
                or isinstance(posicion, bool) or not isinstance(posicion, int)
                or not 0 <= posicion < len(crudos)):
            return None
        vivos: list[Tema] = []
        indice_posicion = None
        for i, item in enumerate(crudos):
            tema = _tema_de(item)
            if tema is None or not _disponible(tema):
                continue
            if i == posicion:
                indice_posicion = len(vivos)
            vivos.append(tema)
        if not vivos:
            return None
        return tuple(vivos), (indice_posicion if indice_posicion is not None else 0)
    except Exception:
        logger.exception("No se pudo leer la memoria de la música")
        return None


def _tema_de(item):
    """Un Tema a partir de una entrada del JSON, o None si no sirve."""
    if not isinstance(item, dict):
        return None
    origen = item.get("origen")
    if not isinstance(origen, str) or not origen:
        return None
    return Tema(origen, _texto(item.get("titulo")),
                _texto(item.get("artista")), _texto(item.get("album")))


def _texto(valor) -> str:
    return valor if isinstance(valor, str) else ""


def _disponible(tema: Tema) -> bool:
    """Un tema sirve si es un enlace o si su archivo sigue existiendo."""
    return tema.es_enlace or os.path.exists(tema.origen)


def _borrar(ruta: Path) -> None:
    try:
        ruta.unlink()
    except FileNotFoundError:
        pass
