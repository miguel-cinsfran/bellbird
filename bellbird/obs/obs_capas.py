"""Cómo se reordenan las capas de una escena de OBS."""

from __future__ import annotations

from bellbird.core.idioma import _


def _elemento(elementos, fuente):
    return next((elemento for elemento in elementos
                 if elemento.get("sourceName") == fuente), None)


def indice_destino(elementos, fuente, movimiento):
    """El índice nuevo de la fuente, o None si no hay que moverla."""
    elemento = _elemento(elementos, fuente)
    if elemento is None:
        return None
    actual = elemento.get("sceneItemIndex", 0)
    # En OBS el índice 0 es el fondo y el más alto es el frente.
    total = len(elementos)
    if isinstance(movimiento, int):
        return (movimiento if movimiento != actual
                and 0 <= movimiento < total else None)
    destinos = {
        "adelante": actual + 1 if actual < total - 1 else None,
        "atras": actual - 1 if actual > 0 else None,
        "fondo": 0 if actual > 0 else None,
    }
    return destinos.get(movimiento)


def lugar(elementos, fuente):
    """La posición de la fuente contando desde el frente, y el total."""
    elemento = _elemento(elementos, fuente)
    if elemento is None:
        return None
    total = len(elementos)
    return total - elemento.get("sceneItemIndex", 0), total


def mover(pedir, elementos, escena, fuente, movimiento, parada=None):
    """Pide a OBS el índice nuevo y dice si movió la fuente."""
    elemento = _elemento(elementos, fuente)
    destino = indice_destino(elementos, fuente, movimiento)
    if elemento is None or destino is None:
        return False
    pedir("SetSceneItemIndex", {
        "sceneName": escena, "sceneItemId": elemento["sceneItemId"],
        "sceneItemIndex": destino,
    }, parada)
    return True


def frase_de_movimiento(elementos, fuente, movimiento, movido):
    """Lo que se anuncia después de mover la fuente o al no poder moverla."""
    if not movido:
        if movimiento == "adelante":
            # Traductores: {fuente} es el nombre de la fuente.
            return _("{fuente} ya está al frente.").format(fuente=fuente)
        # Traductores: {fuente} es el nombre de la fuente.
        return _("{fuente} ya está al fondo.").format(fuente=fuente)
    destino = indice_destino(elementos, fuente, movimiento)
    total = len(elementos)
    # Traductores: {fuente} es el nombre; {n} es el lugar desde el frente y
    # {total} la cantidad de capas.
    return _("{fuente}: capa {n} de {total}.").format(
        fuente=fuente, n=total - destino, total=total)
