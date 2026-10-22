"""Texto de la pregunta por igualar el volumen y tamaño de lo pendiente.

Sin interfaz: arma lo que la ventana de música muestra en el diálogo de
Windows. El tamaño se mide en base 1024 y se redondea para que se lea en
voz alta sin decimales de más.
"""

from __future__ import annotations

TITULO = "Igualar el volumen"
CASILLA = "&No volver a preguntar"

_MB = 1024 * 1024
_GB = 1024 * 1024 * 1024

_PREGUNTA = (
    "¿Igualar su volumen ahora? Los archivos no se modifican. "
    "La medición usa el procesador y puede tardar.")


def texto_tamano(bases) -> str:
    """El tamaño en texto: menos de 1 MB, MB enteros o GB con una coma.

    Menos de 1 MB dice «menos de 1 MB». Hasta 1 GB van megabytes enteros
    («350 MB») y desde 1 GB, gigabytes con un decimal y coma («32,4 GB»).
    Función pura.
    """
    try:
        total = int(bases)
    except (TypeError, ValueError):
        return "menos de 1 MB"
    if total < _MB:
        return "menos de 1 MB"
    if total < _GB:
        return f"{total // _MB} MB"
    return f"{round(total / _GB, 1):.1f}".replace(".", ",") + " GB"


def texto_pregunta(cantidad, bases) -> str:
    """La pregunta: cuántas canciones quedan sin medir y cuánto ocupan.

    Con una canción dice «1 canción» y con más, «N canciones». El tamaño
    va entre paréntesis. Función pura.
    """
    try:
        numero = int(cantidad)
    except (TypeError, ValueError):
        numero = 0
    if numero == 1:
        inicio = "Hay 1 canción sin medir"
    else:
        inicio = f"Hay {numero} canciones sin medir"
    return f"{inicio} ({texto_tamano(bases)}). {_PREGUNTA}"
