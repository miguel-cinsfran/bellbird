"""Monitorización de audio del micrófono de OBS, para oírse por los auriculares.

Activa y devuelve el tipo de monitorización de la fuente del micrófono. La
monitorización de OBS suena por el dispositivo de monitorización configurado
en OBS y no cambia lo que sale en la transmisión.
"""

from __future__ import annotations

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.obs import obs_cliente

logger = diagnostico.obtener_logger(__name__)

NINGUNA = "OBS_MONITORING_TYPE_NONE"
SOLO_MONITOR = "OBS_MONITORING_TYPE_MONITOR_ONLY"
MONITOR_Y_SALIDA = "OBS_MONITORING_TYPE_MONITOR_AND_OUTPUT"


def _cliente_por_defecto():
    return obs_cliente.ClienteObs(obs_cliente.leer_ajustes())


def _con_cliente(accion, crear_cliente=None):
    fabrica = crear_cliente or _cliente_por_defecto
    cliente = None
    try:
        cliente = fabrica()
        cliente.conectar()
        return accion(cliente)
    finally:
        if cliente is not None:
            try:
                cliente.cerrar()
            except Exception as exc:
                logger.debug("No se pudo cerrar la conexión de la "
                             "monitorización del micrófono: %s", exc)


def _tipo_actual(cliente, fuente):
    respuesta = cliente.pedir(
        "GetInputAudioMonitorType", {"inputName": fuente})
    return respuesta.get("responseData", {}).get("monitorType", NINGUNA)


def _fijar(cliente, fuente, tipo):
    cliente.pedir("SetInputAudioMonitorType",
                  {"inputName": fuente, "monitorType": tipo})


def activar(fuente, crear_cliente=None):
    """Pone la fuente en monitorizar y emitir y devuelve el tipo anterior."""

    def accion(cliente):
        anterior = _tipo_actual(cliente, fuente)
        if anterior != MONITOR_Y_SALIDA:
            _fijar(cliente, fuente, MONITOR_Y_SALIDA)
        return anterior

    return _con_cliente(accion, crear_cliente)


def restaurar(fuente, anterior, crear_cliente=None):
    """Devuelve la fuente al tipo que tenía antes de activar la escucha."""

    def accion(cliente):
        if anterior != MONITOR_Y_SALIDA:
            _fijar(cliente, fuente, anterior)

    return _con_cliente(accion, crear_cliente)


def frase_activada(anterior):
    """El anuncio al activar la escucha, con el aviso del acople si hace falta."""
    if anterior == MONITOR_Y_SALIDA:
        return _("La monitorización ya estaba activada en OBS.")
    return _("Monitorización activada. Te oyes por el dispositivo de "
             "monitorización de OBS. Usa auriculares para evitar acople.")


def frase_desactivada(anterior):
    """El anuncio al desactivar, según el tipo de monitorización anterior."""
    if anterior == NINGUNA:
        return _("Monitorización desactivada.")
    return _("Monitorización restablecida como estaba en OBS.")
