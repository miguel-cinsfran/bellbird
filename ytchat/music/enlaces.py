"""Enlaces de YouTube para la cola de música.

Reconoce direcciones de vídeo o de lista, las expande a temas con yt-dlp en
modo plano y resuelve la dirección de audio de un vídeo cuando le toca sonar.
Sin wx. Las funciones que hablan con yt-dlp o con la red BLOQUEAN: se llaman
desde un hilo.
"""

from __future__ import annotations

import json
import re
import subprocess

from ytchat.core.idioma import N_, _
from ytchat.downloads import ytdlp_bin
from ytchat.music.modelo import Tema
from ytchat.player import formatos


TOPE_PROGRAMA = 60

_DOMINIOS_YOUTUBE = ("youtube.com", "youtu.be")

_ID_EN_URL = (
    re.compile(r"[?&]v=([A-Za-z0-9_-]+)"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]+)"),
    re.compile(r"/shorts/([A-Za-z0-9_-]+)"),
    re.compile(r"/embed/([A-Za-z0-9_-]+)"),
)


class ErrorEnlace(ValueError):
    """No se pudo leer el enlace o no tiene vídeos."""


TEXTO_NO_SE_PUDO_LEER = N_("No se pudo leer el enlace")
TEXTO_SIN_VIDEOS = N_("El enlace no tiene vídeos")


def _sin_esquema(texto: str) -> str:
    limpio = re.sub(r"^[A-Za-z][A-Za-z0-9+.-]*://", "", texto.strip())
    if limpio[:4].lower() == "www.":
        limpio = limpio[4:]
    return limpio


def _host(texto: str) -> str:
    return texto.split("/", 1)[0].split("?", 1)[0].split(":", 1)[0].lower()


def es_enlace_youtube(texto) -> bool:
    """¿La dirección es de un vídeo o de una lista de YouTube?

    Vale con o sin ``https://`` y ``www.``, para video, Shorts, youtu.be,
    music.youtube.com y cualquier dirección de YouTube con ``list=``.
    """
    if not isinstance(texto, str):
        return False
    texto = _sin_esquema(texto).lower()
    if not texto:
        return False
    host = _host(texto)
    if host == "youtu.be":
        pass
    elif host == "youtube.com" or host.endswith(".youtube.com"):
        pass
    else:
        return False
    if "list=" in texto:
        return True
    ruta = texto[len(host):]
    if host == "youtu.be":
        return len(ruta) > 1
    return ruta.startswith("/watch?v=") or ruta.startswith("/shorts/")


def id_de_url(origen) -> str:
    """Identificador del vídeo dentro de una dirección de YouTube, o ``""``."""
    if not isinstance(origen, str):
        return ""
    for patron in _ID_EN_URL:
        coincidencia = patron.search(origen)
        if coincidencia:
            return coincidencia.group(1)
    return ""


def _tema_de_entrada(entrada: dict) -> Tema | None:
    video_id = entrada.get("id")
    if not isinstance(video_id, str) or not video_id:
        return None
    titulo = str(entrada.get("title") or "").strip() or video_id
    return Tema(f"https://www.youtube.com/watch?v={video_id}", titulo)


def temas_de_info(datos) -> tuple[Tema, ...]:
    """Interpreta el JSON plano de yt-dlp: un vídeo suelto o una lista.

    Función pura. Las entradas sin id (privadas o borradas) se saltan.
    """
    if not isinstance(datos, dict):
        return ()
    entradas = datos.get("entries")
    if entradas is None:
        tema = _tema_de_entrada(datos)
        return (tema,) if tema is not None else ()
    temas = []
    for entrada in entradas:
        if not isinstance(entrada, dict):
            continue
        tema = _tema_de_entrada(entrada)
        if tema is not None:
            temas.append(tema)
    return tuple(temas)


def _extraer_plano_con_programa(ruta: str, url: str) -> dict:
    argumentos = [ruta, "--flat-playlist", "-J", "--no-warnings", url]
    try:
        resultado = subprocess.run(
            argumentos, capture_output=True, text=True, timeout=TOPE_PROGRAMA,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ErrorEnlace(_(TEXTO_NO_SE_PUDO_LEER)) from exc
    if resultado.returncode:
        raise ErrorEnlace(_(TEXTO_NO_SE_PUDO_LEER))
    try:
        return json.loads(resultado.stdout)
    except (TypeError, ValueError) as exc:
        raise ErrorEnlace(_(TEXTO_NO_SE_PUDO_LEER)) from exc


def _extraer_plano_con_modulo(url: str) -> dict:
    import yt_dlp
    opciones = {
        "quiet": True, "no_warnings": True, "skip_download": True,
        "extract_flat": "in_playlist", "socket_timeout": 20,
    }
    try:
        with yt_dlp.YoutubeDL(opciones) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as exc:
        raise ErrorEnlace(_(TEXTO_NO_SE_PUDO_LEER)) from exc


def _info_plano(url: str) -> dict:
    ruta = ytdlp_bin.ruta_ytdlp()
    if ruta is not None:
        return _extraer_plano_con_programa(ruta, url)
    return _extraer_plano_con_modulo(url)


def expandir(url: str) -> tuple[Tema, ...]:
    """Los temas de la dirección: uno si es un vídeo, uno por entrada si es
    una lista, en orden, con su título. Bloqueante (usar en hilo)."""
    temas = temas_de_info(_info_plano(url))
    if not temas:
        raise ErrorEnlace(_(TEXTO_SIN_VIDEOS))
    return temas


def _extraer_video_con_modulo(video_id: str) -> dict:
    import yt_dlp
    opciones = {
        "quiet": True, "no_warnings": True, "skip_download": True,
        "noplaylist": True, "socket_timeout": 20,
    }
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(opciones) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as exc:
        raise ErrorEnlace(_(TEXTO_NO_SE_PUDO_LEER)) from exc


def _info_video(video_id: str) -> dict:
    if ytdlp_bin.ruta_ytdlp() is not None:
        info = ytdlp_bin.info_video(video_id)
        if info is None:
            raise ErrorEnlace(_(TEXTO_NO_SE_PUDO_LEER))
        return info
    return _extraer_video_con_modulo(video_id)


def url_audio(origen: str) -> str:
    """Dirección del audio para reproducir ese vídeo ahora. Vence: no se
    guarda. Bloqueante (usar en hilo). Lanza `ErrorEnlace` si no hay audio."""
    video_id = id_de_url(origen)
    if not video_id:
        raise ErrorEnlace(_(TEXTO_NO_SE_PUDO_LEER))
    url = formatos.mejor_audio(_info_video(video_id))
    if not url:
        raise ErrorEnlace(_(TEXTO_NO_SE_PUDO_LEER))
    return url
