"""Qué autores y mensajes deja pasar el chat.

Única responsabilidad: aplicar los filtros por autor y por palabra. Lo usa el
procesamiento de cada mensaje.
"""

from __future__ import annotations


def permitido(autor: str, mensaje: str, config: dict) -> bool:
    al = autor.lower().strip()
    if any(u in al for u in config["usuarios_silenciados"]): return False
    if al in config.get("silenciados_ocultar", set()): return False
    ml = mensaje.lower()
    if any(p in ml for p in config["palabras_silenciadas"]): return False
    return True
