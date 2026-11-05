"""Cómo se escribe una fila de la lista de fuentes de audio de OBS."""

from __future__ import annotations

from guyrapu.core.idioma import _
from guyrapu.obs import filtros_microfono

CONOCIDOS = frozenset((
    filtros_microfono.TIPO_RUIDO,
    filtros_microfono.TIPO_PUERTA,
    filtros_microfono.TIPO_GANANCIA,
))


def texto(nombre, silenciada, filtros):
    """Nombre, estado y filtros de la fuente, en ese orden.

    Los filtros activos se muestran con el nombre que usa la app y, si hay
    otros activos que la app no ofrece, se resumen al final.
    """
    partes = [nombre, _("silenciada") if silenciada else _("activa")]
    partes.extend(_filtros(filtros))
    return ", ".join(partes)


def _filtros(filtros):
    filtros = list(filtros or ())
    estado = filtros_microfono.estado_de(filtros)
    nombres = []
    if estado.eliminacion:
        nombres.append(_("eliminación de ruido"))
    if estado.puerta:
        nombres.append(_("puerta anti-ruidos"))
    if estado.ganancia_db:
        # Traductores: {valor} es la ganancia en decibelios, con su signo.
        nombres.append(_("ganancia {valor:+d} dB").format(
            valor=estado.ganancia_db))
    otros = _otros_activos(filtros)
    if otros == 1:
        nombres.append(_("y 1 filtro más"))
    elif otros > 1:
        # Traductores: {cantidad} son los filtros activos que no son de la app.
        nombres.append(_("y {cantidad} filtros más").format(cantidad=otros))
    if not nombres:
        return [_("sin filtros")]
    return nombres


def _otros_activos(filtros):
    return sum(1 for filtro in filtros
               if filtro.get("filterEnabled")
               and filtro.get("filterKind") not in CONOCIDOS)
