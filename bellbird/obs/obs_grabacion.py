"""Grabación que arranca y termina junto con la transmisión.

La app no guarda el estado entre sesiones: el supervisor recibe la casilla
desde `frame._config`, y el disco lo lee solo la revisión previa, porque la
ventana Transmisión y el botón no conocen la configuración. El estado de si
esta grabación la empezó la app queda en la instancia que se engancha al
supervisor.
"""

from __future__ import annotations

import configparser
import time

from bellbird.core import diagnostico, ini_tipado, paths
from bellbird.core.idioma import N_, _

logger = diagnostico.obtener_logger(__name__)

AVISO_CODIFICADOR = N_(
    "El perfil de OBS graba con un codificador propio: transmitir y grabar "
    "a la vez carga el doble el equipo.")
FALLO_GRABACION = N_(
    "La transmisión empezó, pero no se pudo iniciar la grabación.")
FALLO_PAUSA = N_(
    "OBS no pausó la grabación: este perfil puede no permitirlo.")
FALLO_REANUDAR = N_("OBS no reanudó la grabación.")


def codificador_propio(modo, calidad_simple, codificador_avanzado) -> bool:
    """Dice si el perfil graba con un codificador distinto del de la señal.

    Medido el 28/10/2026 por websocket: en Simple la grabación comparte el
    codificador de la transmisión con RecQuality «Stream»; en Advanced lo
    comparte con RecEncoder «none». Cualquier otro valor es propio.
    """
    if modo == "Simple":
        return calidad_simple != "Stream"
    if modo == "Advanced":
        return codificador_avanzado != "none"
    return False


def _parametro(cliente, categoria, nombre, parada=None) -> str:
    respuesta = cliente.pedir(
        "GetProfileParameter",
        {"parameterCategory": categoria, "parameterName": nombre},
        parada=parada)
    datos = (respuesta or {}).get("responseData", {}) or {}
    valor = datos.get("parameterValue")
    if not valor:
        valor = datos.get("defaultParameterValue")
    return str(valor or "")


def codificador_propio_en_obs(cliente, parada=None):
    """Pregunta el perfil a OBS; None si OBS no responde."""
    try:
        modo = _parametro(cliente, "Output", "Mode", parada)
        calidad = ""
        codificador = ""
        if modo == "Simple":
            calidad = _parametro(cliente, "SimpleOutput", "RecQuality", parada)
        elif modo == "Advanced":
            codificador = _parametro(cliente, "AdvOut", "RecEncoder", parada)
    except Exception as error:
        logger.debug("no se pudo leer el codificador de grabación: %s", error)
        return None
    return codificador_propio(modo, calidad, codificador)


def grabar_al_transmitir(ruta=None) -> bool:
    """Lee la casilla desde config.ini; un fallo de lectura da False."""
    try:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(ruta or paths.config_ini(), encoding="utf-8")
        return ini_tipado.leer_booleano(
            parser, "transmision", "grabar_al_transmitir")
    except Exception as error:
        logger.debug("no se pudo leer grabar_al_transmitir: %s", error)
        return False


def _datos_respuesta(respuesta):
    return (respuesta or {}).get("responseData", respuesta or {})


def _leer_pausa(pedir, parada=None):
    """Devuelve el outputPaused confirmado por GetRecordStatus."""
    estado = _datos_respuesta(pedir("GetRecordStatus", parada=parada))
    return bool(estado.get("outputPaused", False))


# Medido el 02/11/2026 con OBS 5.7.6: ToggleRecordPause puede responder
# outputPaused=True sin cambiar la grabación. El estado válido es el que
# devuelve GetRecordStatus después.
def alternar_pausa(pedir, parada=None):
    """Pausa o reanuda y confirma con GetRecordStatus."""
    en_pausa = _leer_pausa(pedir, parada)
    pedir("ToggleRecordPause", parada=parada)
    for _intento in range(5):
        time.sleep(0.2)
        nuevo = _leer_pausa(pedir, parada)
        if nuevo != en_pausa:
            return nuevo, en_pausa
    return None, en_pausa


def frase_fallo_pausa(en_pausa) -> str:
    """El aviso cuando ToggleRecordPause no cambió el estado."""
    return _(FALLO_REANUDAR if en_pausa else FALLO_PAUSA)


class GrabacionAlTransmitir:
    """Estado de la grabación de una transmisión y sus dos enganches."""

    def __init__(self, activa=None, al_anunciar=None, crear_gestor=None):
        self._activa = activa or (lambda: False)
        self._al_anunciar = al_anunciar or (lambda frase, sonido: None)
        self._crear_gestor = crear_gestor
        self._la_empezo_la_app = False

    def _gestor(self, cliente):
        if self._crear_gestor is not None:
            return self._crear_gestor(cliente)
        # Import local: obs_panel importa este módulo al revisar el prevuelo.
        from bellbird.obs.obs_panel import GestorPanelObs
        return GestorPanelObs(cliente)

    def _empezar(self, cliente, parada):
        try:
            gestor = self._gestor(cliente)
            if gestor.estado_grabacion(parada).get("outputActive"):
                return
            if gestor.alternar_grabacion(parada):
                self._la_empezo_la_app = True
                return
        except Exception as error:
            logger.debug("no se pudo iniciar la grabación: %s", error)
        self._al_anunciar(_(FALLO_GRABACION), "grabacion_problema")

    def al_detener(self, estado, real, parada=None):
        if estado.get("outputActive") or not self._la_empezo_la_app:
            return
        self._la_empezo_la_app = False
        try:
            if real.estado_grabacion(parada).get("outputActive"):
                real.alternar_grabacion(parada)
        except Exception as error:
            logger.debug("no se pudo detener la grabación: %s", error)

    def envolver_esperar_salida(self, original):
        def esperar_salida(cliente, parada=None):
            veredicto = original(cliente, parada)
            if veredicto == "enviando" and self._activa():
                self._empezar(cliente, parada)
            return veredicto
        return esperar_salida

    def envolver_crear_gestor(self, original):
        def crear_gestor(*args, **kwargs):
            return _GestorConGrabacion(original(*args, **kwargs), self)
        return crear_gestor


class _GestorConGrabacion:
    """Delega todo en el gestor real y detiene la grabación al apagarse."""

    def __init__(self, real, grabacion):
        self._real = real
        self._grabacion = grabacion

    def estado_transmision(self, parada=None):
        estado = self._real.estado_transmision(parada)
        self._grabacion.al_detener(estado, self._real, parada)
        return estado

    def __getattr__(self, nombre):
        return getattr(self._real, nombre)
