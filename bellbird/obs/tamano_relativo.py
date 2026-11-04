"""Tamaño de una fuente medido como parte del vídeo."""

from __future__ import annotations

from bellbird.core.idioma import N_

COMUNES = (
    ("un_quinto", N_("Un quinto del vídeo"), 1 / 5),
    ("un_cuarto", N_("Un cuarto del vídeo"), 1 / 4),
    ("un_tercio", N_("Un tercio del vídeo"), 1 / 3),
    ("la_mitad", N_("La mitad del vídeo"), 1 / 2),
    ("dos_tercios", N_("Dos tercios del vídeo"), 2 / 3),
    ("todo", N_("Todo el vídeo"), 1.0),
)


def porcentajes(ancho, alto, lienzo_ancho, lienzo_alto):
    """El ancho y el alto de la fuente como porcentaje del vídeo."""
    if not lienzo_ancho or not lienzo_alto:
        return 0, 0
    return (int(round(ancho / lienzo_ancho * 100)),
            int(round(alto / lienzo_alto * 100)))


def comun_de(porcentaje_ancho):
    """La clave del tamaño común a un punto o menos, o None."""
    for clave, _nombre, fraccion in COMUNES:
        if abs(porcentaje_ancho - round(fraccion * 100)) <= 1:
            return clave
    return None


def a_pixeles(porcentaje_ancho, porcentaje_alto, lienzo_ancho, lienzo_alto,
              ancho_actual, alto_actual):
    """El tamaño en píxeles que corresponde a los porcentajes pedidos."""
    if not lienzo_ancho or not lienzo_alto:
        return 1, 1
    ancho = max(1, int(round(porcentaje_ancho / 100 * lienzo_ancho)))
    if porcentaje_alto is None:
        if ancho_actual and alto_actual:
            alto = int(round(ancho * alto_actual / ancho_actual))
        else:
            alto = int(round(ancho * lienzo_alto / lienzo_ancho))
    else:
        alto = int(round(porcentaje_alto / 100 * lienzo_alto))
    return ancho, max(1, alto)
