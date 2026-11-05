"""Cómo se juzga el nivel que OBS mide para el micrófono. Sin wx ni conexión."""

from __future__ import annotations

import math
from dataclasses import dataclass

from guyrapu.core.idioma import _

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


SONIDO_BIEN = "microfono_bien"
SONIDO_REVISAR = "microfono_revisar"


def _frase_bien() -> str:
    return _("Nivel correcto.")


def _frase_bajo() -> str:
    return _("Nivel bajo. Acércate al micrófono o sube su volumen "
             "en Windows.")


def _frase_alto() -> str:
    return _("Nivel alto. Aléjate un poco del micrófono.")


def _frase_saturado() -> str:
    return _("El sonido se satura. Aléjate del micrófono o baja su "
             "volumen en Windows.")


def _frase_silencio() -> str:
    return _("No llega sonido. Revisa que el micrófono esté conectado y "
             "no silenciado en Windows.")


def _frase_sin_muestras() -> str:
    return _("OBS no recibe nada de este micrófono. Revisa que esté "
             "conectado o elige otro en Elegir micrófono.")


_FRASES = {
    BIEN: _frase_bien,
    BAJO: _frase_bajo,
    ALTO: _frase_alto,
    SATURADO: _frase_saturado,
    SILENCIO: _frase_silencio,
    SIN_MUESTRAS: _frase_sin_muestras,
}


def frase_de_tramo(nivel: Nivel) -> str:
    """Anuncio del nivel de un tramo con qué hacer para mejorarlo."""
    return _FRASES.get(nivel.estado, _frase_sin_muestras)()


def sonido_de_tramo(nivel: Nivel) -> str:
    """Evento de sonido que acompaña el anuncio de un tramo."""
    if nivel.estado == BIEN:
        return SONIDO_BIEN
    if nivel.estado in (BAJO, ALTO, SATURADO):
        return SONIDO_REVISAR
    return "microfono_sin_senal"
