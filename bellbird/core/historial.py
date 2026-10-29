"""Historial de directos y vídeos vistos (persistente, con lógica pura).

Guarda cada conexión con éxito: plataforma, la clave para reconectar (id de
YouTube o @usuario de TikTok), la URL, el título y el canal. Sirve para volver
a un directo sin recordar el enlace. Se persiste como JSON junto a la app.

Notas de diseño:
  - TikTok se reconecta por `@usuario/live` (reutilizable): una entrada por
    usuario, que se actualiza (título/fecha) al reconectar.
  - YouTube usa el id del vídeo, distinto en cada directo nuevo; se guarda cada
    uno igual (un directo terminado no reconectará, pero un vídeo normal sí).
  - La lógica (`upsert`, `de_plataforma`, `etiqueta`) es pura y testeable; la
    E/S de disco va aparte (`cargar`, `guardar`).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from bellbird.core import archivos
from bellbird.core import diagnostico
from bellbird.core.idioma import _

logger = diagnostico.obtener_logger(__name__)

MAX_ENTRADAS = 100


def upsert(lista: list, plataforma: str, clave: str, url: str, titulo: str,
           canal: str, fecha: str | None = None, directo: bool = False,
           max_entradas: int = MAX_ENTRADAS) -> list:
    """Lista nueva con la entrada al principio (la más reciente arriba),
    deduplicada por (plataforma, clave) y recortada a `max_entradas`.

    `directo=True` marca un directo (un directo de YouTube ya terminado no
    reconecta; un @usuario de TikTok sí, si está en vivo)."""
    if not clave:
        return list(lista)
    fecha = fecha or datetime.now().isoformat(timespec="seconds")
    entrada = {
        "plataforma": plataforma, "clave": clave, "url": url,
        "titulo": titulo or "", "canal": canal or "", "fecha": fecha,
        "directo": bool(directo),
    }
    resto = [e for e in lista
             if not (e.get("plataforma") == plataforma and e.get("clave") == clave)]
    return ([entrada] + resto)[:max_entradas]


def de_plataforma(lista: list, plataforma: str) -> list:
    """Entradas de una plataforma, en el orden guardado (reciente primero)."""
    return [e for e in lista if e.get("plataforma") == plataforma]


def fecha_mostrada(texto: str | None) -> str:
    """Fecha corta de una fila del historial, o el texto crudo si no se puede leer."""
    crudo = (texto or "")[:10]
    try:
        fecha = datetime.fromisoformat(crudo)
    except ValueError:
        return crudo
    # Traductores: fecha corta de una fila del historial; se ordena como la
    # fecha corta de Windows en ese idioma, y en inglés de Estados Unidos es
    # «{mes}/{dia}/{anio}».
    return _("{dia}/{mes}/{anio}").format(
        dia=f"{fecha.day:02d}", mes=f"{fecha.month:02d}",
        anio=f"{fecha.year:04d}")


def etiqueta(entrada: dict) -> str:
    """Texto legible de una entrada para la lista (canal — título · directo (fecha))."""
    canal = (entrada.get("canal") or "").strip()
    titulo = (entrada.get("titulo") or "").strip()
    fecha = fecha_mostrada(entrada.get("fecha"))
    partes = [p for p in (canal, titulo) if p]
    base = " — ".join(partes) if partes else (entrada.get("clave") or "?")
    if entrada.get("directo") and fecha:
        # Traductores: fila del historial de un directo; {base} es el canal y
        # el título y {fecha} la fecha corta.
        return _("{base} · directo ({fecha})").format(base=base, fecha=fecha)
    if entrada.get("directo"):
        # Traductores: fila del historial de un directo sin fecha; {base} es
        # el canal y el título.
        return _("{base} · directo").format(base=base)
    if fecha:
        # Traductores: fila del historial; {base} es el canal y el título y
        # {fecha} la fecha corta.
        return _("{base} ({fecha})").format(base=base, fecha=fecha)
    return base


def cargar(ruta: Path) -> list:
    """Lee el historial del JSON. Lista vacía si no existe o está corrupto.
    Se descartan las entradas que no sean dict: una lista editada a mano con
    basura dentro no debe tirar el diálogo del historial."""
    data = archivos.leer_json(ruta, [])
    if not isinstance(data, list):
        return []
    return [e for e in data if isinstance(e, dict)]


def guardar(ruta: Path, lista: list) -> None:
    """Escribe el historial al JSON (silencioso si falla; no es crítico)."""
    try:
        archivos.escribir_json_atomico(ruta, lista, indent=1)
    except Exception as exc:
        logger.debug("guardar historial: %s", exc)
