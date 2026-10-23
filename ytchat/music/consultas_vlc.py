"""Consultas a libVLC fuera de la reproducción: salidas y etiquetas.

Responde cómo se le pregunta a libVLC por los dispositivos de salida y por
las etiquetas de un archivo. Sin ``wx``: la lista de salidas se pide desde un
hilo aparte y las etiquetas desde el hilo que indexa la biblioteca.
"""

from __future__ import annotations

import os
import threading

from ytchat.core import diagnostico
from ytchat.music import modelo
from ytchat.player import motor_vlc


logger = diagnostico.obtener_logger(__name__)


def salidas_audio() -> list[tuple[str, str]]:
    """Dispositivos de salida de libVLC como pares (identificador, descripción).

    Usa un reproductor temporal de la instancia compartida y libera la lista y
    el reproductor. Nunca lanza: sin motor o ante un error devuelve lista
    vacía. Es bloqueante, la interfaz la llama desde un hilo aparte.
    """
    instancia = motor_vlc.instancia()
    vlc = motor_vlc.modulo()
    if instancia is None or vlc is None:
        return []
    reproductor = None
    lista = None
    try:
        reproductor = instancia.media_player_new()
        if reproductor is None:
            return []
        lista = reproductor.audio_output_device_enum()
        salidas = []
        nodo = lista
        while nodo:
            datos = nodo.contents
            salidas.append((_texto(datos.device), _texto(datos.description)))
            nodo = datos.next
        return salidas
    except Exception as exc:
        logger.debug("No se pudieron listar las salidas de audio: %s", exc)
        return []
    finally:
        if lista is not None:
            try:
                vlc.libvlc_audio_output_device_list_release(lista)
            except Exception as exc:
                logger.debug("No se pudo liberar la lista de salidas de audio: %s", exc)
        if reproductor is not None:
            try:
                reproductor.release()
            except Exception as exc:
                logger.debug("No se pudo liberar el reproductor temporal: %s", exc)


def _texto(valor) -> str:
    """Campo de texto de libVLC, que puede llegar en bytes o None."""
    if isinstance(valor, bytes):
        return valor.decode("utf-8", "replace")
    return valor or ""


def leer_etiquetas_vlc(ruta, plazo_ms=1500) -> dict:
    """Lee título, artista, álbum y duración de un archivo con libVLC.

    Nunca lanza: devuelve ``{}`` sin motor, si falla o al vencer el plazo. Se
    llama desde el hilo que indexa, nunca desde un callback de VLC.
    """
    instancia, vlc = motor_vlc.instancia(), motor_vlc.modulo()
    if instancia is None or vlc is None:
        return {}
    try:
        media = instancia.media_new(ruta)
    except Exception:
        return {}
    if media is None:
        return {}
    try:
        listo = threading.Event()

        def al_parsear(_evento):
            listo.set()
        try:
            gestor = media.event_manager()
            gestor.event_attach(vlc.EventType.MediaParsedChanged, al_parsear)
        except Exception as exc:
            logger.debug("No se pudo escuchar el fin del parseo de etiquetas: %s", exc)
        if media.parse_with_options(vlc.MediaParseFlag.local, plazo_ms) == -1:
            return {}
        if not listo.wait(plazo_ms / 1000):
            return {}
        titulo = media.get_meta(vlc.Meta.Title)
        artista = media.get_meta(vlc.Meta.Artist)
        album = media.get_meta(vlc.Meta.Album)
        duracion = modelo.normalizar_duracion(media.get_duration())
    except Exception:
        return {}
    finally:
        try:
            media.release()
        except Exception as exc:
            logger.debug("No se pudo liberar el medio de etiquetas: %s", exc)
    return {
        "titulo": _titulo_real(titulo, ruta),
        "artista": artista or "",
        "album": album or "",
        "duracion_ms": duracion,
    }


def _titulo_real(titulo, ruta):
    """Descarta el título cuando libVLC repite el nombre del archivo."""
    if not titulo:
        return ""
    nombre = os.path.basename(ruta)
    raiz = os.path.splitext(nombre)[0]
    if titulo.casefold() in (nombre.casefold(), raiz.casefold()):
        return ""
    return titulo
