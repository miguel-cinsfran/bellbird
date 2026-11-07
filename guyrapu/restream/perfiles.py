"""Perfiles de transmisión por Restream: qué son y cómo se guardan.

La validación es de quien edita; `guardar` no valida. Lo que YouTube acepta
en el cuadro del directo se guarda tal cual y se recuerda en el perfil.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from guyrapu.core import archivos
from guyrapu.core.idioma import _
from guyrapu.restream.canal_youtube import PLATAFORMA_YOUTUBE
from guyrapu.restream.youtube_por_restream import NOMBRE_MANUAL
from guyrapu.youtube.emision import LATENCIAS, PRIVACIDADES

ORIENTACIONES = ("horizontal", "vertical")
CHATS = ("", "youtube", "tiktok")


@dataclass(frozen=True, slots=True)
class Perfil:
    """Una configuración de transmisión con sus canales de Restream."""

    nombre: str
    canales: tuple
    orientacion: str
    youtube: bool = False
    chat: str = ""
    directo: dict = field(default_factory=dict)

    def a_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "canales": list(self.canales),
            "orientacion": self.orientacion,
            "youtube": self.youtube,
            "chat": self.chat,
            "directo": dict(self.directo),
        }


def _texto(valor) -> str:
    return valor if isinstance(valor, str) else ""


def _canales(valor):
    """Tupla de identificadores enteros, o None si alguno no lo es."""
    if valor is None:
        return ()
    if not isinstance(valor, (list, tuple)):
        return None
    limpios = []
    for canal in valor:
        if isinstance(canal, bool) or not isinstance(canal, int):
            return None
        limpios.append(canal)
    return tuple(limpios)


def _directo_nuevo(valor) -> dict:
    return dict(valor) if isinstance(valor, dict) else {}


def _directo_viejo(datos) -> dict:
    """Lo último usado de un perfil guardado con el formato anterior."""
    directo = {"titulo": _texto(datos.get("titulo")),
               "descripcion": _texto(datos.get("descripcion"))}
    if datos.get("privacidad") in PRIVACIDADES:
        directo["privacidad"] = datos["privacidad"]
    if datos.get("latencia") in LATENCIAS:
        directo["latencia"] = datos["latencia"]
    return directo


def _desde_dict(datos):
    if not isinstance(datos, dict):
        return None
    nombre = datos.get("nombre")
    if not isinstance(nombre, str) or not nombre.strip():
        return None
    orientacion = datos.get("orientacion")
    if orientacion not in ORIENTACIONES:
        return None
    canales = _canales(datos.get("canales"))
    if canales is None:
        return None
    chat = datos.get("chat")
    if chat not in CHATS:
        chat = ""
    directo = (_directo_nuevo(datos.get("directo"))
               if "directo" in datos else _directo_viejo(datos))
    return Perfil(
        nombre=nombre,
        canales=canales,
        orientacion=orientacion,
        youtube=bool(datos.get("youtube")),
        chat=chat,
        directo=directo,
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
        mensajes.append(_("Escribe un nombre para el perfil de Restream."))
    elif nombre.casefold() == "youtube":
        mensajes.append(_("El nombre «YouTube» está reservado. Elige otro."))
    else:
        for existente in existentes or []:
            if existente.nombre.strip().casefold() == nombre.casefold():
                mensajes.append(_("Ya existe un perfil de Restream con ese nombre."))
                break

    if not perfil.canales and not perfil.youtube:
        mensajes.append(_("Agrega al menos un destino al perfil de Restream."))
    if perfil.orientacion not in ORIENTACIONES:
        mensajes.append(
            _("La orientación del perfil de Restream debe ser horizontal o "
              "vertical."))
    return mensajes


def es_youtube_conectado(canal) -> bool:
    """¿El destino es el YouTube conectado en Restream?"""
    return getattr(canal, "plataforma_id", None) == PLATAFORMA_YOUTUBE


def es_manual_youtube(canal) -> bool:
    """¿El destino es el manual que Guyrapu crea para YouTube?"""
    return getattr(canal, "nombre", "") == NOMBRE_MANUAL


def normalizar_youtube(perfil, canales):
    """Saca del perfil el YouTube de Restream y lo cuenta como su casilla."""
    ids = {canal.id for canal in canales or ()
           if es_youtube_conectado(canal)}
    restantes = tuple(canal for canal in perfil.canales
                      if canal not in ids)
    youtube = perfil.youtube or any(canal in ids
                                    for canal in perfil.canales)
    if restantes == perfil.canales and youtube == perfil.youtube:
        return perfil
    return replace(perfil, canales=restantes, youtube=youtube)


def destinos_para_perfil(canales) -> list[tuple]:
    """Los destinos del cuadro del perfil, sin el YouTube de Restream."""
    return [(canal.id, canal.texto) for canal in canales or ()
            if not es_youtube_conectado(canal)
            and not es_manual_youtube(canal)]
