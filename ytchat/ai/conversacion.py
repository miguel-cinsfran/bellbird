"""Conversación de IA con visión, sin protocolo ni red.

La conversación es neutral: guarda Mensajes y elige el protocolo recién
al armar el pedido, así cambiar de modelo a mitad no rompe el turno.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from ytchat.ai import protocolos

PREGUNTA_INICIAL = ("Describe lo que se ve en esta imagen como lo ve "
                    "el público de la transmisión: qué hay en pantalla, "
                    "dónde está cada cosa y si algo se ve mal, cortado "
                    "o en negro.")

CORTA = "corta"
MEDIA = "media"
LARGA = "larga"

_BASE_POR_LARGO = {CORTA: 400, MEDIA: 900, LARGA: 2000}
_EXTRA_RAZONAMIENTO = 4000


class SinCaptura(Exception):
    pass


class SinTexto(Exception):
    pass


def prompt_sistema(descripcion_escena):
    """El prompt fijo, con la descripción de OBS si la hay."""
    base = ("Eres el asistente de un streamer ciego que transmite con OBS. "
            "Responde siempre en español, en prosa breve, sin markdown, sin "
            "listas, sin títulos y sin emojis: la respuesta se lee con un "
            "lector de pantalla. Ve directo a lo que se pregunta. Si algo no "
            "se distingue en la imagen, dilo en vez de suponer.")
    if not descripcion_escena:
        return base
    return (base + "\n\nLo que OBS informa de la escena al aire:\n"
            + descripcion_escena)


def max_tokens(largo, piensa, tope_salida):
    """El presupuesto visible, con extra si el modelo piensa y con tope."""
    base = _BASE_POR_LARGO.get(largo, _BASE_POR_LARGO[MEDIA])
    if piensa:
        base += _EXTRA_RAZONAMIENTO
    if isinstance(tope_salida, bool):
        return base
    if isinstance(tope_salida, int):
        return min(base, tope_salida)
    return base


@dataclass
class _Pendiente:
    imagen: bytes
    fuente: str
    hora: str


class Conversacion:
    """La única fuente de verdad de la conversación en curso."""

    def __init__(self):
        self.sesion = str(uuid.uuid4())
        self.mensajes = []
        self.filas = []
        self._pendiente = None

    def agregar_captura(self, imagen, fuente, hora):
        if self._pendiente is not None:
            anterior = "Captura: {}, {}".format(
                self._pendiente.fuente, self._pendiente.hora)
            for i in range(len(self.filas) - 1, -1, -1):
                if self.filas[i] == anterior:
                    del self.filas[i]
                    break
        self._pendiente = _Pendiente(imagen, fuente, hora)
        self.filas.append("Captura: {}, {}".format(fuente, hora))

    def hay_captura(self):
        if self._pendiente is not None:
            return True
        return any(m.imagen is not None for m in self.mensajes)

    def preparar(self, texto, pregunta_inicial):
        if not self.hay_captura():
            raise SinCaptura("la conversación necesita una captura")
        vacio = not texto or not str(texto).strip()
        if vacio:
            if self._pendiente is None:
                raise SinTexto("no hay texto ni captura nueva")
            efectivo = pregunta_inicial
        else:
            efectivo = texto
        imagen = self._pendiente.imagen \
            if self._pendiente is not None else None
        return list(self.mensajes) + [
            protocolos.Mensaje("usuario", efectivo, imagen)]

    def confirmar(self, texto_enviado, respuesta):
        imagen = self._pendiente.imagen \
            if self._pendiente is not None else None
        self.mensajes.append(protocolos.Mensaje(
            "usuario", texto_enviado, imagen))
        self.mensajes.append(protocolos.Mensaje("asistente", respuesta))
        self.filas.append("Pregunta: {}".format(texto_enviado))
        self.filas.append("Respuesta: {}".format(respuesta))
        self._pendiente = None

    def nueva(self):
        self.sesion = str(uuid.uuid4())
        self.mensajes = []
        self.filas = []
        self._pendiente = None
