"""Qué se le pide a la API REST de Restream y cómo se interpreta.

La lista pública de plataformas se guarda en memoria: no cambia mientras la
app está abierta. Los canales se leen de forma tolerante porque todavía no
se vio una respuesta real. Ni el token ni la respuesta cruda se escriben en
el registro.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from bellbird.core.idioma import _

logger = logging.getLogger(__name__)

PLATAFORMAS = "https://api.restream.io/v2/platform/all"
CANALES = "https://api.restream.io/v2/user/channel/all"
PERFIL = "https://api.restream.io/v2/user/profile"
ELIMINAR_CANAL = "https://api.restream.io/v2/user/channels/{id}"
ESPERA = 15.0

# Restream escribe «Youtube» en su lista pública.
NOMBRES_PROPIOS = {"Youtube": "YouTube"}

_PLATAFORMAS = None


class ErrorApi(Exception):
    """No se pudieron leer los destinos de Restream."""

    def __init__(self):
        super().__init__(
            _("No se pudieron leer los destinos de Restream. "
              "Vuelve a intentarlo."))


@dataclass(frozen=True, slots=True)
class Canal:
    """Un canal de la cuenta, con su plataforma ya resuelta."""

    id: int
    plataforma_id: int
    plataforma: str
    nombre: str
    url: str
    activo: bool = True

    @property
    def texto(self) -> str:
        return f"{self.plataforma}: {self.nombre}"


@dataclass(frozen=True, slots=True)
class DatosCuenta:
    """El correo y el usuario que Restream da de la cuenta conectada."""

    correo: str
    usuario: str


def _entero(valor, defecto=None):
    if isinstance(valor, bool) or not isinstance(valor, int):
        return defecto
    return valor


def _texto(valor):
    return valor if isinstance(valor, str) else ""


def _pedir(cliente, url, cabeceras=None, metodo="GET"):
    try:
        if cliente is None:
            with httpx.Client() as propio:
                return propio.request(metodo, url, headers=cabeceras,
                                      timeout=ESPERA)
        return cliente.request(metodo, url, headers=cabeceras, timeout=ESPERA)
    except httpx.HTTPError:
        logger.warning("no se pudo hablar con la API de Restream")
        raise ErrorApi() from None


def _leer(respuesta):
    if respuesta.status_code != 200:
        logger.warning("la API de Restream respondió %s",
                       respuesta.status_code)
        raise ErrorApi()
    try:
        return respuesta.json()
    except ValueError:
        logger.warning("la API de Restream no devolvió JSON")
        raise ErrorApi() from None


def plataformas(cliente=None) -> dict:
    """Lista pública de plataformas como {id: nombre}."""
    global _PLATAFORMAS
    if _PLATAFORMAS is not None:
        return dict(_PLATAFORMAS)
    datos = _leer(_pedir(cliente, PLATAFORMAS))
    if not isinstance(datos, list):
        logger.warning("la lista de plataformas de Restream no es una lista")
        raise ErrorApi()
    mapa = {}
    for entrada in datos:
        if not isinstance(entrada, dict):
            continue
        identificador = _entero(entrada.get("id"))
        nombre = _texto(entrada.get("name"))
        if identificador is None or not nombre:
            continue
        mapa[identificador] = NOMBRES_PROPIOS.get(nombre, nombre)
    _PLATAFORMAS = mapa
    return dict(mapa)


def _plataforma_id(entrada):
    """El id de la plataforma, venga como `platformId` o `streamingPlatformId`."""
    identificador = _entero(entrada.get("platformId"))
    if identificador is None:
        identificador = _entero(entrada.get("streamingPlatformId"), 0)
    return identificador


def _nombre(entrada, url):
    return _texto(entrada.get("displayName")) or url


def _canal(entrada, mapa):
    if not isinstance(entrada, dict):
        return None
    identificador = _entero(entrada.get("id"))
    if identificador is None:
        return None
    plataforma_id = _plataforma_id(entrada)
    plataforma = mapa.get(plataforma_id)
    if not plataforma:
        plataforma = _("Plataforma {id}").format(id=plataforma_id)
    url = _texto(entrada.get("channelUrl")) or _texto(entrada.get("url"))
    nombre = _nombre(entrada, url)
    return Canal(
        id=identificador,
        plataforma_id=plataforma_id,
        plataforma=plataforma,
        nombre=nombre,
        url=url,
        activo=entrada.get("enabled") is not False,
    )


def canales(token, cliente=None) -> list[Canal]:
    """Canales de la cuenta, ordenados por plataforma y nombre."""
    mapa = plataformas(cliente)
    cabeceras = {"Authorization": f"Bearer {token}"}
    datos = _leer(_pedir(cliente, CANALES, cabeceras))
    if isinstance(datos, dict):
        datos = datos.get("channels")
    if not isinstance(datos, list):
        logger.warning("la lista de canales de Restream no es una lista")
        raise ErrorApi()
    leidos = []
    for entrada in datos:
        canal = _canal(entrada, mapa)
        if canal is not None:
            leidos.append(canal)
    leidos.sort(key=lambda canal: (canal.plataforma, canal.nombre))
    return leidos


def perfil(token, cliente=None) -> DatosCuenta:
    """Correo y usuario de la cuenta conectada."""
    cabeceras = {"Authorization": f"Bearer {token}"}
    datos = _leer(_pedir(cliente, PERFIL, cabeceras))
    if not isinstance(datos, dict):
        logger.warning("el perfil de Restream no es un objeto")
        raise ErrorApi()
    return DatosCuenta(
        correo=_texto(datos.get("email")),
        usuario=_texto(datos.get("username")),
    )


def eliminar_canal(token, identificador, cliente=None) -> None:
    """Elimina un canal de la cuenta. Cualquier respuesta fuera de 2xx falla."""
    cabeceras = {"Authorization": f"Bearer {token}"}
    url = ELIMINAR_CANAL.format(id=identificador)
    respuesta = _pedir(cliente, url, cabeceras, metodo="DELETE")
    if not 200 <= respuesta.status_code < 300:
        logger.warning("la API de Restream respondió %s al eliminar un canal",
                       respuesta.status_code)
        raise ErrorApi()
