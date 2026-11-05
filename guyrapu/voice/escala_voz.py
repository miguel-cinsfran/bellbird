"""Escala de velocidad propia de la app y resolución de voces por nombre.

Módulo puro: no importa Prism ni wx. Traduce entre el porcentaje entero que
usa la interfaz (0 a 100 en pasos de 5, con 50 como velocidad normal) y las
escalas de cada motor, y elige la voz guardada entre las disponibles.
"""

from __future__ import annotations

VELOCIDAD_MIN = 0
VELOCIDAD_MAX = 100
PASO_VELOCIDAD = 5
VELOCIDAD_NORMAL = 50

_MOTOR_SAPI = "sapi"

# ElevenLabs acepta `speed` entre 0.7 y 1.2, con 1.0 normal.
_ELEVENLABS_MIN = 0.7
_ELEVENLABS_MAX = 1.2


def _a_multiplo(pct: int) -> int:
    return round(pct / PASO_VELOCIDAD) * PASO_VELOCIDAD


def ajustar_velocidad(pct: int, pasos: int) -> int:
    """Suma pasos a la velocidad, acota a 0..100 y deja múltiplos de 5.

    Un valor que no sea múltiplo de 5 (por ejemplo editado a mano en el
    config) se redondea al múltiplo más cercano antes de sumar.
    """
    base = _a_multiplo(int(pct))
    return max(VELOCIDAD_MIN,
               min(VELOCIDAD_MAX, base + int(pasos) * PASO_VELOCIDAD))


def velocidad_desde_wpm(wpm: int) -> int:
    """Convierte la velocidad vieja (palabras por minuto) al porcentaje nuevo.

    Primero reproduce el entero SAPI que usaba la app, después lo lleva a la
    escala propia. Así una velocidad guardada suena igual que antes en SAPI.
    """
    r = max(-10, min(10, round((int(wpm) - 180) / 20)))
    return (r + 10) * PASO_VELOCIDAD


def velocidad_a_prism(motor: str, pct: int) -> float:
    """Devuelve el float de velocidad de Prism (0.0 a 1.0) para un motor.

    En SAPI la escala es la del motor (entero -10 a 10) y hace falta el
    desplazamiento de 0.02 porque Prism trunca hacia cero al volver a entero.
    En cualquier otro motor el porcentaje pasa directo.
    """
    if motor == _MOTOR_SAPI:
        r = round(int(pct) / PASO_VELOCIDAD) - 10
        desplazamiento = 0.02 if r > 0 else (-0.02 if r < 0 else 0.0)
        prism = (r + desplazamiento + 10) / 20
    else:
        prism = int(pct) / 100
    return min(1.0, max(0.0, prism))


def porcentaje_a_prism(pct: int) -> float:
    """Convierte un porcentaje 0..100 al float 0.0..1.0 para volumen y tono."""
    return min(1.0, max(0.0, int(pct) / 100))


def velocidad_a_elevenlabs(pct: int) -> float:
    """Convierte el porcentaje 0..100 a la velocidad de ElevenLabs (0.7 a 1.2).

    50 es 1.0. Dos tramos lineales: de 0 a 50 va de 0.7 a 1.0, y de 50 a 100
    de 1.0 a 1.2. Se acota y se redondea a cuatro decimales porque la cuenta
    en float deja valores como 0.9999999 y la API espera 1.0 redondo.
    """
    valor = max(VELOCIDAD_MIN, min(VELOCIDAD_MAX, int(pct)))
    if valor <= VELOCIDAD_NORMAL:
        velocidad = _ELEVENLABS_MIN + (1.0 - _ELEVENLABS_MIN) * (
            valor / VELOCIDAD_NORMAL)
    else:
        velocidad = 1.0 + (_ELEVENLABS_MAX - 1.0) * (
            (valor - VELOCIDAD_NORMAL) / (VELOCIDAD_MAX - VELOCIDAD_NORMAL))
    return round(min(_ELEVENLABS_MAX, max(_ELEVENLABS_MIN, velocidad)), 4)


def resolver_voz(guardada, nombres) -> int | None:
    """Elige el índice de la voz guardada en el config.

    Acepta un índice en texto (configuraciones viejas), un nombre exacto o un
    fragmento del nombre sin distinguir mayúsculas. Devuelve None si nada
    coincide, si el texto está vacío o si el índice cae fuera de rango.
    """
    if guardada is None:
        return None
    texto = str(guardada).strip()
    if not texto:
        return None
    try:
        idx = int(texto)
    except ValueError:
        pass
    else:
        return idx if 0 <= idx < len(nombres) else None
    for i, nombre in enumerate(nombres):
        if nombre == texto:
            return i
    bajo = texto.lower()
    for i, nombre in enumerate(nombres):
        if bajo in nombre.lower():
            return i
    return None


def migrar_voz(guardada, nombres) -> str | None:
    """Convierte una voz guardada por número a su nombre, una sola vez.

    Solo convierte un entero en texto que caiga en rango; cualquier otro caso
    (nombre ya guardado, vacío, fuera de rango) devuelve None, que significa
    «no hay nada que migrar». La voz se guarda por nombre porque el número es
    la posición en la lista: instalar una voz corre la lista y cambia la
    elegida sin avisar.
    """
    if guardada is None:
        return None
    texto = str(guardada).strip()
    if not texto:
        return None
    try:
        idx = int(texto)
    except ValueError:
        return None
    if 0 <= idx < len(nombres):
        return nombres[idx]
    return None
