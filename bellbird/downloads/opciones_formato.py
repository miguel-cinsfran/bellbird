"""Qué opciones de descarga existen: formatos, calidades, plantillas y topes.

Una sola responsabilidad: qué formatos existen, qué calidad admite cada
uno y con qué opciones de yt-dlp se piden. Lo usan la GUI, la
configuración y los argumentos.
"""

from __future__ import annotations

from bellbird.core.idioma import N_, _


FORMATOS = (
    (N_("Vídeo original"), "video_original"),
    (N_("Vídeo MP4"), "mp4"),
    (N_("Vídeo WebM"), "webm"),
    (N_("Audio original"), "audio_original"),
    (N_("Audio MP3"), "mp3"),
    (N_("Audio M4A"), "m4a"),
    (N_("Audio Opus"), "opus"),
    (N_("Audio FLAC"), "flac"),
    (N_("Audio WAV"), "wav"),
)

RESOLUCIONES = (0, 2160, 1440, 1080, 720, 480, 360)
BITRATES = (128, 192, 256, 320)

PLANTILLAS = (
    (N_("Título e identificador"), "titulo_id", "%(title)s [%(id)s]"),
    (N_("Título"), "titulo", "%(title)s"),
    (N_("Canal y título"), "canal_titulo", "%(uploader)s - %(title)s"),
    (N_("Fecha y título"), "fecha_titulo", "%(upload_date>%Y-%m-%d)s - %(title)s"),
)

SIMULTANEAS_MIN = 1
SIMULTANEAS_MAX = 5
# Dos a la vez: la PC que usa la app tiene cuatro núcleos y 7,83 GiB,
# y diez yt-dlp a la vez la dejan sin resto.
SIMULTANEAS_DEFECTO = 2
LIMITE_MAX = 1000

_FORMATOS_VIDEO = ("video_original", "mp4", "webm")
_FORMATOS_BITRATE = ("mp3", "m4a", "opus")


def clase_de_calidad(formato: str) -> str:
    """Qué desplegable Calidad muestra cada formato."""
    f = (formato or "").lower().strip()
    if f in _FORMATOS_VIDEO:
        return "resolucion"
    if f in _FORMATOS_BITRATE:
        return "bitrate"
    return ""


def etiquetas_de_calidad(formato: str) -> list[str]:
    """Lo que muestra el desplegable Calidad para cada formato."""
    clase = clase_de_calidad(formato)
    if clase == "resolucion":
        return [_("Máxima")] + [f"{r}p" for r in RESOLUCIONES if r]
    if clase == "bitrate":
        return [f"{b} kbps" for b in BITRATES]
    return []


def argumentos_exactos(selector: str, contenedor: str) -> list[str]:
    """Opciones de yt-dlp para una opción exacta elegida de un vídeo.

    El selector une dos formatos con «+» o trae los dos en uno solo.
    `--embed-thumbnail` solo donde va bien: con MP4 o M4A, nunca con
    WebM ni Opus. Con Opus, `-x` deja el `.opus` sin convertir.
    """
    cont = (contenedor or "").lower().strip()
    args = ["-f", selector]
    if cont == "opus":
        args += ["-x"]
    if "+" in selector:
        args += ["--merge-output-format", cont]
    args += ["--embed-metadata"]
    if cont in ("mp4", "m4a"):
        args += ["--embed-thumbnail"]
    return args


def transitorias_de(formato) -> dict:
    """Lo transitorio para descargar con ese formato sin mover lo elegido.

    «audio» y «video» dan su formato guardable; un diccionario (el de una
    opción exacta elegida) se devuelve igual.
    """
    if isinstance(formato, dict):
        return formato
    if formato == "audio":
        return {"formato": "audio_original"}
    if formato == "video":
        return {"formato": "mp4"}
    return {"formato": formato or "mp4"}


def _normalizar(formato: str) -> str:
    f = (formato or "").lower().strip()
    if f in ("video_original", "mp4", "webm", "audio_original", "mp3",
             "m4a", "opus", "flac", "wav"):
        return f
    return "mp4"


def argumentos_de_formato(formato: str, bitrate: int, resolucion: int) -> list[str]:
    """Opciones de yt-dlp para un formato, con metadatos y portada."""
    f = _normalizar(formato)
    try:
        b = int(bitrate)
    except Exception:
        b = 192
    try:
        r = int(resolucion)
    except Exception:
        r = 0
    if f == "video_original":
        args = ["-f", "bv*+ba/b"]
        if r:
            args += ["-S", f"res:{r}"]
        return args + ["--embed-metadata"]
    if f == "mp4":
        orden = "vcodec:h264,acodec:aac,ext:mp4"
        if r:
            orden = f"res:{r}," + orden
        return ["-f", "bv*+ba/b", "-S", orden,
                "--merge-output-format", "mp4",
                "--embed-thumbnail", "--embed-metadata"]
    if f == "webm":
        args = ["-f", "bv*[ext=webm]+ba[ext=webm]/b[ext=webm]/b",
                "--merge-output-format", "webm"]
        if r:
            args += ["-S", f"res:{r}"]
        return args + ["--embed-metadata"]
    if f == "audio_original":
        return ["-f", "ba/b", "-x",
                "--embed-thumbnail", "--embed-metadata"]
    if f in ("mp3", "m4a", "opus"):
        return ["-f", "ba/b", "-x", "--audio-format", f,
                "--audio-quality", f"{b}K",
                "--embed-thumbnail", "--embed-metadata"]
    if f == "flac":
        return ["-f", "ba/b", "-x", "--audio-format", "flac",
                "--embed-thumbnail", "--embed-metadata"]
    return ["-f", "ba/b", "-x", "--audio-format", "wav",
            "--embed-metadata"]
