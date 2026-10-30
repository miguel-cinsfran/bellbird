"""Terminar un proceso de yt-dlp con sus hijos, sin dejar restos.

Razón del módulo: matar el árbol yt-dlp más ffmpeg en Windows y vigilar
la cancelación hasta que el proceso termina.
"""

from __future__ import annotations

import os
import subprocess

from bellbird.core import diagnostico
from bellbird.downloads.analisis_enlace import _sin_ventana

logger = diagnostico.obtener_logger(__name__)


def _matar_arbol(proceso) -> None:
    """Mata a yt-dlp Y a su ffmpeg hijo. En Windows kill() solo mata al
    padre: el ffmpeg que estaba uniendo audio y vídeo seguía vivo y escribiendo
    en la carpeta. taskkill /T baja el árbol entero; kill() queda de red."""
    pid = getattr(proceso, "pid", None)
    if os.name == "nt" and isinstance(pid, int):
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)],
                           capture_output=True, timeout=10, check=False,
                           creationflags=_sin_ventana())
        except Exception as exc:
            logger.debug("taskkill: %s", exc)
    try:
        proceso.kill()
    except Exception as exc:
        logger.debug("kill: %s", exc)


def _vigilar_cancelacion(proceso, cancel_event, intervalo=0.2) -> bool:
    while proceso.poll() is None:
        if cancel_event.wait(intervalo):
            _matar_arbol(proceso)
            return True
    return False
