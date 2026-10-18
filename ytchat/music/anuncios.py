"""Frases y sonidos de la música, sin interfaz.

Traduce lo que pasa con la música (los códigos del coordinador y las
preferencias) a un `Aviso`: el texto que se anuncia y el sonido que lo
acompaña. Un sonido `None` significa que no se reproduce ninguno. Sin wx y
sin VLC, para poder probarlo solo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from ytchat.music.modelo import (
    AVANZO,
    COLA_VACIA,
    ERROR_MOTOR,
    FIN_LISTA,
    INICIO_LISTA,
    OK,
    SIN_TEMA,
    TEMA_FALLIDO,
)

SONIDO_TEMA = "musica_tema"
SONIDO_FIN = "musica_fin"
SONIDO_FALLO = "musica_fallo"
SONIDO_ERROR = "error"

TEXTO_FIN_LISTA = "Fin de la lista de música"
TEXTO_FALLO = "No se pudo reproducir: {nombre}. Se pasa al siguiente"
TEXTO_SIN_TEMA = "No hay música sonando"
TEXTO_COLA_VACIA = "No hay temas para reproducir"
TEXTO_ULTIMO = "Último tema de la lista"
TEXTO_PRIMERO = "Primer tema de la lista"
TEXTO_PAUSA = "Música en pausa"
TEXTO_REANUDADA = "Música reanudada"
TEXTO_DETENIDA = "Música detenida"
TEXTO_ERROR_MOTOR_TEMA = "No se pudo reproducir: {nombre}"
TEXTO_ERROR_MOTOR = "No se pudo usar el motor de música"
TEXTO_VOLUMEN = "Volumen de la música: {valor}"
TEXTO_QUE_SUENA = "Sonando: {nombre}. Tema {posicion} de {total}"
TEXTO_EN_PAUSA = "En pausa: {nombre}. Tema {posicion} de {total}"
TEXTO_ALEATORIO_ON = "Orden aleatorio activado"
TEXTO_ALEATORIO_OFF = "Orden aleatorio desactivado"
TEXTO_SIN_CARPETA = "No hay carpeta de música. Elige una en Preferencias, página Música"
TEXTO_MOTOR = "La música no está disponible: no se pudo cargar VLC"
TEXTO_PREPARANDO = "Preparando la música"
TEXTO_PREPARANDO_OCUPADO = "La música se está preparando"


@dataclass(frozen=True)
class Aviso:
    """Lo que se anuncia por la música: el texto y, si toca, el sonido."""

    texto: str
    sonido: str | None = None


def nombre_tema(tema, incluir_artista: bool) -> str:
    """El título del tema; con artista, «Título, de Artista».

    Un título vacío cae al nombre del archivo sin extensión o, si el origen
    es un enlace, al origen completo.
    """
    titulo = tema.titulo or _titulo_de_origen(tema)
    if incluir_artista and tema.artista:
        return f"{titulo}, de {tema.artista}"
    return titulo


def _titulo_de_origen(tema) -> str:
    if tema.es_enlace:
        return tema.origen
    return os.path.splitext(os.path.basename(tema.origen))[0]


def _nombre(resultado, incluir_artista: bool) -> str:
    tema = resultado.tema if resultado.tema is not None else resultado.estado.actual
    if tema is None:
        return ""
    return nombre_tema(tema, incluir_artista)


def aviso_automatico(resultado, sonido_tema: bool, decir_titulo: bool,
                     incluir_artista: bool) -> Aviso | None:
    """Lo que llega solo por `al_cambiar` del coordinador.

    «avanzo» respeta las casillas; «fin_lista» y «tema_fallido» suenan
    siempre. Cualquier otro código no genera aviso.
    """
    if resultado.codigo == AVANZO:
        actual = resultado.estado.actual
        texto = nombre_tema(actual, incluir_artista) if (decir_titulo and actual) else ""
        sonido = SONIDO_TEMA if sonido_tema else None
        if not texto and sonido is None:
            return None
        return Aviso(texto, sonido)
    if resultado.codigo == FIN_LISTA:
        return Aviso(TEXTO_FIN_LISTA, SONIDO_FIN)
    if resultado.codigo == TEMA_FALLIDO:
        nombre = nombre_tema(resultado.tema, False) if resultado.tema else ""
        return Aviso(TEXTO_FALLO.format(nombre=nombre), SONIDO_FALLO)
    return None


def aviso_accion(accion: str, resultado, incluir_artista: bool) -> Aviso:
    """Lo que pidió el usuario con un atajo o el menú.

    Sin sonido salvo el error, porque el usuario lo pidió y está atento.
    """
    codigo = resultado.codigo
    if codigo == SIN_TEMA:
        return Aviso(TEXTO_SIN_TEMA)
    if codigo == COLA_VACIA:
        return Aviso(TEXTO_COLA_VACIA)
    if codigo == ERROR_MOTOR:
        if resultado.tema is not None:
            texto = TEXTO_ERROR_MOTOR_TEMA.format(
                nombre=nombre_tema(resultado.tema, incluir_artista))
            return Aviso(texto, SONIDO_ERROR)
        return Aviso(TEXTO_ERROR_MOTOR, SONIDO_ERROR)
    if codigo == FIN_LISTA and accion == "siguiente":
        return Aviso(TEXTO_ULTIMO)
    if codigo == INICIO_LISTA and accion == "anterior":
        return Aviso(TEXTO_PRIMERO)
    if codigo == OK:
        if accion in ("siguiente", "anterior", "reproducir"):
            return Aviso(_nombre(resultado, incluir_artista))
        if accion == "pausa":
            return Aviso(TEXTO_PAUSA if resultado.estado.pausado else TEXTO_REANUDADA)
        if accion == "detener":
            return Aviso(TEXTO_DETENIDA)
    return Aviso("")


def aviso_volumen(valor: int) -> Aviso:
    """Confirmación del volumen nuevo pedido por el usuario."""
    return Aviso(TEXTO_VOLUMEN.format(valor=valor))


def aviso_que_suena(estado, incluir_artista: bool) -> Aviso:
    """Qué está sonando, para el atajo que consulta el estado."""
    actual = estado.actual
    if actual is None or estado.terminado:
        return Aviso(TEXTO_SIN_TEMA)
    nombre = nombre_tema(actual, incluir_artista)
    posicion = estado.posicion + 1
    total = len(estado.cola)
    plantilla = TEXTO_EN_PAUSA if estado.pausado else TEXTO_QUE_SUENA
    return Aviso(plantilla.format(nombre=nombre, posicion=posicion, total=total))


def aviso_aleatorio(activo: bool) -> Aviso:
    """Confirmación del orden aleatorio tras el atajo."""
    return Aviso(TEXTO_ALEATORIO_ON if activo else TEXTO_ALEATORIO_OFF)


def aviso_sin_carpeta() -> Aviso:
    """No hay carpeta de música elegida en Preferencias."""
    return Aviso(TEXTO_SIN_CARPETA, SONIDO_ERROR)


def aviso_motor_no_disponible() -> Aviso:
    """libVLC no se pudo cargar, así que la música no está disponible."""
    return Aviso(TEXTO_MOTOR, SONIDO_ERROR)


def aviso_preparando() -> Aviso:
    """Aviso al lanzar la preparación del motor; sin sonido, lo pidió el
    usuario y está atento."""
    return Aviso(TEXTO_PREPARANDO)


def aviso_preparando_ocupado() -> Aviso:
    """Una acción llegó mientras el motor todavía se está preparando."""
    return Aviso(TEXTO_PREPARANDO_OCUPADO)
