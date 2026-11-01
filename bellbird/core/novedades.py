"""Qué novedades se muestran al actualizar, sin interfaz.

Arma el texto de la ventana con las notas de todas las versiones
publicadas entre la instalada y la nueva, para que quien salta varias
versiones se entere de lo que trajo cada una. El paquete a instalar sale
del canal de actualizaciones: la última release en Estable o la mayor
publicación en Beta.
"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bellbird.core import actualizacion
from bellbird.core import canal_app
from bellbird.core import versiones
from bellbird.core.config import APP_VERSION
from bellbird.core.idioma import _


URL_PUBLICACIONES = canal_app.URL_PUBLICACIONES


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
                     version_nueva: str, incluir_betas: bool = False) -> str:
    """Markdown con las versiones publicadas entre la instalada y la nueva.

    Deja fuera borradores, etiquetas que no son versión y, salvo
    `incluir_betas`, los prereleases. Ordena de mayor a menor.
    """
    publicaciones = publicaciones if isinstance(publicaciones, list) else []
    desde = versiones.orden_version(
        versiones.version_como_tupla(version_actual))
    hasta = versiones.orden_version(
        versiones.version_como_tupla(version_nueva))
    if desde is None or hasta is None:
        return ""
    elegidas = []
    for publicacion in publicaciones:
        if not isinstance(publicacion, dict) or publicacion.get("draft"):
            continue
        if publicacion.get("prerelease") and not incluir_betas:
            continue
        orden = versiones.orden_version(
            versiones.version_como_tupla(publicacion.get("tag_name")))
        if orden is not None and desde < orden <= hasta:
            elegidas.append((orden, publicacion))
    elegidas.sort(key=lambda elegida: elegida[0], reverse=True)
    return "\n\n".join(_texto_publicacion(publicacion)
                       for _orden, publicacion in elegidas)


def consultar_con_novedades() -> actualizacion.PaqueteElegido | None:
    """Paquete del canal con las notas de todas las versiones salteadas.

    En Beta la publicación sale de la lista y las notas incluyen los
    prelanzamientos; en Estable se consulta la última release. La lista solo
    se pide si hay versión nueva y, si falla, quedan las notas de la última.
    """
    incluir_betas = canal_app.canal_guardado() == "beta"
    paquete = (canal_app.consultar_ultima_beta() if incluir_betas
               else actualizacion.consultar_ultima_version())
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
        notas = juntar_novedades(publicaciones, APP_VERSION, paquete.version,
                                 incluir_betas=incluir_betas)
    except (HTTPError, URLError, OSError, TypeError, ValueError):
        return paquete
    if not notas:
        return paquete
    return paquete._replace(notas=notas)
