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

from guyrapu.core.idioma import _
from guyrapu.restream import eventos as eventos_restream

logger = logging.getLogger(__name__)

PLATAFORMAS = "https://api.restream.io/v2/platform/all"
CANALES = "https://api.restream.io/v2/user/channel/all"
PERFIL = "https://api.restream.io/v2/user/profile"
CANAL = "https://api.restream.io/v2/user/channel/{id}"
CLAVE_CUENTA = "https://api.restream.io/v2/user/streamKey"
META_CANAL = "https://api.restream.io/v2/user/channel-meta/{id}"
CANALES_USUARIO = "https://api.restream.io/v2/user/channels"
ELIMINAR_CANAL = CANALES_USUARIO + "/{id}"
SERVIDOR_RTMP = "rtmp://live.restream.io/live"
EVENTOS = {
    eventos_restream.TIPO_PROXIMOS:
        "https://api.restream.io/v2/user/events/upcoming?source=2",
    eventos_restream.TIPO_EN_DIRECTO:
        "https://api.restream.io/v2/user/events/in-progress",
    eventos_restream.TIPO_HISTORIAL:
        "https://api.restream.io/v2/user/events/history?page=1&limit=50",
}
ESTADISTICAS = "https://api.restream.io/v2/user/events/{id}/analytics/viewers"
ESPERA = 15.0

# Restream escribe «Youtube» en su lista pública.
NOMBRES_PROPIOS = {"Youtube": "YouTube"}

_PLATAFORMAS = None


class ErrorApi(Exception):
    """No se pudo completar la operación con Restream."""

    def __init__(self, mensaje=None):
        if mensaje is None:
            mensaje = _("No se pudieron leer los destinos de Restream. "
                        "Vuelve a intentarlo.")
        super().__init__(mensaje)


@dataclass(frozen=True, slots=True)
class Canal:
    """Un canal de la cuenta, con su plataforma ya resuelta."""

    id: int
    plataforma_id: int
    plataforma: str
    nombre: str
    url: str
    activo: bool = True
    identificador: str = ""

    @property
    def texto(self) -> str:
        return f"{self.plataforma}: {self.nombre}"


@dataclass(frozen=True, slots=True)
class DatosCuenta:
    """El correo y el usuario que Restream da de la cuenta conectada."""

    correo: str
    usuario: str


@dataclass(frozen=True, slots=True, repr=False)
class ClaveCuenta:
    """La clave de transmisión de la cuenta, con su servidor RTMP."""

    clave: str
    servidor: str = SERVIDOR_RTMP

    def __repr__(self) -> str:
        return f"{type(self).__name__}(servidor={self.servidor!r}, " \
               "clave=<oculta>)"


@dataclass(frozen=True, slots=True)
class MetaCanal:
    """El título y la descripción de un canal."""

    titulo: str
    descripcion: str


def _entero(valor, defecto=None):
    if isinstance(valor, bool) or not isinstance(valor, int):
        return defecto
    return valor


def _texto(valor):
    return valor if isinstance(valor, str) else ""


def _pedir(cliente, url, cabeceras=None, metodo="GET", cuerpo=None,
           mensaje=None):
    opciones = {"headers": cabeceras, "timeout": ESPERA}
    if cuerpo is not None:
        opciones["json"] = cuerpo
    try:
        if cliente is None:
            with httpx.Client() as propio:
                return propio.request(metodo, url, **opciones)
        return cliente.request(metodo, url, **opciones)
    except httpx.HTTPError:
        logger.warning("no se pudo hablar con la API de Restream")
        raise ErrorApi(mensaje) from None


def _leer(respuesta, mensaje=None, aceptar_2xx=False):
    validas = range(200, 300) if aceptar_2xx else (200,)
    if respuesta.status_code not in validas:
        logger.warning("la API de Restream respondió %s",
                       respuesta.status_code)
        raise ErrorApi(mensaje)
    try:
        return respuesta.json()
    except ValueError:
        logger.warning("la API de Restream no devolvió JSON")
        raise ErrorApi(mensaje) from None


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
    return Canal(
        id=identificador,
        plataforma_id=plataforma_id,
        plataforma=plataforma,
        nombre=_nombre(entrada, url),
        url=url,
        activo=entrada.get("enabled") is not False,
        identificador=_texto(entrada.get("identifier")),
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


def clave_cuenta(token, cliente=None) -> ClaveCuenta:
    """Servidor y clave de transmisión de la cuenta."""
    mensaje = _("No se pudo leer la clave de transmisión de Restream. "
                "Vuelve a intentarlo.")
    cabeceras = {"Authorization": f"Bearer {token}"}
    datos = _leer(_pedir(cliente, CLAVE_CUENTA, cabeceras, mensaje=mensaje),
                  mensaje)
    if not isinstance(datos, dict):
        logger.warning("la clave de Restream no es un objeto")
        raise ErrorApi(mensaje)
    clave = _texto(datos.get("streamKey"))
    if not clave:
        logger.warning("la API de Restream no devolvió la clave de transmisión")
        raise ErrorApi(mensaje)
    return ClaveCuenta(clave=clave)


def activar_canal(token, identificador, activo, cliente=None) -> None:
    """Activa o desactiva un canal de la cuenta."""
    if activo:
        mensaje = _("No se pudo activar el destino. Vuelve a intentarlo.")
    else:
        mensaje = _("No se pudo desactivar el destino. Vuelve a intentarlo.")
    cabeceras = {"Authorization": f"Bearer {token}"}
    url = CANAL.format(id=identificador)
    respuesta = _pedir(cliente, url, cabeceras, metodo="PATCH",
                       cuerpo={"active": bool(activo)}, mensaje=mensaje)
    if not 200 <= respuesta.status_code < 300:
        logger.warning("la API de Restream respondió %s al activar un canal",
                       respuesta.status_code)
        raise ErrorApi(mensaje)


def leer_meta(token, identificador, cliente=None) -> MetaCanal:
    """Título y descripción de un canal de la cuenta."""
    mensaje = _("No se pudo leer el título del destino. "
                "Vuelve a intentarlo.")
    cabeceras = {"Authorization": f"Bearer {token}"}
    url = META_CANAL.format(id=identificador)
    datos = _leer(_pedir(cliente, url, cabeceras, mensaje=mensaje), mensaje)
    if not isinstance(datos, dict):
        logger.warning("la meta de Restream no es un objeto")
        raise ErrorApi(mensaje)
    return MetaCanal(
        titulo=_texto(datos.get("title")),
        descripcion=_texto(datos.get("description")),
    )


def cambiar_meta(token, identificador, titulo, descripcion,
                 cliente=None) -> None:
    """Cambia el título y la descripción de un canal de la cuenta."""
    mensaje = _("No se pudo cambiar el título del destino. "
                "Vuelve a intentarlo.")
    cabeceras = {"Authorization": f"Bearer {token}"}
    url = META_CANAL.format(id=identificador)
    respuesta = _pedir(
        cliente, url, cabeceras, metodo="PATCH",
        cuerpo={"title": titulo, "description": descripcion},
        mensaje=mensaje)
    if not 200 <= respuesta.status_code < 300:
        logger.warning("la API de Restream respondió %s al cambiar la meta",
                       respuesta.status_code)
        raise ErrorApi(mensaje)


def _campos_canal_manual(plataforma_id, nombre, servidor, clave):
    campos = {"platformId": plataforma_id}
    for campo, valor in (("displayName", nombre), ("streamUrl", servidor),
                         ("streamKey", clave)):
        texto = _texto(valor).strip()
        if texto:
            campos[campo] = texto
    return campos


def agregar_canal_manual(token, plataforma_id, nombre, servidor, clave,
                         cliente=None) -> Canal:
    """Agrega un canal manual y devuelve el canal creado."""
    mensaje = _("No se pudo agregar el destino. Vuelve a intentarlo.")
    try:
        mapa = plataformas(cliente)
    except ErrorApi:
        raise ErrorApi(mensaje) from None
    campos = _campos_canal_manual(plataforma_id, nombre, servidor, clave)
    cabeceras = {"Authorization": f"Bearer {token}"}
    respuesta = _pedir(cliente, CANALES_USUARIO, cabeceras, metodo="POST",
                       cuerpo=campos, mensaje=mensaje)
    datos = _leer(respuesta, mensaje, aceptar_2xx=True)
    canal = _canal(datos, mapa)
    if canal is None:
        logger.warning("la API de Restream no devolvió el canal creado")
        raise ErrorApi(mensaje)
    return canal


def eventos(token, tipo, cliente=None) -> list:
    """Eventos de Restream del tipo pedido, ya interpretados."""
    cabeceras = {"Authorization": f"Bearer {token}"}
    datos = _leer(_pedir(cliente, EVENTOS[tipo], cabeceras))
    return eventos_restream.leer_eventos(datos, tipo)


def estadisticas(token, identificador, cliente=None):
    """Estadísticas de espectadores y tiempo visto de un evento."""
    cabeceras = {"Authorization": f"Bearer {token}"}
    url = ESTADISTICAS.format(id=identificador)
    datos = _leer(_pedir(cliente, url, cabeceras))
    return eventos_restream.leer_estadisticas(datos)
