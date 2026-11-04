"""Duraciones en palabras, para leer en voz alta."""

from __future__ import annotations

from bellbird.core.idioma import ngettext


def duracion_legible(segundos) -> str:
    """Duración en horas, minutos y segundos para leer en voz alta."""
    try:
        total = int(segundos)
    except (TypeError, ValueError):
        total = 0
    if total < 0:
        total = 0
    horas, resto = divmod(total, 3600)
    minutos, resto = divmod(resto, 60)
    partes = []
    if horas:
        partes.append(ngettext("{n} hora", "{n} horas", horas).format(n=horas))
    if minutos:
        partes.append(ngettext("{n} minuto", "{n} minutos", minutos).format(n=minutos))
    if resto or not partes:
        partes.append(ngettext("{n} segundo", "{n} segundos", resto).format(n=resto))
    if len(partes) == 1:
        return partes[0]
    return ", ".join(partes[:-1]) + " y " + partes[-1]
