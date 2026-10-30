"""Textos para mostrar un resultado de la búsqueda, sin interfaz.

Razón del módulo: dar forma legible a los datos de un resultado para la
lista y los detalles. Lo usan la pestaña de búsqueda y la vista de
contenido.
"""

from __future__ import annotations

from bellbird.core.idioma import _


def texto_detalles(resultado, ahora: float) -> str:
    """Los detalles de un resultado, una línea por dato sin los vacíos."""
    lineas = []
    if resultado.titulo:
        lineas.append(resultado.titulo)
    if resultado.canal:
        lineas.append(resultado.canal)
    duracion = texto_duracion(resultado.duracion)
    if duracion:
        lineas.append(duracion)
    vistas = texto_vistas(resultado.vistas)
    if vistas:
        lineas.append(vistas)
    fecha = texto_fecha(resultado.marca_tiempo, ahora)
    if fecha:
        lineas.append(fecha)
    if resultado.descripcion:
        lineas.append(resultado.descripcion)
    if resultado.en_directo:
        lineas.append(_("En directo"))
    elif resultado.programado:
        lineas.append(_("Programado"))
    return "\n".join(lineas)


def texto_duracion(segundos: int | None) -> str:
    """Duración como 17:48 o 1:02:05. Sin dato, cadena vacía."""
    if segundos is None:
        return ""
    try:
        total = int(segundos)
    except (TypeError, ValueError):
        return ""
    if total < 0:
        return ""
    horas = total // 3600
    minutos = (total % 3600) // 60
    resto = total % 60
    if horas:
        return f"{horas}:{minutos:02d}:{resto:02d}"
    return f"{minutos}:{resto:02d}"


def texto_vistas(n: int | None) -> str:
    """Vistas en español, con punto de miles. Sin dato, cadena vacía."""
    if n is None:
        return ""
    try:
        cuantos = int(n)
    except (TypeError, ValueError):
        return ""
    if cuantos == 1:
        return _("1 vista")
    numero = f"{cuantos:,}".replace(",", ".")
    return _("{n} vistas").format(n=numero)


def texto_fecha(marca: int | None, ahora: float) -> str:
    """Fecha relativa, nunca exacta porque yt-dlp la estima.

    Sin dato, cadena vacía. Una marca futura cuenta como hoy.
    """
    if marca is None:
        return ""
    try:
        diferencia = float(ahora) - float(marca)
    except (TypeError, ValueError):
        return ""
    if diferencia < 0:
        diferencia = 0
    dias = int(diferencia // 86400)
    if dias < 1:
        return _("hoy")
    if dias == 1:
        return _("hace 1 día")
    if dias < 7:
        return _("hace {n} días").format(n=dias)
    if dias < 30:
        semanas = dias // 7
        if semanas <= 1:
            return _("hace 1 semana")
        return _("hace {n} semanas").format(n=semanas)
    if dias < 365:
        meses = dias // 30
        if meses <= 1:
            return _("hace 1 mes")
        return _("hace {n} meses").format(n=meses)
    anios = dias // 365
    if anios <= 1:
        return _("hace 1 año")
    return _("hace {n} años").format(n=anios)
