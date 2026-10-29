"""Texto de la pregunta por igualar el volumen y tamaño de lo pendiente.

Sin interfaz: arma lo que la ventana de música muestra en el diálogo de
Windows. El tamaño se mide en base 1024 y se redondea para que se lea en
voz alta sin decimales de más.
"""

from __future__ import annotations

from ytchat.core.idioma import N_, _, ngettext

TITULO = N_("Igualar volumen")
CASILLA = N_("&No volver a preguntar")

_MB = 1024 * 1024
_GB = 1024 * 1024 * 1024

_PREGUNTA = N_(
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
        return _("menos de 1 MB")
    if total < _MB:
        return _("menos de 1 MB")
    if total < _GB:
        # Traductores: {mb} es cuántos megabytes; se lee en el diálogo.
        return _("{mb} MB").format(mb=total // _MB)
    gigas = f"{round(total / _GB, 1):.1f}".replace(".", ",")
    # Traductores: {gb} son los gigabytes con coma; se lee en el diálogo.
    return _("{gb} GB").format(gb=gigas)


def texto_pregunta(cantidad, bases) -> str:
    """La pregunta: cuántas canciones quedan sin medir y cuánto ocupan.

    Con una canción dice «1 canción» y con más, «N canciones». El tamaño
    va entre paréntesis. Función pura.
    """
    try:
        numero = int(cantidad)
    except (TypeError, ValueError):
        numero = 0
    # Traductores: {numero} es cuántas canciones faltan por medir; pregunta.
    inicio = ngettext("Hay 1 canción sin medir",
                      "Hay {numero} canciones sin medir",
                      numero).format(numero=numero)
    # Traductores: {inicio} es la cuenta, {tamano} el tamaño y {pregunta} el pedido.
    return _("{inicio} ({tamano}). {pregunta}").format(
        inicio=inicio, tamano=texto_tamano(bases), pregunta=_(_PREGUNTA))
