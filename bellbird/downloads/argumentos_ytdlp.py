"""Argumentos de yt-dlp para descargar: formato, plantilla y línea de comandos.

Una sola responsabilidad: armar lo que se le pasa al programa independiente.
`descargas` las reexporta para que la GUI, las pruebas y quien las importe
desde `descargas` sigan iguales.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bellbird.core import paths
from bellbird.downloads import ffmpeg_bin
from bellbird.downloads.opciones_formato import (
    PLANTILLAS, argumentos_de_formato, argumentos_exactos)
from bellbird.downloads.progreso_ytdlp import (
    PREFIJO_RUTA_FINAL, plantillas_progreso)


_PLANTILLA_POR_CLAVE = {clave: plantilla for _etiqueta, clave, plantilla in PLANTILLAS}


def carpeta_base(opciones: dict) -> Path:
    """Carpeta elegida en Preferencias o la de por defecto."""
    return Path(str(opciones.get("carpeta") or paths.descargas_por_defecto()))


def recortar_url_registro(url: str) -> str:
    """Devuelve el identificador de vídeo sin parámetros para el registro."""
    partes = urlparse(url)
    consulta = parse_qs(partes.query)
    if consulta.get("v"):
        return consulta["v"][0]
    segmentos = [segmento for segmento in partes.path.split("/") if segmento]
    if partes.netloc.lower().endswith("youtu.be") and segmentos:
        return segmentos[0]
    if len(segmentos) >= 2 and segmentos[0] in ("shorts", "embed", "live"):
        return segmentos[1]
    return segmentos[-1] if segmentos else "sin identificador"


def construir_outtmpl(opciones: dict, enumerar: bool) -> str:
    """Plantilla de nombre de archivo para yt-dlp.

    El directorio se pasa en `opciones["carpeta"]`; yt-dlp lo une con el nombre.
    Con `enumerar=True` yt-dlp prefijará «01 - », «02 - », etc. SOLO si el
    resultado es una playlist; en vídeos sueltos el prefijo no aparece (el
    condicional «&…|» de yt-dlp; un %(playlist_index)02d a secas daba «NA - »).
    Con `es_lista` y `carpeta_lista` a la vez, la lista va en una subcarpeta
    con su título; el vídeo suelto va directo en la carpeta de descargas.
    """
    base = carpeta_base(opciones)
    if opciones.get("es_lista") and opciones.get("carpeta_lista"):
        base = base / "%(playlist_title)s"
    plantilla = _PLANTILLA_POR_CLAVE.get(opciones.get("plantilla"), "%(title)s [%(id)s]")
    if enumerar:
        nombre = "%(playlist_index&{:02d} - |)s" + plantilla
    else:
        nombre = plantilla
    return str(base / (nombre + ".%(ext)s"))


def argumentos_limite(opciones: dict) -> list[str]:
    """Tope de velocidad para yt-dlp: `-r {limite}M` o nada con cero."""
    try:
        limite = int(opciones.get("limite") or 0)
    except Exception:
        return []
    if limite <= 0:
        return []
    return ["-r", f"{limite}M"]


def argumentos_de_la_opcion(formato, opciones, bitrate, resolucion) -> list[str]:
    """Args de formato: el exacto con su selector o el formato elegido.

    Con «exacto» se pide tal cual la opción elegida del vídeo; sin
    selector se trata como MP4, no revienta.
    """
    if formato == "exacto" and (opciones.get("selector") or "").strip():
        return argumentos_exactos(opciones["selector"],
                                  opciones.get("contenedor") or "")
    if formato == "exacto":
        formato = "mp4"
    return argumentos_de_formato(formato, bitrate, resolucion)


def argumentos_descarga(url, opciones, enumerar, ffmpeg_location=None) -> list[str]:
    """Arma los argumentos de una descarga, sin ejecutar programas."""
    f = (opciones.get("formato") or "mp4").lower().strip()
    bitrate = int(opciones.get("bitrate") or 192)
    resolucion = int(opciones.get("resolucion") or 0)
    # --print after_move: el nombre que llega por el progreso es el del
    # fragmento («….f140.m4a»); el definitivo solo se sabe tras unir o
    # convertir. --print implica --quiet, y --progress recupera el progreso.
    argumentos = ["--encoding", "utf-8", "--newline", "--no-warnings",
                  "--progress", *plantillas_progreso(),
                  "--print", f"after_move:{PREFIJO_RUTA_FINAL} %(filepath)s",
                  *argumentos_de_la_opcion(f, opciones, bitrate, resolucion),
                  "-o", construir_outtmpl(opciones, enumerar),
                  *argumentos_limite(opciones)]
    if ffmpeg_location is None:
        ffmpeg_location = ffmpeg_bin.ruta_ffmpeg()
    if ffmpeg_location is not None:
        argumentos.extend(["--ffmpeg-location", str(ffmpeg_location)])
    argumentos.extend(["--no-playlist", "--", url])
    return argumentos
