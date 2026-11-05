"""Texto que dice la voz ante un evento del directo.

Puro y sin wx. Única razón para cambiar: qué dice la voz ante un evento.
"""

from __future__ import annotations

from bellbird.core.idioma import _
from bellbird.core.tipos_mensaje import (
    TIPO_MIEMBRO, TIPO_ENTRADA, TIPO_SEGUIR, TIPO_COMPARTIR, TIPO_COFRE,
    TIPO_ME_GUSTA, TIPO_ENCUESTA, TIPO_ENCUESTA_FIN,
)


def texto_evento(tipo, autor, monto, mensaje="") -> str | None:
    """Texto de la voz para un evento del directo, o None si no lo es."""
    if tipo in (TIPO_ENCUESTA, TIPO_ENCUESTA_FIN):
        return mensaje
    if tipo == TIPO_MIEMBRO:
        return _("Nuevo miembro: {autor}").format(autor=autor)
    if tipo == TIPO_ENTRADA:
        try:
            varios = int(monto) > 1
        except (TypeError, ValueError):
            varios = False
        # Traductores: {autor} es quien entró; en un grupo, varios nombres.
        return (_("{autor} entraron") if varios
                else _("{autor} entró")).format(autor=autor)
    if tipo == TIPO_SEGUIR:
        return _("{autor} sigue el canal").format(autor=autor)
    if tipo == TIPO_COMPARTIR:
        return _("{autor} compartió el directo").format(autor=autor)
    if tipo == TIPO_COFRE:
        return _("{autor} envió un cofre").format(autor=autor)
    if tipo == TIPO_ME_GUSTA:
        # Traductores: {n} es cuántos «me gusta» dieron.
        return (_("{autor} dio {n} me gusta").format(autor=autor, n=monto)
                if monto else _("{autor} dio me gusta").format(autor=autor))
    return None
