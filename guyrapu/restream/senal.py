"""Qué aviso sale de cada mensaje del WebSocket de estado de Restream.

Puro: recibe el texto de un mensaje y devuelve los avisos que corresponden.
Guarda el estado de una transmisión: los destinos conectados, la sesión
entrante, la referencia de la señal y su racha.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass

from guyrapu.core.idioma import N_, _

AVISO_DESTINO_CAIDO = N_("{destino} se desconectó.")
AVISO_DESTINO_VUELVE = N_("{destino} vuelve a recibir la transmisión.")
AVISO_SIN_SENAL = N_("Restream dejó de recibir la señal de OBS.")
AVISO_SENAL_VUELVE = N_("Restream vuelve a recibir la señal.")
AVISO_SENAL_DEBIL = N_("Señal débil: a Restream llegan {kbps} kbps.")
AVISO_SENAL_RECUPERADA = N_("La señal se recuperó.")
NOMBRE_DESTINO_DESCONOCIDO = N_("Un destino")

SONIDO_DESTINO_CAIDO = "restream_destino_caido"
SONIDO_DESTINO_VUELVE = "restream_destino_vuelve"
SONIDO_SIN_SENAL = "restream_sin_senal"
SONIDO_SENAL_VUELVE = "restream_senal_vuelve"
SONIDO_SENAL_DEBIL = "restream_senal_debil"

# Cinco mensajes arman la referencia y dos seguidos confirman el cambio.
MUESTRAS_REFERENCIA = 5
MENSAJES_CONFIRMACION = 2


@dataclass(frozen=True)
class Aviso:
    """Una frase para el lector y el sonido que la acompaña."""

    frase: str
    sonido: str


class AnalizadorSenal:
    """El estado de una transmisión y los avisos de cada mensaje."""

    def __init__(self, destinos=None):
        self._destinos = dict(destinos or {})
        self._conectados = set()
        self._estuvieron = set()
        self._suid = None
        self._recibiendo = False
        self._sin_senal = False
        self._muestras = []
        self._referencia = None
        self._debil = False
        self._racha_baja = 0
        self._racha_alta = 0

    def recibir(self, texto):
        """Devuelve los avisos que produce el texto de un mensaje."""
        try:
            mensaje = json.loads(texto)
        except (TypeError, ValueError):
            return []
        if not isinstance(mensaje, dict):
            return []
        accion = mensaje.get("action")
        if accion == "updateIncoming":
            return self._entrante(mensaje)
        if accion == "deleteIncoming":
            return self._sin_entrante()
        if accion == "updateOutgoing":
            return self._saliente(mensaje)
        if accion == "deleteOutgoing":
            return self._borrar_saliente(mensaje)
        return []

    def _nombre(self, canal):
        nombre = self._destinos.get(canal)
        return nombre or _(NOMBRE_DESTINO_DESCONOCIDO)

    def _entrante(self, mensaje):
        avisos = []
        suid = mensaje.get("suid")
        if self._sin_senal and suid != self._suid:
            avisos.append(Aviso(_(AVISO_SENAL_VUELVE), SONIDO_SENAL_VUELVE))
            self._sin_senal = False
            self._reiniciar_referencia()
        self._suid = suid
        self._recibiendo = True
        total = _total(mensaje)
        if total is not None:
            avisos.extend(self._medir(total))
        return avisos

    def _sin_entrante(self):
        if not self._recibiendo:
            return []
        self._recibiendo = False
        self._sin_senal = True
        self._debil = False
        self._reiniciar_rachas()
        return [Aviso(_(AVISO_SIN_SENAL), SONIDO_SIN_SENAL)]

    def _reiniciar_referencia(self):
        self._muestras = []
        self._referencia = None
        self._debil = False
        self._reiniciar_rachas()

    def _reiniciar_rachas(self):
        self._racha_baja = 0
        self._racha_alta = 0

    def _medir(self, total):
        if self._referencia is None:
            self._muestras.append(total)
            if len(self._muestras) >= MUESTRAS_REFERENCIA:
                self._referencia = statistics.median(self._muestras)
                self._reiniciar_rachas()
            return []
        if total < self._referencia / 2:
            self._racha_baja += 1
            self._racha_alta = 0
        else:
            self._racha_baja = 0
        if total >= self._referencia * 0.8:
            self._racha_alta += 1
        else:
            self._racha_alta = 0
        if not self._debil and self._racha_baja >= MENSAJES_CONFIRMACION:
            self._debil = True
            return [Aviso(_(AVISO_SENAL_DEBIL).format(kbps=int(round(total))),
                          SONIDO_SENAL_DEBIL)]
        if (self._debil
                and self._racha_alta >= MENSAJES_CONFIRMACION):
            self._debil = False
            self._reiniciar_rachas()
            return [Aviso(_(AVISO_SENAL_RECUPERADA), SONIDO_SENAL_VUELVE)]
        return []

    def _saliente(self, mensaje):
        estado = _estado(mensaje)
        return self._cambiar_destino(mensaje.get("channelId"),
                                     estado == "CONNECTED")

    def _borrar_saliente(self, mensaje):
        return self._cambiar_destino(mensaje.get("channelId"), False)

    def _cambiar_destino(self, canal, conectado):
        estaba = canal in self._conectados
        if conectado:
            if estaba:
                return []
            self._conectados.add(canal)
            primera_vez = canal not in self._estuvieron
            self._estuvieron.add(canal)
            if primera_vez:
                return []
            return [Aviso(
                _(AVISO_DESTINO_VUELVE).format(destino=self._nombre(canal)),
                SONIDO_DESTINO_VUELVE)]
        self._conectados.discard(canal)
        if not estaba:
            return []
        return [Aviso(
            _(AVISO_DESTINO_CAIDO).format(destino=self._nombre(canal)),
            SONIDO_DESTINO_CAIDO)]


def _total(mensaje):
    streaming = mensaje.get("streaming")
    if not isinstance(streaming, dict):
        return None
    bitrate = streaming.get("bitrate")
    if not isinstance(bitrate, dict):
        return None
    total = bitrate.get("total")
    if isinstance(total, bool) or not isinstance(total, (int, float)):
        return None
    return total


def _estado(mensaje):
    streaming = mensaje.get("streaming")
    if not isinstance(streaming, dict):
        return None
    return streaming.get("status")
