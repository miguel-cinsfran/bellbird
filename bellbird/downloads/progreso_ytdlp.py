"""Analiza el progreso textual emitido por el programa yt-dlp."""

from __future__ import annotations

import time
from pathlib import Path

PREFIJO = "PROG"
PLANTILLA = (
    "download:PROG %(progress.downloaded_bytes)s "
    "%(progress.total_bytes)s %(progress.total_bytes_estimate)s "
    "%(progress.speed)s %(progress.eta)s %(progress.filename)s"
)
PLANTILLA_DESCARGA = (
    "download:PROGD %(progress.downloaded_bytes)s "
    "%(progress.total_bytes)s %(progress.total_bytes_estimate)s "
    "%(progress.speed)s %(progress.eta)s "
    "%(info.playlist_autonumber)s %(info.n_entries)s "
    "%(progress.filename)s"
)
PLANTILLA_PROCESO = (
    "postprocess:PROC %(progress.status)s %(progress.postprocessor)s"
)
# Marca con la que yt-dlp imprime la ruta definitiva (tras unir audio y
# vídeo o convertir): así se distingue de cualquier otra línea de salida.
PREFIJO_RUTA_FINAL = "RUTA_FINAL"
INTERVALO_PROGRESO_S = 0.5


def plantillas_progreso() -> list[str]:
    """Los dos pares --progress-template: descarga (PROGD) y postproceso (PROC)."""
    return ["--progress-template", PLANTILLA_DESCARGA,
            "--progress-template", PLANTILLA_PROCESO]


def _numero(texto: str, convertir):
    if texto == "NA":
        return None
    try:
        return convertir(texto)
    except (TypeError, ValueError):
        return None


def analizar_linea_progreso(linea: str) -> dict | None:
    """Convierte una línea de progreso a datos, o devuelve ``None``."""
    partes = linea.rstrip("\r\n").split(" ", 6)
    if len(partes) not in (6, 7) or partes[0] != PREFIJO:
        return None

    descargado = _numero(partes[1], int)
    if descargado is None:
        return None
    total_bytes = _numero(partes[2], int)
    total_estimado = _numero(partes[3], float)
    total = total_bytes
    total_para_pct = total_bytes if total_bytes is not None else total_estimado
    velocidad = _numero(partes[4], float)
    if len(partes) == 7:
        eta = _numero(partes[5], int)
        nombre = partes[6]
    else:
        eta = None
        nombre = partes[5]
    if not nombre:
        return None

    pct = (descargado * 100.0 / total_para_pct) if total_para_pct else 0.0
    return {
        "descargado": descargado,
        "total": total,
        "pct": pct,
        "velocidad": velocidad,
        "eta": eta,
        "nombre": nombre,
    }


def analizar_linea_descarga(linea: str) -> dict | None:
    """Datos de una línea PROGD, con el índice y el total de la lista."""
    partes = linea.rstrip("\r\n").split(" ", 8)
    if len(partes) != 9 or partes[0] != "PROGD":
        return None
    descargado = _numero(partes[1], int)
    if descargado is None:
        return None
    total_bytes = _numero(partes[2], int)
    total_estimado = _numero(partes[3], float)
    total_para_pct = total_bytes if total_bytes is not None else total_estimado
    nombre = partes[8]
    if not nombre:
        return None
    pct = (descargado * 100.0 / total_para_pct) if total_para_pct else 0.0
    return {
        "descargado": descargado,
        "total_bytes": total_bytes,
        "pct": pct,
        "velocidad": _numero(partes[4], float),
        "eta": _numero(partes[5], int),
        "indice": _numero(partes[6], int),
        "total": _numero(partes[7], int),
        "nombre": nombre,
    }


def analizar_linea_proceso(linea: str) -> tuple[str, str] | None:
    """Estado y procesador de una línea PROC, o None."""
    partes = linea.rstrip("\r\n").split(" ", 2)
    if len(partes) != 3 or partes[0] != "PROC":
        return None
    if not partes[1] or not partes[2]:
        return None
    return partes[1], partes[2]


def progreso_total(indice, total, pct) -> float:
    """Progreso del vídeo dentro del total de la lista, siempre de 0 a 100."""
    pct = max(0.0, min(100.0, float(pct or 0.0)))
    if not total or total <= 1 or not indice:
        return pct
    return max(0.0, min(100.0, ((indice - 1) * 100 + pct) / total))


def debe_emitir_progreso(ultimo_ts, ahora, pct):
    """Decide si toca avisar del progreso, para no inundar la interfaz."""
    return (ultimo_ts is None or pct >= 100.0 or
            ahora - ultimo_ts >= INTERVALO_PROGRESO_S)


def _avisar(cb, *args) -> None:
    try:
        cb(*args)
    except Exception as exc:
        # Import perezoso: diagnostico importa ytdlp_bin, que importa este
        # módulo, y a nivel de módulo sería un ciclo.
        from bellbird.core import diagnostico
        diagnostico.obtener_logger(__name__).debug(
            "callback de descarga lanzó: %s", exc)


def _aplicar_descarga(estado, datos, progreso_cb, al_detalle) -> None:
    estado["ultimo_archivo"] = datos["nombre"]
    cambios = {"procesando": False}
    if datos["indice"] is not None:
        estado["indice"] = cambios["indice"] = datos["indice"]
    if datos["total"] is not None:
        estado["total"] = cambios["total"] = datos["total"]
    estado["procesando"] = False
    pct = progreso_total(estado["indice"], estado["total"], datos["pct"])
    ahora = time.monotonic()
    if debe_emitir_progreso(estado["ultimo_ts"], ahora, pct):
        estado["ultimo_ts"] = ahora
        _avisar(progreso_cb, pct, datos["velocidad"], datos["eta"], datos["nombre"])
    _avisar(al_detalle, cambios)


def tratar_linea(linea, estado, progreso_cb, al_detalle) -> None:
    """Aplica una línea de yt-dlp al estado de la descarga en curso."""
    if linea.startswith("ERROR:"):
        estado["ultimo_error"] = linea.strip()
    if linea.startswith(PREFIJO_RUTA_FINAL + " "):
        ruta = linea[len(PREFIJO_RUTA_FINAL) + 1:].strip()
        if ruta:
            estado["rutas"].append(ruta)
            pct = progreso_total(estado["indice"], estado["total"], 100)
            _avisar(progreso_cb, pct, None, None, Path(ruta).name)
            _avisar(al_detalle, {"ruta": ruta})
        return
    proceso = analizar_linea_proceso(linea)
    if proceso is not None:
        if proceso[0] == "started" and proceso[1] != "MoveFiles":
            estado["procesando"] = True
            _avisar(al_detalle, {"procesando": True})
        return
    datos = analizar_linea_descarga(linea)
    if datos is not None:
        _aplicar_descarga(estado, datos, progreso_cb, al_detalle)
