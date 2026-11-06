"""Qué opciones ofrece «Transmitir a» y cómo se traducen a un perfil de OBS.

Puro: sin red ni wx. La opción es lo que se elige y se guarda; el destino de
OBS es el perfil de OBS que corresponde. Los perfiles de Restream entran por
parámetro, ya leídos por quien llama.
"""

from __future__ import annotations

from dataclasses import dataclass

from guyrapu.capture import tiktok_vivo
from guyrapu.core.idioma import _
from guyrapu.obs.obs_destinos import DESTINOS

PREFIJO = "restream:"


@dataclass(frozen=True, slots=True)
class CambioCanal:
    """Un canal que hay que activar o desactivar, con su estado anterior."""

    canal_id: int
    activo: bool
    antes: bool


def opciones(perfiles) -> tuple:
    """Las opciones de «Transmitir a», con los perfiles al final."""
    return tuple(DESTINOS) + tuple(
        PREFIJO + perfil.nombre for perfil in perfiles or ())


def texto(opcion) -> str:
    """El texto visible de una opción; los perfiles llevan «Restream:»."""
    nombre = nombre_perfil(opcion)
    if not nombre:
        return opcion or ""
    return _("Restream: {nombre}").format(nombre=nombre)


def es_restream(opcion) -> bool:
    """¿La opción es un perfil de Restream y no un destino de OBS?"""
    return (isinstance(opcion, str) and opcion.startswith(PREFIJO)
            and len(opcion) > len(PREFIJO))


def nombre_perfil(opcion) -> str:
    """El nombre del perfil de una opción de Restream, o vacío."""
    return opcion[len(PREFIJO):] if es_restream(opcion) else ""


def es_opcion_valida(opcion) -> bool:
    """¿Se puede guardar como destino de transmisión?"""
    return opcion in DESTINOS or es_restream(opcion)


def perfil_de_opcion(opcion, perfiles):
    """El perfil que corresponde a una opción, o None si ya no existe."""
    nombre = nombre_perfil(opcion)
    if not nombre:
        return None
    for perfil in perfiles or ():
        if perfil.nombre == nombre:
            return perfil
    return None


def destino_obs(opcion, perfiles) -> str:
    """El perfil de OBS de una opción: vertical da TikTok y horizontal YouTube."""
    if opcion in DESTINOS:
        return opcion
    perfil = perfil_de_opcion(opcion, perfiles)
    if perfil is None:
        return ""
    return "TikTok" if perfil.orientacion == "vertical" else "YouTube"


def canales_del_perfil(perfil, canales) -> tuple:
    """Los canales de la cuenta que están en el perfil, en su orden."""
    por_id = {canal.id: canal for canal in canales or ()}
    return tuple(por_id[identificador] for identificador in perfil.canales
                 if identificador in por_id)


def plan_canales(perfil, canales) -> tuple:
    """Los canales que hay que cambiar para dejar activos solo los del perfil."""
    del_perfil = set(perfil.canales)
    cambios = []
    for canal in canales or ():
        activo = canal.id in del_perfil
        if bool(canal.activo) != activo:
            cambios.append(CambioCanal(
                canal_id=canal.id, activo=activo, antes=bool(canal.activo)))
    return tuple(cambios)


def usuario_tiktok(perfil, canales) -> str:
    """El usuario de TikTok del primer canal de TikTok del perfil.

    Sale de la dirección del canal y, si no hay, de su nombre. Devuelve
    vacío si el perfil no tiene un canal de TikTok con un usuario legible.
    """
    for canal in canales_del_perfil(perfil, canales):
        if canal.plataforma != "TikTok":
            continue
        usuario = tiktok_vivo.usuario_tiktok(canal.url)
        if not usuario:
            usuario = tiktok_vivo.usuario_tiktok(canal.nombre)
        if usuario:
            return usuario
    return ""
