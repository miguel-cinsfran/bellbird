"""Perfiles de transmisión por Restream: qué son y cómo se guardan.

La validación es de quien edita; `guardar` no valida. Privacidad y latencia
usan los valores de YouTube para no mantener dos listas que se separen.
"""

from __future__ import annotations

from dataclasses import dataclass

from bellbird.core import archivos
from bellbird.core.idioma import _
from bellbird.youtube.emision import (
    LATENCIAS,
    LATENCIA_INICIAL,
    PRIVACIDADES,
    PRIVACIDAD_INICIAL,
)

ORIENTACIONES = ("horizontal", "vertical")


@dataclass(frozen=True, slots=True)
class Perfil:
    """Una configuración de transmisión con sus canales de Restream."""

    nombre: str
    canales: tuple
    orientacion: str
    titulo: str = ""
    descripcion: str = ""
    privacidad: str = PRIVACIDAD_INICIAL
    latencia: str = LATENCIA_INICIAL

    def a_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "canales": list(self.canales),
            "orientacion": self.orientacion,
            "titulo": self.titulo,
            "descripcion": self.descripcion,
            "privacidad": self.privacidad,
            "latencia": self.latencia,
        }


def _texto(valor) -> str:
    return valor if isinstance(valor, str) else ""


def _canales(valor):
    """Tupla de identificadores enteros, o None si alguno no lo es."""
    if not isinstance(valor, (list, tuple)) or not valor:
        return None
    limpios = []
    for canal in valor:
        if isinstance(canal, bool) or not isinstance(canal, int):
            return None
        limpios.append(canal)
    return tuple(limpios)


def _desde_dict(datos):
    if not isinstance(datos, dict):
        return None
    nombre = datos.get("nombre")
    if not isinstance(nombre, str) or not nombre.strip():
        return None
    orientacion = datos.get("orientacion")
    if orientacion not in ORIENTACIONES:
        return None
    privacidad = datos.get("privacidad")
    if privacidad not in PRIVACIDADES:
        return None
    latencia = datos.get("latencia")
    if latencia not in LATENCIAS:
        return None
    canales = _canales(datos.get("canales"))
    if canales is None:
        return None
    return Perfil(
        nombre=nombre,
        canales=canales,
        orientacion=orientacion,
        titulo=_texto(datos.get("titulo")),
        descripcion=_texto(datos.get("descripcion")),
        privacidad=privacidad,
        latencia=latencia,
    )


def cargar(ruta) -> list[Perfil]:
    """Lee los perfiles guardados y salta las entradas que no son válidas."""
    datos = archivos.leer_json(ruta, [])
    if not isinstance(datos, list):
        return []
    perfiles = []
    nombres = set()
    for entrada in datos:
        perfil = _desde_dict(entrada)
        if perfil is None:
            continue
        clave = perfil.nombre.strip().casefold()
        if clave in nombres:
            continue
        nombres.add(clave)
        perfiles.append(perfil)
    return perfiles


def guardar(ruta, perfiles) -> None:
    archivos.escribir_json_atomico(ruta, [perfil.a_dict() for perfil in perfiles])


def validar(perfil, existentes) -> list[str]:
    """Devuelve los mensajes que impiden guardar el perfil; vacío si vale."""
    mensajes = []
    nombre = (perfil.nombre or "").strip()
    if not nombre:
        mensajes.append(_("Escribe un nombre para el perfil."))
    elif nombre.casefold() == "youtube":
        mensajes.append(_("El nombre «YouTube» está reservado. Elige otro."))
    else:
        for existente in existentes or []:
            if existente.nombre.strip().casefold() == nombre.casefold():
                mensajes.append(_("Ya existe un perfil con ese nombre."))
                break

    if not perfil.canales:
        mensajes.append(_("Agrega al menos un canal al perfil."))
    if perfil.orientacion not in ORIENTACIONES:
        mensajes.append(
            _("La orientación del perfil debe ser horizontal o vertical."))
    if perfil.privacidad not in PRIVACIDADES:
        mensajes.append(_("La privacidad del perfil no está entre las opciones."))
    if perfil.latencia not in LATENCIAS:
        mensajes.append(_("La latencia del perfil no está entre las opciones."))
    return mensajes
