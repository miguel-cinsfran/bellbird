"""Qué publicación ve cada canal de actualizaciones, sin interfaz.

El canal Estable consulta la última release con `releases/latest`, que
GitHub ya filtra sin prelanzamientos. El canal Beta mira la lista de
publicaciones y se queda con la mayor, sea beta o estable. La preferencia
se lee del INI sin la carga completa de `config`.
"""

from __future__ import annotations

import configparser
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bellbird.core import actualizacion
from bellbird.core import paths
from bellbird.core import versiones


CANALES = ("estable", "beta")

URL_PUBLICACIONES = (
    "https://api.github.com/repos/miguel-cinsfran/bellbird/releases?per_page=30"
)


def normalizar_canal(valor) -> str:
    """Un canal válido tal cual y cualquier otra cosa como estable."""
    if isinstance(valor, str) and valor.strip().lower() in CANALES:
        return valor.strip().lower()
    return "estable"


def canal_guardado() -> str:
    """Canal de `[actualizaciones]` en el INI, sin la carga completa.

    Ausente, ilegible o raro vale estable. No escribe el archivo.
    """
    # Local: config importa lo que este módulo necesita al cargarse.
    from bellbird.core.config import _mk_parser

    ruta = paths.config_ini()
    p = _mk_parser()
    if ruta.exists():
        try:
            p.read(ruta, encoding="utf-8")
        except configparser.Error:
            pass
    if not p.has_option("actualizaciones", "canal"):
        return "estable"
    return normalizar_canal(p.get("actualizaciones", "canal"))


def elegir_publicacion(
        publicaciones) -> actualizacion.PaqueteElegido | None:
    """La publicación de mayor versión con paquete compatible, o None.

    Saltea borradores y las que no tienen un zip con su firma. No filtra
    prelanzamientos: este camino es el del canal Beta.
    """
    if not isinstance(publicaciones, list):
        return None
    elegida = None
    orden_elegida = None
    for publicacion in publicaciones:
        if not isinstance(publicacion, dict):
            continue
        if publicacion.get("draft"):
            continue
        paquete = actualizacion.elegir_paquete(publicacion)
        if paquete is None:
            continue
        orden = versiones.orden_version(
            versiones.version_como_tupla(paquete.version))
        if orden_elegida is None or orden > orden_elegida:
            elegida = paquete
            orden_elegida = orden
    return elegida


def consultar_ultima_beta() -> actualizacion.PaqueteElegido | None:
    """La mayor publicación, beta o estable, con paquete compatible.

    None ante cualquier error de red o de JSON.
    """
    try:
        solicitud = Request(
            URL_PUBLICACIONES,
            headers={"User-Agent": actualizacion.USER_AGENT})
        with urlopen(solicitud, timeout=actualizacion.TIEMPO_ESPERA) as respuesta:
            publicaciones = json.load(respuesta)
        return elegir_publicacion(publicaciones)
    except (HTTPError, URLError, OSError, TypeError, ValueError):
        return None
