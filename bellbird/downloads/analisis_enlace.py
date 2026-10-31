"""Pregunta a yt-dlp qué es un enlace, sin descargar.

Separa del gestor la inspección previa de la URL: tipo, identificador,
título y cantidad de entradas. Vive acá para que el gestor no crezca.
"""

from __future__ import annotations

import json
import subprocess

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.downloads import ytdlp_bin

logger = diagnostico.obtener_logger(__name__)

# Tope del análisis previo de la URL: sin él, una red caída dejaba el ítem
# «en cola» para siempre.
TIEMPO_ESPERA_ANALISIS = 60


def _error(mensaje: str) -> dict:
    return {"tipo": "error", "id": "", "titulo": "", "cuenta": 0,
            "mensaje": mensaje}


def analizar_url(url: str) -> dict:
    """Inspecciona una URL y devuelve tipo / id / título / cuenta.

    Pide los datos al programa independiente. Si no está disponible, devuelve
    el mismo error que se informaba cuando faltaba el módulo de Python.
    """
    ruta = ytdlp_bin.ruta_ytdlp()
    if ruta is None:
        return _error(_("yt-dlp no está instalado"))
    # -J (un único JSON) y --flat-playlist: --dump-json emitía un JSON por
    # entrada en las playlists y json.loads fallaba con «Extra data».
    try:
        resultado = subprocess.run(
            [ruta, *ytdlp_bin.argumentos_comunes(), "-J", "--flat-playlist",
             "--quiet", "--no-warnings", "--skip-download", "--no-playlist",
             "--socket-timeout", "20", url],
            capture_output=True, text=True, creationflags=_sin_ventana(),
            check=False, timeout=TIEMPO_ESPERA_ANALISIS,
        )
        if resultado.returncode:
            return _error(resultado.stderr.strip() or _("yt-dlp falló"))
        info = json.loads(resultado.stdout)
    except (OSError, subprocess.SubprocessError, TypeError, ValueError) as exc:
        logger.warning("analizar_url falló: %s", exc)
        return _error(str(exc))
    if not info:
        return _error(_("Enlace vacío"))
    if info.get("_type") == "playlist" or "entries" in info:
        return {"tipo": "playlist",
                "id": info.get("id", ""),
                "titulo": info.get("title", ""),
                "cuenta": len(info.get("entries") or [])}
    return {"tipo": "video",
            "id": info.get("id", ""),
            "titulo": info.get("title", ""),
            "cuenta": 1,
            "en_directo": bool(info.get("is_live"))}


def _sin_ventana() -> int:
    """Evita una ventana de consola en Windows al ejecutar yt-dlp."""
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)
