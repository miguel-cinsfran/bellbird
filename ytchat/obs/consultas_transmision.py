"""Consultas a OBS de la ventana de transmisión, sin wx."""

from __future__ import annotations

from dataclasses import dataclass

from ytchat.obs.obs_panel import NOMBRE_FUENTE


def elegir_fuente(fuentes) -> str:
    """La fuente del chat si está, si no la primera, si no ""."""
    if NOMBRE_FUENTE in fuentes:
        return NOMBRE_FUENTE
    return fuentes[0] if fuentes else ""


@dataclass(frozen=True)
class CargaInicial:
    escenas: object
    escena: str
    al_aire: str
    fuentes: object
    fuente: str
    snap: object
    transformacion: object
    transmision: object
    grabacion: object
    perfil: object
    opciones: object
    actual: object
    descripcion: object


def cargar_inicial(gestor) -> CargaInicial:
    gestor.conectar()
    escenas = gestor.escenas()
    al_aire = gestor.escena_al_aire()
    escena = al_aire if al_aire in escenas else (escenas[0] if escenas else "")
    fuentes = gestor.fuentes(escena)
    fuente = elegir_fuente(fuentes)
    snap = gestor.instantanea(escena, fuente=fuente)
    opciones, actual = gestor.ventanas(escena)
    return CargaInicial(
        escenas=escenas, escena=escena, al_aire=al_aire, fuentes=fuentes,
        fuente=fuente, snap=snap,
        transformacion=gestor.transformacion(escena, fuente=fuente),
        transmision=gestor.estado_transmision(),
        grabacion=gestor.estado_grabacion(),
        perfil=gestor.perfil_actual(), opciones=opciones, actual=actual,
        descripcion=gestor.descripcion_escena())


@dataclass(frozen=True)
class VentanaAplicada:
    frase: str
    fuentes: object
    fuente: str
    snap: object
    al_aire: str
    transmision: object
    grabacion: object
    opciones: object
    actual: object


def aplicar_ventana(gestor, escena, valor) -> VentanaAplicada:
    frase = gestor.usar_ventana(escena, valor)
    fuentes = gestor.fuentes(escena)
    fuente = elegir_fuente(fuentes)
    snap = gestor.instantanea(escena, fuente=fuente)
    al_aire = gestor.escena_al_aire()
    transmision = gestor.estado_transmision()
    grabacion = gestor.estado_grabacion()
    opciones, actual = gestor.ventanas(escena)
    return VentanaAplicada(
        frase=frase, fuentes=fuentes, fuente=fuente, snap=snap,
        al_aire=al_aire, transmision=transmision, grabacion=grabacion,
        opciones=opciones, actual=actual)


@dataclass(frozen=True)
class EscenaLeida:
    fuentes: object
    fuente: str
    snap: object
    opciones: object
    actual: object


def leer_escena(gestor, escena) -> EscenaLeida:
    fuentes = gestor.fuentes(escena)
    fuente = elegir_fuente(fuentes)
    snap = gestor.instantanea(escena, fuente=fuente)
    opciones, actual = gestor.ventanas(escena)
    return EscenaLeida(
        fuentes=fuentes, fuente=fuente, snap=snap, opciones=opciones,
        actual=actual)
