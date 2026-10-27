"""Leer la sección [lectura] de config.ini.

Una sola responsabilidad: las opciones de lectura validadas contra un único
origen de verdad, sin tener que duplicar la carga de config.ini. `config`
las reexporta para que la carga y las pruebas sigan iguales.
"""

from __future__ import annotations

from ytchat.core.ini_tipado import _gs, _pb


def opciones_lectura(p) -> dict:
    """La sección [lectura] como claves en memoria, en el mismo orden."""
    formato = _gs(p, "lectura", "formato_prefijo").lower()
    if formato not in (
            "nombre_mensaje", "mensaje_nombre", "solo_mensaje", "solo_nombre"):
        formato = "nombre_mensaje"
    recientes = _gs(p, "lectura", "recientes").lower()
    if recientes not in ("lector", "voz"):
        recientes = "lector"
    return {
        "formato_prefijo": formato,
        "lectura_recientes": recientes,
        "lectura_atajos_globales": _pb(p, "lectura", "atajos_globales"),
    }
