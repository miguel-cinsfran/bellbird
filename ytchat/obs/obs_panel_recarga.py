"""Recarga de la fuente del panel en OBS cuando el panel vuelve a encenderse.

OBS carga la página del chat una sola vez. Si el panel estaba apagado, la
página de error del navegador no ejecuta el script y no reintenta nunca.
Pulsar «refreshnocache» sobre la fuente la vuelve a cargar con el puerto ya
abierto.
"""

from __future__ import annotations

from ytchat.core import diagnostico
from ytchat.obs import obs_activacion, obs_cliente, obs_panel

logger = diagnostico.obtener_logger(__name__)


def recargar_fuente_panel(crear_cliente=None, obs_abierto=None) -> bool:
    """Recarga la fuente del panel si OBS está abierto y la fuente existe.

    Devuelve True solo cuando se pulsó el botón de recarga. No avisa nada:
    es parte silenciosa del encendido del panel.
    """
    if obs_abierto is None:
        obs_abierto = obs_activacion.obs_esta_en_ejecucion
    if not obs_abierto():
        return False
    if crear_cliente is None:
        crear_cliente = lambda: obs_cliente.ClienteObs(
            obs_cliente.leer_ajustes())
    cliente = None
    try:
        cliente = crear_cliente()
        cliente.conectar()
        respuesta = cliente.pedir("GetInputList")
        entradas = respuesta.get("responseData", {}).get("inputs", ())
        fuente = next((entrada for entrada in entradas
                       if entrada.get("inputName") == obs_panel.NOMBRE_FUENTE
                       and entrada.get("inputKind") == obs_panel.TIPO_FUENTE),
                      None)
        if fuente is None:
            return False
        cliente.pedir("PressInputPropertiesButton", {
            "inputName": obs_panel.NOMBRE_FUENTE,
            "propertyName": "refreshnocache",
        })
        return True
    except Exception as exc:
        logger.debug("No se pudo recargar la fuente del panel en OBS: %s", exc)
        return False
    finally:
        if cliente is not None:
            try:
                cliente.cerrar()
            except Exception as exc:
                logger.debug("No se pudo cerrar la conexión con OBS: %s", exc)
