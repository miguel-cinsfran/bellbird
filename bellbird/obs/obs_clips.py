"""Búfer de repetición de OBS: prepararlo, ponerlo en marcha y guardar clips.

Habla con OBS a través de un cliente con `pedir`, como `obs_grabacion`, y
no importa wx ni conoce los anuncios. Medido el 03/11/2026 con OBS 33:
cambiar `RecRB` y `RecRBTime` no alcanza, hay que salir del perfil y volver
para que `StartReplayBuffer` lo acepte. Nunca se cambia de perfil con una
salida activa.
"""

from __future__ import annotations

import configparser
import time
import uuid
from dataclasses import dataclass

from bellbird.core import diagnostico, ini_tipado, paths
from bellbird.core.idioma import N_, _
from bellbird.obs import obs_cliente

logger = diagnostico.obtener_logger(__name__)

SEGUNDOS_VALIDOS = (30, 60)
SEGUNDOS_POR_DEFECTO = 30
_CATEGORIAS = {"Simple": "SimpleOutput", "Advanced": "AdvOut"}

# El archivo tarda en escribirse después de SaveReplayBuffer; se consulta
# hasta que OBS devuelve la ruta, sin adivinar una espera fija.
INTERVALO_CLIP = 0.2
LIMITE_CLIP = 5.0

GUARDAR = "guardar"
PREPARAR = "preparar"
INICIAR = "iniciar"
RECHAZAR = "rechazar"

MENSAJE_DESACTIVADOS = N_("Los clips están desactivados en Preferencias.")
MENSAJE_NO_DISPONIBLE = N_(
    "OBS no ofrece clips con la calidad de grabación de este perfil.")
MENSAJE_SALIDA_ACTIVA = N_(
    "Los clips se preparan antes de transmitir o grabar. Detén el directo "
    "y la grabación y vuelve a intentarlo.")
MENSAJE_CLIP_GUARDADO = N_("Clip guardado: {archivo}.")
MENSAJE_CLIP_GUARDADO_POR = N_("Clip guardado por {autor}: {archivo}.")
MENSAJE_CLIPS_LISTOS = N_(
    "Clips listos: desde ahora se guardan los últimos {segundos} segundos.")
MENSAJE_SIN_ARCHIVO = N_("OBS no devolvió el archivo del clip.")


@dataclass(frozen=True, slots=True)
class EstadoClips:
    salida_activa: bool
    buffer_activo: bool
    preparado: bool
    soportado: bool
    conocido: bool


def leer_segundos(ruta=None) -> int:
    """La duración elegida en Preferencias; 0 si los clips están apagados."""
    try:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(ruta or paths.config_ini(), encoding="utf-8")
        segundos = ini_tipado.leer_entero(
            parser, "transmision", "clips", lo=0, hi=60)
    except Exception as error:
        logger.debug("no se pudo leer la duración de los clips: %s", error)
        return SEGUNDOS_POR_DEFECTO
    return segundos if segundos in (0, *SEGUNDOS_VALIDOS) else SEGUNDOS_POR_DEFECTO


def decidir(salida_activa, buffer_activo, preparado) -> str:
    """Qué hacer al pulsar Guardar clip, solo con los estados leídos."""
    if buffer_activo:
        return GUARDAR
    if not preparado and salida_activa:
        return RECHAZAR
    return INICIAR if preparado else PREPARAR


def soporta_buffer(modo, calidad, codificador) -> bool:
    """Si el perfil actual admite el búfer, según la calidad de grabación."""
    if modo not in _CATEGORIAS:
        return False
    if modo == "Simple":
        return str(calidad).strip().lower() != "lossless"
    return str(codificador).strip().lower() != "ffmpeg"


def _datos(respuesta):
    return (respuesta or {}).get("responseData", respuesta or {})


def _parametro(cliente, categoria, nombre, parada=None) -> str:
    respuesta = cliente.pedir(
        "GetProfileParameter",
        {"parameterCategory": categoria, "parameterName": nombre},
        parada=parada)
    datos = _datos(respuesta)
    valor = datos.get("parameterValue")
    if not valor:
        valor = datos.get("defaultParameterValue")
    return str(valor or "")


def _activo(cliente, tipo, parada=None) -> bool:
    return bool(_datos(cliente.pedir(tipo, parada=parada)).get("outputActive"))


def _buffer_activo(cliente, parada=None) -> bool:
    """El búfer apagado hace fallar la consulta; eso significa apagado."""
    try:
        return _activo(cliente, "GetReplayBufferStatus", parada)
    except obs_cliente.ObsError as error:
        logger.debug("OBS no informó el búfer, se toma como apagado: %s",
                     error)
        return False


def _leer_perfil(cliente, parada=None):
    """Modo, calidad de grabación y parámetros del búfer del perfil."""
    modo = _parametro(cliente, "Output", "Mode", parada)
    calidad = codificador = rb = rb_time = ""
    categoria = _CATEGORIAS.get(modo)
    if categoria == "SimpleOutput":
        calidad = _parametro(cliente, categoria, "RecQuality", parada)
    elif categoria == "AdvOut":
        codificador = _parametro(cliente, categoria, "RecEncoder", parada)
    if categoria is not None:
        rb = _parametro(cliente, categoria, "RecRB", parada)
        rb_time = _parametro(cliente, categoria, "RecRBTime", parada)
    return modo, calidad, codificador, rb, rb_time


def _mismos_segundos(valor, segundos) -> bool:
    try:
        return int(float(str(valor).strip())) == int(segundos)
    except (TypeError, ValueError):
        return False


def leer_estado(cliente, segundos, parada=None) -> EstadoClips:
    """El estado de salida, del búfer y del perfil, en una sola lectura."""
    if not callable(getattr(cliente, "pedir", None)):
        return EstadoClips(False, False, False, False, False)
    modo, calidad, codificador, rb, rb_time = _leer_perfil(cliente, parada)
    conocido = modo in _CATEGORIAS
    return EstadoClips(
        salida_activa=(_activo(cliente, "GetStreamStatus", parada)
                       or _activo(cliente, "GetRecordStatus", parada)),
        buffer_activo=_buffer_activo(cliente, parada),
        preparado=(conocido and str(rb).strip().lower() == "true"
                   and _mismos_segundos(rb_time, segundos)),
        soportado=soporta_buffer(modo, calidad, codificador),
        conocido=conocido)


def _cambiar_y_volver(cliente, parada=None) -> None:
    """Sale del perfil y vuelve para que OBS cargue los parámetros nuevos."""
    datos = _datos(cliente.pedir("GetProfileList", parada=parada))
    actual = str(datos.get("currentProfileName") or "")
    perfiles = [str(nombre) for nombre in (datos.get("profiles") or [])]
    otro = next((nombre for nombre in perfiles if nombre != actual), "")
    temporal = ""
    if not otro:
        temporal = "Bellbird " + uuid.uuid4().hex[:8]
        cliente.pedir("CreateProfile", {"profileName": temporal}, parada)
        otro = temporal
    cliente.pedir("SetCurrentProfile", {"profileName": otro}, parada)
    cliente.pedir("SetCurrentProfile", {"profileName": actual}, parada)
    if temporal:
        cliente.pedir("RemoveProfile", {"profileName": temporal}, parada)


def iniciar(cliente, parada=None) -> None:
    """Pone en marcha el búfer ya preparado."""
    cliente.pedir("StartReplayBuffer", parada=parada)


def preparar(cliente, segundos, parada=None) -> None:
    """Deja el perfil con el búfer de la duración pedida y lo pone en marcha."""
    modo, calidad, codificador, _rb, _rb_time = _leer_perfil(cliente, parada)
    if not soporta_buffer(modo, calidad, codificador):
        raise obs_cliente.ObsError(_(MENSAJE_NO_DISPONIBLE))
    if (_activo(cliente, "GetStreamStatus", parada)
            or _activo(cliente, "GetRecordStatus", parada)):
        raise obs_cliente.ObsError(_(MENSAJE_SALIDA_ACTIVA))
    categoria = _CATEGORIAS[modo]
    for nombre, valor in (("RecRB", "true"),
                          ("RecRBTime", str(int(segundos)))):
        cliente.pedir(
            "SetProfileParameter",
            {"parameterCategory": categoria, "parameterName": nombre,
             "parameterValue": valor},
            parada)
    _cambiar_y_volver(cliente, parada)
    iniciar(cliente, parada)


def _ruta_guardada(cliente, parada=None, tolerar_error=False) -> str:
    try:
        datos = _datos(cliente.pedir("GetLastReplayBufferReplay",
                                     parada=parada))
    except obs_cliente.ObsError as error:
        if not tolerar_error:
            raise
        logger.debug("OBS todavía no tiene un clip guardado: %s", error)
        return ""
    return str(datos.get("savedReplayPath") or "")


def guardar(cliente, parada=None, dormir=time.sleep, reloj=time.monotonic,
            limite=LIMITE_CLIP, intervalo=INTERVALO_CLIP) -> str:
    """Guarda el clip y devuelve su ruta cuando OBS termina de escribirlo."""
    anterior = _ruta_guardada(cliente, parada, tolerar_error=True)
    cliente.pedir("SaveReplayBuffer", parada=parada)
    inicio = reloj()
    while True:
        try:
            ruta = _ruta_guardada(cliente, parada)
        except obs_cliente.ObsError as error:
            logger.debug("OBS todavía no devolvió el clip: %s", error)
            ruta = ""
        if ruta and ruta != anterior:
            return ruta
        if reloj() - inicio >= limite:
            raise obs_cliente.ObsError(_(MENSAJE_SIN_ARCHIVO))
        dormir(intervalo)


def _avisar_fallo(al_fallar, error) -> None:
    logger.debug("los clips no se prepararon: %s", error)
    if al_fallar is None:
        return
    try:
        al_fallar(error)
    except Exception as error_aviso:
        logger.debug("no se pudo anunciar el fallo de los clips: %s",
                     error_aviso)


def preparar_para_directo(cliente, segundos, al_preparar=None,
                          al_fallar=None, parada=None) -> str:
    """Prepara el búfer al iniciar el directo, sin poder cortarlo.

    Los modos que este código no conoce se dejan en paz: un doble o una
    versión distinta de OBS no deben sonar a error.
    """
    if not segundos:
        return "desactivado"
    if not callable(getattr(cliente, "pedir", None)):
        return "sin_obs"
    try:
        estado = leer_estado(cliente, segundos, parada)
    except Exception as error:
        logger.debug("no se pudo leer el búfer de clips: %s", error)
        return "error"
    if not estado.conocido:
        return "sin_datos"
    if not estado.soportado:
        _avisar_fallo(al_fallar, obs_cliente.ObsError(
            _(MENSAJE_NO_DISPONIBLE)))
        return "no_disponible"
    if estado.buffer_activo:
        return "listo"
    if estado.preparado:
        try:
            iniciar(cliente, parada)
        except Exception as error:
            _avisar_fallo(al_fallar, error)
            return "error"
        return "listo"
    if estado.salida_activa:
        _avisar_fallo(al_fallar, obs_cliente.ObsError(
            _(MENSAJE_SALIDA_ACTIVA)))
        return "no_preparado"
    if al_preparar is not None:
        try:
            al_preparar()
        except Exception as error:
            logger.debug("no se pudo anunciar la preparación de los clips: %s",
                         error)
    try:
        preparar(cliente, segundos, parada)
    except Exception as error:
        _avisar_fallo(al_fallar, error)
        return "error"
    return "preparado"
