"""Tonos de la guía de encuadre, armados en memoria.

Su única razón para cambiar es cómo suenan los pitidos, el tono del centro
y la muestra de Preferencias. Sin wx ni winmm: cada función devuelve un
WAV completo, con cabecera RIFF, a 44 100 Hz, 16 bits y estéreo, listo
para `voice.sonido_memoria`.
"""

from __future__ import annotations

import io
import math
import wave

import numpy as np

FRECUENCIA_MUESTREO = 44100
BITS = 16
CANALES = 2
DURACION_PITIDO = 0.06
FRECUENCIA_CENTRO = 440.0
DURACION_CENTRO = 0.5
# Pico de los `.wav` que generaba `scripts/sound_gen.py` antes de este
# módulo (0,6 del fondo de escala). Ningún timbre lo pasa.
PICO = 0.6
PICO_8BITS = 0.45
TIMBRES = ("normal", "calido", "8bits")

_ATAQUE = {"normal": 0.004, "calido": 0.015, "8bits": 0.001}
_CAIDA = {"normal": 0.06, "calido": 0.09, "8bits": 0.08}
_SILENCIO_MUESTRA = 0.05


def normalizar_timbre(timbre) -> str:
    """El timbre pedido, o «normal» si no es uno de los tres conocidos."""
    return timbre if timbre in TIMBRES else "normal"


def _envolvente(muestras: int, timbre: str):
    """Ataque lineal y caída exponencial, como los pitidos de hoy."""
    ataque = max(1, int(FRECUENCIA_MUESTREO * _ATAQUE[timbre]))
    indices = np.arange(muestras)
    subida = np.minimum(1.0, indices / ataque)
    caida = np.exp(-indices / (FRECUENCIA_MUESTREO * _CAIDA[timbre]))
    return subida * caida


def _normalizar(onda, objetivo: float):
    pico = float(np.abs(onda).max()) if len(onda) else 0.0
    if pico < 1e-9:
        return onda
    return onda * (objetivo / pico)


def _onda(frecuencia: float, muestras: int, timbre: str, con_envolvente: bool):
    """La forma de onda del timbre, escalada al pico que le toca."""
    timbre = normalizar_timbre(timbre)
    fase = 2 * math.pi * frecuencia * np.arange(muestras) / FRECUENCIA_MUESTREO
    if timbre == "calido":
        onda = np.sin(fase) + 0.3 * np.sin(2 * fase) + 0.1 * np.sin(3 * fase)
    elif timbre == "8bits":
        onda = np.where(np.sin(fase) >= 0, 1.0, -1.0)
    else:
        onda = np.sin(fase)
    if con_envolvente:
        onda = onda * _envolvente(muestras, timbre)
    objetivo = PICO if timbre != "8bits" else PICO_8BITS
    return _normalizar(onda, objetivo)


def _muestras_pitido(frecuencia: float, timbre: str):
    return _onda(frecuencia, int(FRECUENCIA_MUESTREO * DURACION_PITIDO),
                 timbre, con_envolvente=True)


def _muestras_centro(timbre: str):
    """Medio segundo de la nota de partida, con ciclos enteros.

    El largo es un número entero de ciclos de 440 Hz, sin repetir el punto
    de inicio al final, así que el bucle sigue la onda sin un salto propio.
    """
    muestras = int(round(DURACION_CENTRO * FRECUENCIA_MUESTREO))
    return _onda(FRECUENCIA_CENTRO, muestras, timbre, con_envolvente=False)


def _estereo(mono, paneo: float):
    """Paneo de potencia constante: izquierda cos, derecha sin."""
    paneo = max(-1.0, min(1.0, float(paneo)))
    angulo = (paneo + 1) * math.pi / 4
    izquierda = mono * math.cos(angulo)
    derecha = mono * math.sin(angulo)
    return np.stack([izquierda, derecha], axis=1)


def _wav(estereo) -> bytes:
    """Un WAV completo en memoria, con cabecera RIFF."""
    enteros = np.round(np.clip(estereo, -1.0, 1.0) * 32767).astype("<i2")
    salida = io.BytesIO()
    with wave.open(salida, "wb") as wav:
        wav.setnchannels(CANALES)
        wav.setsampwidth(BITS // 8)
        wav.setframerate(FRECUENCIA_MUESTREO)
        wav.writeframes(enteros.tobytes())
    return salida.getvalue()


def pitido(paneo: float, frecuencia: float, timbre: str) -> bytes:
    """Un pitido de 60 ms hacia el lado y con la nota pedidos."""
    return _wav(_estereo(_muestras_pitido(frecuencia, timbre), paneo))


def tono_centro(timbre: str) -> bytes:
    """Medio segundo del tono del centro, para repetir en bucle sin corte."""
    return _wav(_estereo(_muestras_centro(timbre), 0.0))


def muestra(timbre: str) -> bytes:
    """La muestra de Preferencias: izquierda, derecha y el tono del centro."""
    timbre = normalizar_timbre(timbre)
    silencio = np.zeros((int(FRECUENCIA_MUESTREO * _SILENCIO_MUESTRA), 2))
    bloques = [
        _estereo(_muestras_pitido(FRECUENCIA_CENTRO, timbre), -1.0),
        silencio,
        _estereo(_muestras_pitido(FRECUENCIA_CENTRO, timbre), 1.0),
        silencio,
        _estereo(_muestras_centro(timbre), 0.0),
    ]
    return _wav(np.concatenate(bloques, axis=0))
