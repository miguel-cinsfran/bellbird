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
from bellbird.downloads.opciones_formato import argumentos_de_formato
from bellbird.downloads.progreso_ytdlp import plantillas_progreso


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
    """
    carpeta = str(opciones.get("carpeta") or paths.descargas_por_defecto())
    if enumerar:
        nombre = "%(playlist_index&{:02d} - |)s%(title)s [%(id)s].%(ext)s"
    else:
        nombre = "%(title)s [%(id)s].%(ext)s"
    return str(Path(carpeta) / nombre)


def argumentos_descarga(url, opciones, enumerar, ffmpeg_location=None) -> list[str]:
    """Arma los argumentos de una descarga, sin ejecutar programas."""
    from bellbird.downloads.descargas import PREFIJO_RUTA_FINAL
    f = (opciones.get("formato") or "mp4").lower().strip()
    bitrate = int(opciones.get("bitrate") or 192)
    resolucion = int(opciones.get("resolucion") or 0)
    # --print after_move: el nombre que llega por el progreso es el del
    # fragmento («….f140.m4a»); el definitivo solo se sabe tras unir o
    # convertir. --print implica --quiet, y --progress recupera el progreso.
    argumentos = ["--encoding", "utf-8", "--newline", "--no-warnings",
                  "--progress", *plantillas_progreso(),
                  "--print", f"after_move:{PREFIJO_RUTA_FINAL} %(filepath)s",
                  *argumentos_de_formato(f, bitrate, resolucion),
                  "-o", construir_outtmpl(opciones, enumerar)]
    if ffmpeg_location is None:
        ffmpeg_location = ffmpeg_bin.ruta_ffmpeg()
    if ffmpeg_location is not None:
        argumentos.extend(["--ffmpeg-location", str(ffmpeg_location)])
    argumentos.extend(["--no-playlist", "--", url])
    return argumentos
