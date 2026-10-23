"""Consultar y alternar las entradas de audio de OBS.

Recibe un cliente con `pedir(tipo, datos=None, parada=None)` como
`obs_captura` y no crea conexiones.
"""

from __future__ import annotations

from ytchat.core import diagnostico
from ytchat.obs import dispositivo_windows
from ytchat.obs import obs_audio

logger = diagnostico.obtener_logger(__name__)

TIPO_MICROFONO = "wasapi_input_capture"


def _datos(cliente, tipo, datos=None, parada=None):
    respuesta = cliente.pedir(tipo, datos, parada=parada)
    return respuesta.get("responseData", {})


def fuentes_audio(cliente, parada=None) -> tuple:
    entradas = _datos(cliente, "GetInputList", parada=parada).get("inputs", ())
    fuentes = []
    for entrada in entradas:
        nombre = entrada.get("inputName", "")
        if not nombre:
            continue
        try:
            silenciada(cliente, nombre, parada)
        except Exception:
            continue
        fuentes.append(nombre)
    return tuple(fuentes)


def silenciada(cliente, fuente, parada=None) -> bool:
    datos = _datos(cliente, "GetInputMute", {"inputName": fuente}, parada)
    return bool(datos.get("inputMuted", False))


def alternar_silencio(cliente, fuente, parada=None) -> bool:
    datos = _datos(cliente, "ToggleInputMute", {"inputName": fuente}, parada)
    return bool(datos.get("inputMuted", False))


def alternar_microfono(gestor, preferido) -> str:
    """Elige el micrófono, alterna su silencio y arma el anuncio."""
    fuente = obs_audio.elegir_microfono(gestor.fuentes_audio(), preferido)
    estado = gestor.alternar_silencio(fuente) if fuente else False
    nombre, predeterminado = "", False
    if fuente and not estado:
        try:
            nombre, predeterminado = gestor.dispositivo(
                fuente, dispositivo_windows.microfono_predeterminado)
        except Exception as exc:
            # Un fallo al leer el dispositivo no convierte esto en un fallo
            # de OBS: se anuncia el micrófono activado, como antes.
            logger.debug("No se pudo saber el dispositivo del micrófono: %s", exc)
            nombre, predeterminado = "", False
    return obs_audio.frase_microfono(fuente, estado, nombre, predeterminado)


def microfono_por_atajo(preferido, avisar) -> None:
    """Alterna el micrófono desde el atajo y entrega el anuncio."""
    from ytchat.obs.obs_panel import GestorPanelObs

    gestor = None
    try:
        gestor = GestorPanelObs()
        gestor.conectar()
        texto = alternar_microfono(gestor, preferido)
    except Exception:
        texto = ("OBS no responde. En OBS, menú Herramientas, Configuración "
                 "del servidor WebSocket, activa el servidor.")
    finally:
        if gestor is not None:
            try:
                gestor.cerrar()
            except Exception as exc:
                logger.debug("No se pudo cerrar la conexión con OBS: %s", exc)
    avisar(texto, "")


def dispositivo(cliente, fuente, predeterminado, parada=None) -> tuple:
    """Nombre del dispositivo de la fuente y si es el predeterminado.

    El segundo valor es verdadero cuando OBS usa el predeterminado de Windows,
    aunque no se haya podido leer su nombre.
    """
    ajustes = _datos(cliente, "GetInputSettings", {"inputName": fuente}, parada)
    if ajustes.get("inputKind", "") != TIPO_MICROFONO:
        return "", False
    identificador = (ajustes.get("inputSettings") or {}).get("device_id", "")
    if not identificador or identificador == "default":
        return predeterminado(), True
    items = _datos(
        cliente, "GetInputPropertiesListPropertyItems",
        {"inputName": fuente, "propertyName": "device_id"},
        parada).get("propertyItems", ())
    for item in items:
        if item.get("itemValue") == identificador:
            return item.get("itemName", ""), False
    return "", False
