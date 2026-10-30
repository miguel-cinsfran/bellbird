"""Búsquedas recientes del buscador de descargas, sin interfaz.

Razón: recordar las búsquedas recientes.
"""

from __future__ import annotations

from pathlib import Path

from bellbird.core import archivos
from bellbird.core import diagnostico

logger = diagnostico.obtener_logger(__name__)

TOPE = 20


def agregar(lista: list, texto: str) -> list:
    """Lo nuevo primero, sin duplicados aunque cambie mayúsculas.

    Ignora vacíos y recorta al tope. Devuelve una lista nueva.
    """
    limpio = (texto or "").strip() if isinstance(texto, str) else ""
    if not limpio:
        return list(lista)
    resto = [e for e in lista
             if isinstance(e, str) and e.strip()
             and e.lower() != limpio.lower()]
    return [limpio] + resto[:TOPE - 1]


def cargar(ruta: Path) -> list[str]:
    """Lee las recientes o devuelve una lista vacía si no se puede usar."""
    datos = archivos.leer_json(ruta, [])
    if not isinstance(datos, list):
        return []
    return [e for e in datos if isinstance(e, str) and e.strip()][:TOPE]


def guardar(ruta: Path, lista: list[str]) -> None:
    """Guarda las recientes sin impedir la búsqueda si falla el disco."""
    try:
        archivos.escribir_json_atomico(ruta, list(lista))
    except Exception as exc:
        logger.debug("guardar búsquedas recientes: %s", exc)
