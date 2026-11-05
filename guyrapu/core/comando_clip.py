"""Decisión pura del comando !clip escrito en el chat.

No importa wx ni OBS: recibe el texto y el reloj, y dice si hay que guardar
un clip. La espera se mide en minutos desde el último clip que pidió el chat.
"""

from __future__ import annotations

COMANDO = "!clip"
ESPERA_POR_DEFECTO = 1


def es_pedido(texto) -> bool:
    """¿El mensaje empieza con la palabra !clip? No importan mayúsculas ni lo
    que venga después, salvo que sea otra palabra que empiece igual."""
    limpio = str(texto or "").strip().casefold()
    if not limpio.startswith(COMANDO):
        return False
    resto = limpio[len(COMANDO):]
    return not resto or not (resto[0].isalnum() or resto[0] == "_")


def decidir(texto, ahora, ultimo, espera_minutos) -> bool:
    """¿Corresponde guardar el clip que pide este mensaje?

    `ultimo` es el instante del último clip guardado por el chat, o None si
    todavía no hubo. El borde de la espera cuenta como cumplido.
    """
    if not es_pedido(texto):
        return False
    if ultimo is None:
        return True
    try:
        minutos = max(0, int(espera_minutos))
    except (TypeError, ValueError):
        minutos = ESPERA_POR_DEFECTO
    try:
        return float(ahora) - float(ultimo) >= minutos * 60
    except (TypeError, ValueError):
        return True
