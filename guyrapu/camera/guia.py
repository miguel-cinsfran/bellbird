"""Guía de encuadre con pitidos, lógica pura.

Traduce la posición del rostro en un pitido: hacia qué lado moverse,
con cuánto paneo y qué nota, y cada cuánto repetirlo. Sin wx ni sonido:
el hilo, la cámara y la reproducción viven en `ui.encuadre_camara`.

El lado sigue la misma regla de espejo de `encuadre.analizar`, con sus
umbrales importados. La altura de los ojos alta en la imagen pide
«abajo» y la baja pide «arriba», con una nota continua entre ambos.
El intervalo sale de la distancia al objetivo (centro horizontal 0,5 y
ojos a 0,35): cuanto más cerca, más seguidos los pitidos.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from guyrapu.camera import encuadre

# Objetivo en la imagen: centro horizontal y ojos a esa altura.
OBJETIVO_X = 0.5
OBJETIVO_OJOS_Y = 0.35
# Paneo proporcional: este es el desvío que lleva el sonido a un lado entero.
PANEOS_DESVIO = 0.3
# Ritmo de los pitidos: base, cuánto abre con la distancia y sus topes.
INTERVALO_BASE = 0.08
INTERVALO_POR_DISTANCIA = 1.0
INTERVALO_MINIMO = 0.08
INTERVALO_MAXIMO = 0.6
# Sin rostro se avisa con un zumbido aparte, cada un segundo.
INTERVALO_SIN_ROSTRO = 1.0
# Racha centrada que termina la guía sola, con la confirmación.
TIEMPO_CENTRADA = 1.5
# Nota de partida y tramo de ojos que va de una octava abajo a una arriba.
FRECUENCIA_BASE = 440.0
OCTAVA_OJOS = 0.25
SEMITONOS_OCTAVA = 12


@dataclass(frozen=True, slots=True)
class Pulso:
    """Un pitido de la guía: a dónde moverse, cómo suena y cada cuánto."""

    lado: str
    altura: str
    intervalo: float
    paneo: float = 0.0
    frecuencia: float = FRECUENCIA_BASE


@dataclass
class Marcha:
    """Marcha de una guía en curso: qué cuadro mira y desde cuándo va centrada.

    `cliente`, `camara` y `detector` los llena el hilo de la guía y esta
    módulo nunca los toca: solo los guarda para la vuelta siguiente.
    """

    inicio: float
    cliente: object = None
    camara: object = None
    detector: object = None
    espejo: bool = False
    pitido: float = 0.0
    centrada: float | None = None


def _intervalo(centro_x: float, ojos_y: float) -> float:
    """Segundos hasta el pitido siguiente, más cerca más seguido."""
    distancia = math.hypot(centro_x - OBJETIVO_X, ojos_y - OBJETIVO_OJOS_Y)
    return min(INTERVALO_MAXIMO,
               max(INTERVALO_MINIMO,
                   INTERVALO_BASE + INTERVALO_POR_DISTANCIA * distancia))


def _paneo(centro_x: float, espejo: bool) -> float:
    """De -1 (izquierda) a 1 (derecha), proporcional al desvío del centro."""
    paneo = (centro_x - OBJETIVO_X) / PANEOS_DESVIO
    paneo = max(-1.0, min(1.0, paneo))
    return -paneo if espejo else paneo


def _frecuencia(ojos_y: float) -> float:
    """Nota continua: aguda con los ojos bajos, grave con los ojos altos."""
    semitonos = (ojos_y - OBJETIVO_OJOS_Y) / OCTAVA_OJOS * SEMITONOS_OCTAVA
    semitonos = max(-SEMITONOS_OCTAVA, min(SEMITONOS_OCTAVA, semitonos))
    return FRECUENCIA_BASE * 2 ** (semitonos / SEMITONOS_OCTAVA)


def _lado(centro_x: float, espejo: bool) -> str:
    """El lado hacia el que moverse, con la regla de espejo de `encuadre`."""
    izquierda = centro_x < encuadre.UMBRAL_IZQUIERDA
    derecha = centro_x > encuadre.UMBRAL_DERECHA
    if espejo:
        izquierda, derecha = derecha, izquierda
    return "izquierda" if izquierda else "derecha" if derecha else "centro"


def _altura(ojos_y: float) -> str:
    """Si los ojos piden subir, bajar o están en la franja media."""
    if ojos_y < encuadre.OJO_ALTO:
        return "abajo"
    if ojos_y > encuadre.OJO_BAJO:
        return "arriba"
    return "medio"


def pulso(rostro, ancho_imagen: float, alto_imagen: float,
          espejo: bool = False) -> Pulso:
    """El pitido que toca para el rostro principal, o «ninguno» sin rostro."""
    if rostro is None:
        return Pulso(lado="ninguno", altura="medio",
                     intervalo=INTERVALO_SIN_ROSTRO)
    centro_x = (rostro.x + rostro.ancho / 2) / ancho_imagen
    ojos_y = (rostro.ojo_izquierda[1] + rostro.ojo_derecha[1]) / 2
    ojos_y /= alto_imagen
    return Pulso(lado=_lado(centro_x, espejo), altura=_altura(ojos_y),
                 intervalo=_intervalo(centro_x, ojos_y),
                 paneo=_paneo(centro_x, espejo),
                 frecuencia=_frecuencia(ojos_y))


def _toca_pitido(marcha: Marcha, tono: Pulso, ahora: float) -> bool:
    """Marca el pitido si pasó su intervalo y dice si toca."""
    if ahora - marcha.pitido < tono.intervalo:
        return False
    marcha.pitido = ahora
    return True


def _fuera_de_zona(marcha: Marcha, tono: Pulso, ahora: float):
    """Sin rostro o pitido, cada uno a su ritmo."""
    if tono.lado == "ninguno":
        if _toca_pitido(marcha, tono, ahora):
            return ("sin_rostro", None)
        return ("nada", None)
    if _toca_pitido(marcha, tono, ahora):
        return ("pitido", tono)
    return ("nada", None)


def decidir(marcha: Marcha, tono: Pulso, ahora: float):
    """Qué toca este cuadro: ("pitido", pulso), ("centro", None),
    ("sin_rostro", None), ("lista", None) o ("nada", None).

    "centro" en cada cuadro dentro de la zona centrada, para que el tono
    siga sonando. "lista" cuando el centro lleva 1,5 s seguidos: suena la
    confirmación y se dice la frase.
    """
    centrado = tono.lado == "centro" and tono.altura == "medio"
    if centrado:
        if marcha.centrada is None:
            marcha.centrada = ahora
        elif ahora - marcha.centrada >= TIEMPO_CENTRADA:
            return ("lista", None)
    elif marcha.centrada is not None:
        marcha.centrada = None
    if centrado:
        return ("centro", None)
    return _fuera_de_zona(marcha, tono, ahora)


def cuadro(marcha: Marcha, rostros, ancho: float, alto: float,
           luz_rostro, luz_fondo, ahora: float):
    """Lo que toca para el cuadro: ("pitido", pulso, None), ("centro", None,
    None), ("lista", None, frase) o ("nada", None, None). La frase de
    "lista" es la de `encuadre`.
    """
    principal = encuadre.principal(rostros) if rostros else None
    tono = pulso(principal, ancho, alto, marcha.espejo)
    accion, objeto = decidir(marcha, tono, ahora)
    if accion != "lista":
        return (accion, objeto, None)
    estado = encuadre.analizar(
        rostros, ancho, alto, espejo=marcha.espejo,
        luz_rostro=luz_rostro, luz_fondo=luz_fondo)
    return ("lista", None, encuadre.frase(estado))
