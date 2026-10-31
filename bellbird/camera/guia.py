"""Guía de encuadre con pitidos, lógica pura.

Traduce la posición del rostro en un pitido: hacia qué lado moverse,
si subir o bajar, y cada cuánto repetirlo. Sin wx ni sonido: el hilo,
la cámara y la reproducción viven en `ui.encuadre_camara`.

El lado sigue la misma regla de espejo de `encuadre.analizar`, con sus
umbrales importados. La altura de los ojos alta en la imagen pide
«abajo» y la baja pide «arriba». El intervalo sale de la distancia al
objetivo (centro horizontal 0,5 y ojos a 0,35): cuanto más cerca, más
seguidos los pitidos.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from bellbird.camera import encuadre

# Objetivo en la imagen: centro horizontal y ojos a esa altura.
OBJETIVO_X = 0.5
OBJETIVO_OJOS_Y = 0.35
# Ritmo de los pitidos: base, cuánto abre con la distancia y sus topes.
INTERVALO_BASE = 0.2
INTERVALO_POR_DISTANCIA = 1.6
INTERVALO_MINIMO = 0.2
INTERVALO_MAXIMO = 0.9
# Sin rostro se avisa con un zumbido aparte, cada un segundo.
INTERVALO_SIN_ROSTRO = 1.0
# Racha centrada que termina la guía sola, con la confirmación.
TIEMPO_CENTRADA = 1.5


@dataclass(frozen=True, slots=True)
class Pulso:
    """Un pitido de la guía: a dónde moverse y en cuántos segundos se repite."""

    lado: str
    altura: str
    intervalo: float


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


def pulso(rostro, ancho_imagen: float, alto_imagen: float,
          espejo: bool = False) -> Pulso:
    """El pitido que toca para el rostro principal, o «ninguno» sin rostro."""
    if rostro is None:
        return Pulso(lado="ninguno", altura="medio",
                     intervalo=INTERVALO_SIN_ROSTRO)
    centro_x = (rostro.x + rostro.ancho / 2) / ancho_imagen
    izquierda = centro_x < encuadre.UMBRAL_IZQUIERDA
    derecha = centro_x > encuadre.UMBRAL_DERECHA
    if espejo:
        izquierda, derecha = derecha, izquierda
    lado = "izquierda" if izquierda else "derecha" if derecha else "centro"
    ojos_y = (rostro.ojo_izquierda[1] + rostro.ojo_derecha[1]) / 2
    ojos_y /= alto_imagen
    if ojos_y < encuadre.OJO_ALTO:
        altura = "abajo"
    elif ojos_y > encuadre.OJO_BAJO:
        altura = "arriba"
    else:
        altura = "medio"
    return Pulso(lado=lado, altura=altura,
                 intervalo=_intervalo(centro_x, ojos_y))


def decidir(marcha: Marcha, tono: Pulso, ahora: float):
    """Qué toca este cuadro: ("pitido", nombre), ("lista", None) o nada.

    "lista" cuando el centro lleva 1,5 s seguidos: suena la confirmación
    y se dice la frase. El nombre es el `.wav` de `sounds/guia/`.
    """
    if tono.lado == "centro" and tono.altura == "medio":
        if marcha.centrada is None:
            marcha.centrada = ahora
        elif ahora - marcha.centrada >= TIEMPO_CENTRADA:
            return ("lista", None)
    elif marcha.centrada is not None:
        marcha.centrada = None
    if tono.lado == "ninguno":
        nombre = "sin_rostro.wav"
    else:
        nombre = f"{tono.lado}_{tono.altura}.wav"
    if ahora - marcha.pitido >= tono.intervalo:
        marcha.pitido = ahora
        return ("pitido", nombre)
    return ("nada", None)


def cuadro(marcha: Marcha, rostros, ancho: float, alto: float,
           luz_rostro, luz_fondo, ahora: float):
    """Lo que toca para el cuadro: ("pitido", nombre, None), ("lista", None,
    frase) o ("nada", None, None). La frase de "lista" es la de `encuadre`.
    """
    principal = encuadre.principal(rostros) if rostros else None
    tono = pulso(principal, ancho, alto, marcha.espejo)
    accion, nombre = decidir(marcha, tono, ahora)
    if accion != "lista":
        return (accion, nombre, None)
    estado = encuadre.analizar(
        rostros, ancho, alto, espejo=marcha.espejo,
        luz_rostro=luz_rostro, luz_fondo=luz_fondo)
    return ("lista", None, encuadre.frase(estado))
