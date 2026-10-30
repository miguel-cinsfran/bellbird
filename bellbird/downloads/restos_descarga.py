"""Reconoce y borra los restos que deja una descarga cancelada."""

from __future__ import annotations

import re
from pathlib import Path

from bellbird.core import diagnostico

logger = diagnostico.obtener_logger(__name__)

# Sufijo de fragmento DASH que deja yt-dlp: «.f140.m4a», «.f137.mp4.part»…
_RE_FRAGMENTO = re.compile(r"^\.f[\w-]+\.[A-Za-z0-9]+(\.part|\.ytdl)?$")


def nombre_base_descarga(nombre_archivo: str) -> str:
    """«Título [id].f140.m4a.part» → «Título [id]»: lo que comparten todos
    los archivos (fragmentos, .part, .ytdl) de una misma descarga."""
    nombre = Path(nombre_archivo).name
    for sufijo in (".part", ".ytdl"):
        if nombre.endswith(sufijo):
            nombre = nombre[: -len(sufijo)]
    fragmento = re.search(r"\.f[\w-]+\.[A-Za-z0-9]+$", nombre)
    if fragmento:
        return nombre[: fragmento.start()]
    return Path(nombre).stem


def limpiar_restos_descarga(carpeta, nombre_archivo: str) -> list[str]:
    """Borra lo que una descarga cancelada deja en su carpeta.

    Conservador a propósito: solo archivos de ESA carpeta cuyo nombre empiece
    por el nombre base de la descarga y sean claramente temporales (.part,
    .ytdl o un fragmento .fNNN.ext). Un archivo ya terminado no se toca.
    Devuelve los nombres borrados.
    """
    base = nombre_base_descarga(nombre_archivo) if nombre_archivo else ""
    if not base:
        return []
    borrados = []
    try:
        entradas = list(Path(carpeta).iterdir())
    except OSError:
        return []
    for ruta in entradas:
        nombre = ruta.name
        if not nombre.startswith(base) or not ruta.is_file():
            continue
        resto = nombre[len(base):]
        if not (resto.endswith(".part") or resto.endswith(".ytdl") or _RE_FRAGMENTO.match(resto)):
            continue
        try:
            ruta.unlink()
            borrados.append(nombre)
        except OSError as exc:
            logger.debug("no se pudo borrar %s: %s", nombre, exc)
    return borrados
