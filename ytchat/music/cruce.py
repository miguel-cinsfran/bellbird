"""Cuentas del fundido cruzado entre canciones, sin interfaz.

La curva es de igual potencia: la que sale baja con un coseno y la que entra
sube con un seno, así el volumen total no cae en el medio. El cruce empieza
donde termina el sonido real de la canción, no donde termina el archivo.
Módulo puro.
"""

from __future__ import annotations

import math

from ytchat.music.bordes import Bordes

CRUCE_FABRICA_S = 6
CRUCE_MAXIMO_S = 12
CRUCE_MANUAL_MS = 500
SALTO_MINIMO_MS = 500

AMPLITUD_MINIMA_DB = -120.0


def _a_db(amplitud: float) -> float:
    """La amplitud como decibelios; el silencio es -120 dB."""
    if amplitud < 1e-12:
        return AMPLITUD_MINIMA_DB
    return 20.0 * math.log10(amplitud)


def ganancias_db(progreso) -> tuple[float, float]:
    """Las ganancias de la canción que sale y la que entra, en dB.

    `progreso` va de 0 a 1 y se recorta. La curva de igual potencia reparte
    la energía entre las dos canciones durante todo el cruce.
    """
    try:
        avance = float(progreso)
    except (TypeError, ValueError):
        avance = 0.0
    avance = max(0.0, min(1.0, avance))
    angulo = avance * math.pi / 2.0
    return _a_db(math.cos(angulo)), _a_db(math.sin(angulo))


def punto_de_cruce(largo_ms, bordes: Bordes | None, cruce_ms) -> tuple[int, int] | None:
    """Dónde empieza el cruce y cuánto dura, o None si no se puede cruzar.

    El fin del sonido es el largo menos el silencio final. La duración no
    pasa de la mitad de lo que dura el sonido, para que el cruce nunca
    empiece antes de la mitad de la canción.
    """
    try:
        largo = int(largo_ms)
        pedido = int(cruce_ms)
    except (TypeError, ValueError):
        return None
    if largo <= 0 or pedido <= 0:
        return None
    fin = largo - int(getattr(bordes, "silencio_final_ms", 0) or 0)
    if fin <= 0:
        return None
    duracion = min(pedido, fin // 2)
    if duracion <= 0:
        return None
    return fin - duracion, duracion


def salto_inicial_ms(bordes: Bordes | None) -> int:
    """Cuántos milisegundos del principio se saltean, o 0 si no vale la pena."""
    if bordes is None:
        return 0
    silencio = int(getattr(bordes, "silencio_inicial_ms", 0) or 0)
    if silencio < SALTO_MINIMO_MS:
        return 0
    return silencio


def hay_siguiente_local(cola, orden, cursor, repetir) -> bool:
    """Verdadero si la canción actual tiene una siguiente local que cruzar.

    Con repetir "tema" la siguiente es la misma. Al final del orden no hay
    siguiente aunque se repita todo: el ciclo nuevo se mezcla y no se sabe
    cuál viene. Un enlace de YouTube no se cruza.
    """
    if cursor is None:
        return False
    if repetir == "tema":
        if not 0 <= cursor < len(orden):
            return False
        return not cola[orden[cursor]].es_enlace
    destino = cursor + 1
    if not 0 <= destino < len(orden):
        return False
    return not cola[orden[destino]].es_enlace
