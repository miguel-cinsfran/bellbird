"""Prueba del micrófono de OBS por tramos, mientras alguien habla.

La prueba abre un solo cliente con la suscripción de medidores y escucha
tramos seguidos con esa misma conexión. Las llamadas a quien la usa salen
del hilo de la prueba: quien las recibe las pasa al hilo de la interfaz.
"""

from __future__ import annotations

import threading
import time

from guyrapu.core import diagnostico
from guyrapu.core.idioma import _
from guyrapu.obs import dispositivo_windows
from guyrapu.obs import nivel_microfono
from guyrapu.obs import obs_audio
from guyrapu.obs import obs_cliente
from guyrapu.obs import obs_entradas_audio

logger = diagnostico.obtener_logger(__name__)

MOTIVO_DETENIDA = "detenida"
MOTIVO_TOPE = "tope"
MOTIVO_FALLO = "fallo"


def preparar(gestor, preferido) -> tuple:
    """Fuente del micrófono, si está silenciada y su nombre de dispositivo.

    La fuente sale vacía cuando OBS no tiene micrófono y no se consulta el
    silencio. Un fallo al leer el dispositivo deja el nombre vacío.
    """
    fuente = obs_audio.elegir_microfono(
        gestor.entradas_audio(), preferido, gestor.microfono_especial())
    return preparar_fuente(gestor, fuente)


def preparar_fuente(gestor, fuente) -> tuple:
    """La fuente ya elegida, su silencio y el nombre de su dispositivo.

    No vuelve a elegir la fuente, así mide la que se pidió aunque no figure
    entre las entradas de audio de OBS. Un fallo al leer el dispositivo deja
    el nombre vacío.
    """
    if not fuente:
        return "", False, ""
    silenciada = bool(gestor.silenciada(fuente))
    nombre = ""
    try:
        nombre, _predeterminado = gestor.dispositivo(
            fuente, dispositivo_windows.microfono_predeterminado)
    except Exception as exc:
        logger.debug("No se pudo saber el dispositivo del micrófono: %s", exc)
    return fuente, silenciada, nombre


def frase_de_inicio(nombre_dispositivo) -> str:
    """Anuncio del comienzo y aviso si el auricular usa manos libres."""
    frase = _("Prueba del micrófono iniciada. Habla como en un directo.")
    if obs_audio.es_manos_libres(nombre_dispositivo):
        # Traductores: {nombre} es el nombre del dispositivo de audio.
        frase += " " + _(
            "{nombre} es un auricular en modo manos libres y suena con poca "
            "calidad. Para el directo, usa otro micrófono."
        ).format(nombre=nombre_dispositivo)
    return frase


class PruebaMicrofono:
    """Mide el nivel de una fuente de OBS por tramos hasta detenerla."""

    def __init__(self, fuente, al_tramo, al_terminar, crear_cliente=None,
                 segundos_tramo=5.0, tope=120.0):
        self._fuente = fuente
        self._al_tramo = al_tramo
        self._al_terminar = al_terminar
        self._crear_cliente = crear_cliente or self._cliente_por_defecto
        self._segundos_tramo = segundos_tramo
        self._tope = tope
        self._parada = threading.Event()
        self._hilo = None

    @staticmethod
    def _cliente_por_defecto():
        return obs_cliente.ClienteObs(
            obs_cliente.leer_ajustes(),
            suscripciones=obs_entradas_audio.SUSCRIPCION_METROS)

    def iniciar(self) -> None:
        self._hilo = diagnostico.crear_hilo(self._correr, "PruebaMicrofono")
        self._hilo.start()

    def detener(self) -> None:
        self._parada.set()

    def _correr(self) -> None:
        cliente = None
        motivo = MOTIVO_DETENIDA
        comienzo = time.monotonic()
        try:
            cliente = self._crear_cliente()
            cliente.conectar()
            while not self._parada.is_set():
                restante = self._tope - (time.monotonic() - comienzo)
                if restante <= 0:
                    motivo = MOTIVO_TOPE
                    break
                eventos = cliente.escuchar(
                    "InputVolumeMeters",
                    min(self._segundos_tramo, restante), self._parada)
                if self._parada.is_set():
                    break
                self._al_tramo(
                    nivel_microfono.nivel_de(eventos, self._fuente))
        except Exception as exc:
            logger.debug("La prueba del micrófono se cortó: %s", exc)
            motivo = MOTIVO_FALLO
        finally:
            if cliente is not None:
                try:
                    cliente.cerrar()
                except Exception as exc:
                    logger.debug("No se pudo cerrar la prueba del micrófono: "
                                 "%s", exc)
            self._al_terminar(motivo)
