"""Si el YouTube de Restream es el canal de la sesión de la app.

Puro: no habla con la red ni con wx. Decide entre tres resultados y arma la
línea de la pestaña Cuenta. La transmisión por Restream usará la misma
comparación antes de empezar.
"""

from __future__ import annotations

from guyrapu.core.config import APP_NAME
from guyrapu.core.idioma import _

PLATAFORMA_YOUTUBE = 5

SIN_CANAL = "sin_canal"
COINCIDEN = "coinciden"
NO_COINCIDEN = "no_coinciden"


def _youtube(canales):
    return [canal for canal in canales
            if getattr(canal, "plataforma_id", None) == PLATAFORMA_YOUTUBE]


def comparar(canales, id_sesion):
    """Uno de SIN_CANAL, COINCIDEN o NO_COINCIDEN."""
    youtube = _youtube(canales)
    if not youtube or not id_sesion:
        return SIN_CANAL
    if any(getattr(canal, "identificador", "") == id_sesion
           for canal in youtube):
        return COINCIDEN
    return NO_COINCIDEN


def texto(canales, id_sesion):
    """La línea de la pestaña Cuenta, o vacía si no hay nada que decir."""
    resultado = comparar(canales, id_sesion)
    if resultado == SIN_CANAL:
        return ""
    nombres = ", ".join(getattr(canal, "nombre", "")
                        for canal in _youtube(canales))
    if resultado == COINCIDEN:
        plantilla = _("YouTube en Restream: {canales}, el mismo canal de "
                      "la sesión de {app}.")
    else:
        plantilla = _("YouTube en Restream: {canales}, que no es el canal "
                      "de la sesión de {app}.")
    return plantilla.format(canales=nombres, app=APP_NAME)
