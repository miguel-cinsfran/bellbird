"""Qué autores y mensajes deja pasar el chat.

Única responsabilidad: aplicar los filtros por autor y por palabra. Lo usan
el procesamiento de cada mensaje y el agrupador de entradas de TikTok antes de
sumar a una persona.
"""

from __future__ import annotations


def permitido(autor: str, mensaje: str, config: dict) -> bool:
    al = autor.lower().strip()
    if any(u in al for u in config["usuarios_silenciados"]): return False
    if al in config.get("silenciados_ocultar", set()): return False
    ml = mensaje.lower()
    if any(p in ml for p in config["palabras_silenciadas"]): return False
    return True


def entra_en_grupo(autor: str, config: dict) -> bool:
    """Si la persona puede figurar en una fila agrupada de entradas.

    Además del filtro del chat, deja fuera a quien se ocultó durante la
    sesión, que es lo mismo que le impide hablar en la lectura.
    """
    completo = {
        "usuarios_silenciados": [],
        "palabras_silenciadas": [],
        **config,
    }
    if not permitido(autor, "", completo):
        return False
    return autor.lower().strip() not in config.get("silenciados_runtime", set())
