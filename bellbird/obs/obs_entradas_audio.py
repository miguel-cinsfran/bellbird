"""Consultar y alternar las entradas de audio de OBS.

Las funciones reciben un cliente con `pedir(tipo, datos=None,
parada=None)` como `obs_captura` y no crean conexiones. La excepción es
`senal_microfono`, que abre su propia conexión corta con el websocket.
"""

from __future__ import annotations

from bellbird.core import diagnostico
from bellbird.core.idioma import N_, _
from bellbird.obs import dispositivo_windows
from bellbird.obs import obs_audio
from bellbird.obs import obs_cliente

logger = diagnostico.obtener_logger(__name__)

TIPO_MICROFONO = "wasapi_input_capture"

# 1 << 16 habilita solo InputVolumeMeters en las suscripciones del websocket.
SUSCRIPCION_METROS = 1 << 16


def _datos(cliente, tipo, datos=None, parada=None):
    respuesta = cliente.pedir(tipo, datos, parada=parada)
    return respuesta.get("responseData", {})


def entradas_audio(cliente, parada=None) -> tuple:
    entradas = _datos(cliente, "GetInputList", parada=parada).get("inputs", ())
    pares = []
    for entrada in entradas:
        nombre = entrada.get("inputName", "")
        if not nombre:
            continue
        caps = entrada.get("inputKindCaps")
        if caps is not None and not (int(caps) & (1 << 1)):
            continue
        pares.append((nombre, entrada.get("inputKind", "") or ""))
    return tuple(pares)


def microfonos(cliente, parada=None) -> tuple:
    """Nombres de las entradas de micrófono, en el orden de OBS."""
    return tuple(nombre for nombre, tipo in entradas_audio(cliente, parada)
                 if tipo == TIPO_MICROFONO)


def dispositivos(cliente, fuente, parada=None) -> tuple:
    """Pares (nombre, valor) de dispositivos de la fuente y su actual.

    Sin los de nombre vacío. El actual es "" si OBS no trae ninguno;
    vacío significa el predeterminado, "default".
    """
    ajustes = _datos(cliente, "GetInputSettings", {"inputName": fuente},
                     parada)
    actual = (ajustes.get("inputSettings") or {}).get("device_id", "") or ""
    items = _datos(
        cliente, "GetInputPropertiesListPropertyItems",
        {"inputName": fuente, "propertyName": "device_id"},
        parada).get("propertyItems", ())
    pares = tuple((item.get("itemName", ""), item.get("itemValue", ""))
                  for item in items if item.get("itemName", ""))
    return (pares, actual)


def cambiar_dispositivo(cliente, fuente, valor, parada=None) -> None:
    """Cambia el dispositivo de la fuente sin tocar silencio ni volumen."""
    cliente.pedir("SetInputSettings",
                  {"inputName": fuente, "inputSettings": {"device_id": valor},
                   "overlay": True}, parada)


def microfono_especial(cliente, parada=None) -> str:
    try:
        return _datos(cliente, "GetSpecialInputs", parada=parada).get("mic1", "") or ""
    except Exception:
        return ""


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


AVISO_SIN_MICROFONO = N_("OBS no tiene ningún micrófono. Elige uno en "
                         "Preferencias, categoría Transmisión, Micrófono de OBS.")


def alternar_microfono(gestor, preferido) -> tuple:
    """Elige el micrófono, alterna su silencio y arma el anuncio."""
    fuente = obs_audio.elegir_microfono(
        gestor.entradas_audio(), preferido, gestor.microfono_especial())
    if not fuente:
        return (_(AVISO_SIN_MICROFONO), "", False)
    estado = gestor.alternar_silencio(fuente)
    nombre, predeterminado = "", False
    try:
        nombre, predeterminado = gestor.dispositivo(
            fuente, dispositivo_windows.microfono_predeterminado)
    except Exception as exc:
        # Un fallo al leer el dispositivo no convierte esto en un fallo
        # de OBS: se anuncia el micrófono como antes.
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
    from bellbird.obs.obs_panel import GestorPanelObs

    gestor = None
    try:
        gestor = GestorPanelObs()
        gestor.conectar()
        return alternar_microfono(gestor, preferido)
    except Exception:
        return (_("OBS no responde. En OBS, menú Herramientas, "
                  "Configuración del servidor WebSocket, activa el servidor."),
                "", True)
    finally:
        if gestor is not None:
            try:
                gestor.cerrar()
            except Exception as exc:
                logger.debug("No se pudo cerrar la conexión con OBS: %s", exc)


def estado_microfono(preferido) -> bool | None:
    """Silencio actual del micrófono, o None sin OBS o sin micrófono."""
    from bellbird.obs.obs_panel import GestorPanelObs
    gestor = None
    try:
        gestor = GestorPanelObs()
        gestor.conectar()
        fuente = obs_audio.elegir_microfono(
            gestor.entradas_audio(), preferido, gestor.microfono_especial())
        if not fuente:
            return None
        return gestor.silenciada(fuente)
    except Exception:
        return None
    finally:
        if gestor is not None:
            try:
                gestor.cerrar()
            except Exception as exc:
                logger.debug("No se pudo cerrar la conexión con OBS: %s", exc)


def microfono_por_atajo(preferido, avisar, al_estado=None) -> None:
    """Alterna el micrófono desde el atajo, anuncia y si quedó activado
    mide la señal unos segundos para avisar si no entra nada."""
    texto, fuente, silenciado = _texto_del_atajo(preferido)
    avisar(texto, "")
    if al_estado is not None:
        al_estado(None if not fuente else silenciado)
    if fuente and not silenciado and obs_audio.es_microfono(fuente):
        if senal_microfono(fuente) is False:
            avisar(_(obs_audio.TEXTO_SIN_SENAL), "microfono_sin_senal")


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
