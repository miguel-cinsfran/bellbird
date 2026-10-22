"""Argumentos de yt-dlp para descargar: formato, plantilla y línea de comandos.

Una sola responsabilidad: armar lo que se le pasa al programa independiente.
`descargas` las reexporta para que la GUI, las pruebas y quien las importe
desde `descargas` sigan iguales.
"""

from __future__ import annotations

from pathlib import Path

from ytchat.core import paths
from ytchat.downloads import ffmpeg_bin
from ytchat.downloads.progreso_ytdlp import PLANTILLA


def formato_a_ydl(formato: str, bitrate: int) -> str:
    """Selector que se pasa a YoutubeDL como `format`.

    mp4/webm piden el mejor stream de vídeo con esa extensión combinada con el
    mejor audio compatible, y caen a un fallback genérico si no hay.
    mp3/m4a piden solo el mejor audio y `descargar()` añade la conversión.
    """
    f = (formato or "").lower().strip()
    if f == "mp4":
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    if f == "webm":
        return "bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best"
    if f in ("mp3", "m4a"):
        return "bestaudio"
    return "best"


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
    from ytchat.downloads.descargas import PREFIJO_RUTA_FINAL
    f = (opciones.get("formato") or "mp4").lower().strip()
    bitrate = int(opciones.get("bitrate") or 192)
    # --print after_move: el nombre que llega por el progreso es el del
    # fragmento («….f140.m4a»); el definitivo solo se sabe tras unir o
    # convertir. --print implica --quiet, y --progress recupera el progreso.
    argumentos = ["--newline", "--no-warnings", "--progress",
                  "--progress-template", PLANTILLA,
                  "--print", f"after_move:{PREFIJO_RUTA_FINAL} %(filepath)s",
                  "-f", formato_a_ydl(f, bitrate), "-o",
                  construir_outtmpl(opciones, enumerar)]
    if f in ("mp3", "m4a"):
        argumentos.extend(["-x", "--audio-format", f,
                           "--audio-quality", f"{bitrate}K"])
    if ffmpeg_location is None:
        ffmpeg_location = ffmpeg_bin.ruta_ffmpeg()
    if ffmpeg_location is not None:
        argumentos.extend(["--ffmpeg-location", str(ffmpeg_location)])
    argumentos.extend(["--", url])
    return argumentos
