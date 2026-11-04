"""Cómo se juzga el nivel que OBS mide para el micrófono. Sin wx ni conexión."""

from __future__ import annotations

import math
from dataclasses import dataclass

SILENCIO = "silencio"
BAJO = "bajo"
BIEN = "bien"
ALTO = "alto"
SATURADO = "saturado"
SIN_MUESTRAS = "sin_muestras"

# Cortes del medidor de OBS: verde hasta -20 dB, amarillo hasta -9 y rojo
# arriba. Por debajo de -60 no se distingue del silencio.
CORTE_SILENCIO = -60.0
CORTE_BAJO = -20.0
CORTE_BIEN = -9.0
CORTE_ALTO = -0.5


@dataclass(frozen=True)
class Nivel:
    """Estado del nivel y su pico en dBFS; None si no hubo muestras."""
    estado: str
    pico_dbfs: float | None


def _pico_de_canal(canal) -> float:
    # El canal trae [magnitud, pico, pico de entrada]; el índice 1 es el
    # pico que sale al aire, después del volumen y los filtros de OBS.
    return canal[1] if len(canal) > 1 else canal[-1]


def _picos_de(eventos, fuente: str):
    for evento in eventos:
        for entrada in evento.get("inputs") or ():
            if entrada.get("inputName") != fuente:
                continue
            for canal in entrada.get("inputLevelsMul") or ():
                yield _pico_de_canal(canal)


def _a_dbfs(pico: float) -> float:
    if pico <= 0:
        return float("-inf")
    return 20 * math.log10(pico)


def _estado(pico_dbfs: float) -> str:
    if pico_dbfs < CORTE_SILENCIO:
        return SILENCIO
    if pico_dbfs < CORTE_BAJO:
        return BAJO
    if pico_dbfs < CORTE_BIEN:
        return BIEN
    if pico_dbfs < CORTE_ALTO:
        return ALTO
    return SATURADO


def nivel_de(eventos, fuente: str) -> Nivel:
    """Estado del nivel de la fuente y su mayor pico en dBFS."""
    picos = list(_picos_de(eventos, fuente))
    if not picos:
        return Nivel(SIN_MUESTRAS, None)
    pico_dbfs = _a_dbfs(max(picos))
    return Nivel(_estado(pico_dbfs), round(pico_dbfs, 1))
