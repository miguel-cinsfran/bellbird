"""Textos del resumen de Cuenta y de la fila de un perfil de Restream.

Puro: no habla con la red ni con wx. Recibe la cuenta, los destinos y los
perfiles ya leídos, y normaliza los destinos que le llegan a la ventana.
"""

from __future__ import annotations

from types import SimpleNamespace

from guyrapu.core.idioma import _, ngettext


def como_destino(entrada):
    """Un destino con `texto`, `id` y `activo`, venga como venga."""
    if hasattr(entrada, "texto"):
        return entrada
    identificador, texto = entrada
    return SimpleNamespace(id=identificador, texto=texto, activo=True)


def resumen(conectada, nombre, destinos, perfiles, youtube="", errores=()):
    """El texto de la pestaña Cuenta, con los pasos que faltan."""
    if not conectada:
        lineas = [_(
            "Sin cuenta de Restream conectada. Restream transmite a varias "
            "plataformas a la vez: conecta la cuenta para elegir los destinos "
            "y armar perfiles.")]
    else:
        lineas = [_cuenta(nombre), _cantidades(destinos, perfiles)]
        paso = _paso(destinos, perfiles)
        if paso:
            lineas.append(paso)
        if youtube:
            lineas.append(youtube)
    lineas.extend(error for error in errores if error)
    return "\n".join(lineas)


def _cuenta(nombre):
    if nombre:
        return _("Cuenta conectada: {nombre}.").format(nombre=nombre)
    return _("Cuenta de Restream conectada.")


def _cantidades(destinos, perfiles):
    total = len(destinos)
    activos = sum(1 for destino in destinos
                  if getattr(destino, "activo", False))
    return _("{destinos}, {activos}. {perfiles}.").format(
        destinos=ngettext("{n} destino", "{n} destinos", total).format(n=total),
        activos=ngettext("{n} activo", "{n} activos", activos).format(
            n=activos),
        perfiles=ngettext("{n} perfil", "{n} perfiles", perfiles).format(
            n=perfiles))


def _paso(destinos, perfiles):
    if not destinos:
        return _("Todavía no hay destinos. Agrégalos en la pestaña Destinos.")
    if not perfiles:
        return _("Todavía no hay perfiles. Créalos en la pestaña Perfiles.")
    return ""


def fila_perfil(perfil, nombres=None, leidos=False):
    """La fila de la lista de perfiles con sus destinos por nombre."""
    nombres = nombres or {}
    partes = [_("{nombre}, {orientacion}").format(
        nombre=perfil.nombre, orientacion=_(perfil.orientacion))]
    canales = tuple(perfil.canales)
    if not canales:
        partes.append(": " + _("YouTube") if perfil.youtube
                      else _(", sin destinos"))
        return "".join(partes)
    conocidos = [nombres[canal] for canal in canales if canal in nombres]
    if conocidos:
        partes.append(": " + ", ".join(conocidos))
    faltan = sum(1 for canal in canales if canal not in nombres)
    if leidos and faltan == 1:
        partes.append(_(", falta un destino"))
    elif leidos and faltan > 1:
        partes.append(_(", faltan {n} destinos").format(n=faltan))
    return "".join(partes)
