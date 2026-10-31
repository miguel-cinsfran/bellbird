"""Qué novedades se muestran al actualizar, sin interfaz.

Arma el texto de la ventana con las notas de todas las versiones
publicadas entre la instalada y la nueva, para que quien salta varias
versiones se entere de lo que trajo cada una. El paquete a instalar sigue
saliendo de la última release, que GitHub ya filtra.
"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bellbird.core import actualizacion
from bellbird.core.config import APP_VERSION
from bellbird.core.idioma import _


URL_PUBLICACIONES = (
    "https://api.github.com/repos/miguel-cinsfran/bellbird/releases?per_page=30"
)


def _texto_publicacion(publicacion: dict) -> str:
    """Encabezado con la versión y, debajo, el cuerpo tal como vino."""
    version = publicacion.get("tag_name", "")
    if version.startswith("v"):
        version = version[1:]
    # Traductores: encabezado de las novedades de una versión.
    encabezado = "## " + _("Versión {version}").format(version=version)
    cuerpo = publicacion.get("body")
    if not isinstance(cuerpo, str):
        cuerpo = ""
    cuerpo = cuerpo.strip()
    if not cuerpo:
        return encabezado
    # La línea en blanco deja la versión sola: `notas_legibles` junta los
    # párrafos y sin ella la pegaría al principio del cuerpo.
    return f"{encabezado}\n\n{cuerpo}"


def juntar_novedades(publicaciones, version_actual: str,
                     version_nueva: str) -> str:
    """Markdown con las versiones publicadas entre la instalada y la nueva.

    Deja fuera borradores, prereleases y etiquetas que no son versión, y
    ordena de mayor a menor sin confiar en el orden de la API. Vacío si la
    entrada no es una lista o no queda ninguna versión.
    """
    if not isinstance(publicaciones, list):
        return ""
    actual = actualizacion.version_como_tupla(version_actual)
    nueva = actualizacion.version_como_tupla(version_nueva)
    if actual is None or nueva is None:
        return ""
    elegidas = []
    for publicacion in publicaciones:
        if not isinstance(publicacion, dict):
            continue
        if publicacion.get("draft") or publicacion.get("prerelease"):
            continue
        tupla = actualizacion.version_como_tupla(publicacion.get("tag_name"))
        if tupla is None or not actual < tupla <= nueva:
            continue
        elegidas.append((tupla, publicacion))
    elegidas.sort(key=lambda elegida: elegida[0], reverse=True)
    return "\n\n".join(_texto_publicacion(publicacion)
                       for _version, publicacion in elegidas)


def consultar_con_novedades() -> actualizacion.PaqueteElegido | None:
    """Última release con las notas de todas las versiones salteadas.

    La lista de publicaciones solo se pide si hay versión nueva. Si no se
    puede consultar, devuelve el paquete tal cual, con las notas de la
    última versión.
    """
    paquete = actualizacion.consultar_ultima_version()
    if paquete is None:
        return None
    if not actualizacion.hay_version_nueva(APP_VERSION, paquete.version):
        return paquete
    try:
        solicitud = Request(
            URL_PUBLICACIONES,
            headers={"User-Agent": actualizacion.USER_AGENT})
        with urlopen(solicitud, timeout=actualizacion.TIEMPO_ESPERA) as respuesta:
            publicaciones = json.load(respuesta)
        notas = juntar_novedades(publicaciones, APP_VERSION, paquete.version)
    except (HTTPError, URLError, OSError, TypeError, ValueError):
        return paquete
    if not notas:
        return paquete
    return paquete._replace(notas=notas)
