"""Consultar y alternar las entradas de audio de OBS.

Las funciones reciben un cliente con `pedir(tipo, datos=None,
parada=None)` como `obs_captura` y no crean conexiones. La excepción es
`senal_microfono`, que abre su propia conexión corta con el websocket.
"""

from __future__ import annotations

from ytchat.core import diagnostico
from ytchat.obs import dispositivo_windows
from ytchat.obs import obs_audio
from ytchat.obs import obs_cliente

logger = diagnostico.obtener_logger(__name__)

TIPO_MICROFONO = "wasapi_input_capture"

# 1 << 16 habilita solo InputVolumeMeters en las suscripciones del websocket.
SUSCRIPCION_METROS = 1 << 16


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


def alternar_microfono(gestor, preferido) -> tuple:
    """Elige el micrófono, alterna su silencio y arma el anuncio.

    Devuelve `(texto, fuente, silenciado)` para que quien use el resultado
    pueda, además del anuncio, saber qué fuente quedó y en qué estado.
    """
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
    texto = obs_audio.frase_microfono(fuente, estado, nombre, predeterminado)
    return texto, fuente, estado


def _medir_eventos(fabrica, segundos) -> list | None:
    """Crea el cliente, conecta y escucha los medidores del websocket.
    Devuelve None si la medición no se pudo hacer; siempre cierra."""
    cliente = None
    try:
        cliente = fabrica()
        cliente.conectar()
        return cliente.escuchar("InputVolumeMeters", segundos)
    except Exception as exc:
        logger.debug("No se pudo medir la señal del micrófono: %s", exc)
        return None
    finally:
        if cliente is not None:
            try:
                cliente.cerrar()
            except Exception as exc:
                logger.debug("No se pudo cerrar la medición de OBS: %s", exc)


def senal_microfono(fuente, segundos=3.0, crear_cliente=None) -> bool | None:
    """Escucha el medidor de la fuente en OBS durante unos segundos y
    dice si entró señal. None si la medición no se puede hacer."""
    fabrica = crear_cliente or (
        lambda: obs_cliente.ClienteObs(
            obs_cliente.leer_ajustes(), suscripciones=SUSCRIPCION_METROS))
    eventos = _medir_eventos(fabrica, segundos)
    if eventos is None:
        return None
    try:
        return obs_audio.tiene_senal(eventos, fuente)
    except Exception as exc:
        logger.debug("No se pudo leer la medición del micrófono: %s", exc)
        return None


def _texto_del_atajo(preferido) -> tuple:
    """Crea y conecta el gestor del panel, alterna y rinde
    `(texto, fuente, silenciado)`; si OBS no responde, rinde su aviso."""
    from ytchat.obs.obs_panel import GestorPanelObs

    gestor = None
    try:
        gestor = GestorPanelObs()
        gestor.conectar()
        return alternar_microfono(gestor, preferido)
    except Exception:
        return ("OBS no responde. En OBS, menú Herramientas, Configuración "
                "del servidor WebSocket, activa el servidor.", "", True)
    finally:
        if gestor is not None:
            try:
                gestor.cerrar()
            except Exception as exc:
                logger.debug("No se pudo cerrar la conexión con OBS: %s", exc)


def microfono_por_atajo(preferido, avisar) -> None:
    """Alterna el micrófono desde el atajo, anuncia y si quedó activado
    mide la señal unos segundos para avisar si no entra nada."""
    texto, fuente, silenciado = _texto_del_atajo(preferido)
    avisar(texto, "")
    if fuente and not silenciado and obs_audio.es_microfono(fuente):
        if senal_microfono(fuente) is False:
            avisar(obs_audio.TEXTO_SIN_SENAL, "microfono_sin_senal")


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
