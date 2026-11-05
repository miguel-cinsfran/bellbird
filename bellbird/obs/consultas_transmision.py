"""Consultas a OBS de la ventana de transmisión, sin wx."""

from __future__ import annotations

from dataclasses import dataclass

from bellbird.obs import obs_audio
from bellbird.obs import obs_disposicion
from bellbird.obs.obs_destinos import DESTINOS
from bellbird.obs.obs_panel import NOMBRE_FUENTE


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
    transmision: object
    grabacion: object
    perfil: object
    problemas: object = ()
    microfono: str = ""
    silenciado: bool = False


def _elegir_microfono(gestor, preferido) -> str:
    return obs_audio.elegir_microfono(
        gestor.entradas_audio(), preferido, gestor.microfono_especial())


def _silencio(gestor, microfono) -> bool:
    return bool(gestor.silenciada(microfono)) if microfono else False


def _problemas(gestor, destino) -> tuple:
    if destino not in DESTINOS:
        return ()
    revision = gestor.revisar(destino)
    return tuple(getattr(revision, "problemas", ()) or ())


def estado_transmision(leer, parada=None) -> dict:
    datos = leer("GetStreamStatus", parada=parada)
    estado = {clave: datos.get(clave, 0) for clave in (
        "outputActive", "outputDuration", "outputSkippedFrames", "outputTotalFrames")}
    estado["outputReconnecting"] = bool(datos.get("outputReconnecting", False))
    # obs-websocket da outputDuration en milisegundos; el resto de la app
    # (obs_estado.frase_transmision, F2) lo trata en segundos. Sin esta
    # conversión un minuto de directo se anunciaba como «16 h 40 min».
    try:
        estado["outputDuration"] = int(float(estado["outputDuration"]) / 1000)
    except (TypeError, ValueError):
        estado["outputDuration"] = 0
    return estado


def leer_filas(gestor, escena) -> tuple:
    """Las filas de la lista de fuentes, releídas tras cada acción."""
    return gestor.filas_escena(escena)


def cargar_inicial(gestor, preferido="") -> CargaInicial:
    gestor.conectar()
    escenas = gestor.escenas()
    al_aire = gestor.escena_al_aire()
    escena = al_aire if al_aire in escenas else (escenas[0] if escenas else "")
    fuentes = gestor.fuentes(escena)
    transmision = gestor.estado_transmision()
    grabacion = gestor.estado_grabacion()
    perfil = gestor.perfil_actual()
    microfono = _elegir_microfono(gestor, preferido)
    return CargaInicial(
        escenas=escenas, escena=escena, al_aire=al_aire, fuentes=fuentes,
        transmision=transmision, grabacion=grabacion, perfil=perfil,
        problemas=_problemas(gestor, perfil), microfono=microfono,
        silenciado=_silencio(gestor, microfono))


@dataclass(frozen=True)
class EstadoLeido:
    escena: str
    transmision: object
    grabacion: object
    perfil: object
    problemas: object
    microfono: str
    silenciado: bool


def leer_estado(gestor, destino="", preferido="") -> EstadoLeido:
    """El estado que muestra el panel, también tras cada acción."""
    escena = gestor.escena_al_aire()
    transmision = gestor.estado_transmision()
    grabacion = gestor.estado_grabacion()
    perfil = gestor.perfil_actual()
    microfono = _elegir_microfono(gestor, preferido)
    return EstadoLeido(
        escena=escena, transmision=transmision, grabacion=grabacion,
        perfil=perfil, problemas=_problemas(gestor, destino),
        microfono=microfono, silenciado=_silencio(gestor, microfono))


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
    descripcion: object
    filas: object = ()


def leer_escena(gestor, escena) -> EscenaLeida:
    fuentes = gestor.fuentes(escena)
    fuente = elegir_fuente(fuentes)
    snap = gestor.instantanea(escena, fuente=fuente)
    return EscenaLeida(
        fuentes=fuentes, fuente=fuente, snap=snap,
        descripcion=gestor.descripcion_escena(escena),
        filas=leer_filas(gestor, escena))


def aplicar_tamano(gestor, registro, escena, fuente, ancho, alto):
    registro.guardar(gestor, escena, fuente)
    if fuente == NOMBRE_FUENTE:
        gestor.redimensionar(escena, ancho, alto)
        aplicado = True
    else:
        aplicado = bool(gestor.escalar(escena, ancho, alto, fuente=fuente))
    return gestor.instantanea(escena, fuente=fuente), aplicado


def aplicar_posicion_y_tamano(gestor, registro, escena, fuente, ancho, alto,
                              anclaje):
    """Aplica primero el tamaño y después el lugar, si se eligió uno."""
    snap, aplicado = aplicar_tamano(
        gestor, registro, escena, fuente, ancho, alto)
    if anclaje:
        gestor.colocar(escena, anclaje, fuente=fuente)
        snap = gestor.instantanea(escena, fuente=fuente)
    return snap, aplicado


def cambiar_y_leer(gestor, registro, escena, fuente, funcion, *argumentos):
    registro.guardar(gestor, escena, fuente)
    funcion(escena, *argumentos, fuente=fuente)
    return gestor.instantanea(escena, fuente=fuente)


def preparar_ajuste(gestor, registro, escena, fuente):
    registro.guardar(gestor, escena, fuente)
    return (gestor.transformacion(escena, fuente=fuente),
            gestor.instantanea(escena, fuente=fuente))


def capturar(gestor, escena, fuente, ruta):
    gestor.captura_de_escena(escena, ruta)
    return gestor.instantanea(escena, fuente=fuente)


def restaurar(gestor, registro, escena, fuente):
    registro.aplicar(gestor)
    return gestor.instantanea(escena, fuente=fuente)


def mover(gestor, escena, dx, dy, fuente):
    gestor.mover(escena, dx, dy, fuente=fuente)
    return gestor.instantanea(escena, fuente=fuente)


def descripcion_de_fuente(descripcion, fuente, snap):
    if not fuente:
        return descripcion or ""
    componentes = tuple(
        componente for componente in obs_disposicion.COMPONENTES
        if componente not in ("conexion", "escena", "transparencia"))
    detalle = obs_disposicion.describir_fuente(
        fuente, snap, componentes, "largo")
    return "\n\n".join(
        parte for parte in (descripcion or "", detalle) if parte)
