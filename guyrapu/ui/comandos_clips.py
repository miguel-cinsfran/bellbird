"""Comando Guardar clip del menú OBS, sin abrir el panel."""

from pathlib import Path

import wx

from guyrapu.core import diagnostico
from guyrapu.core.config_transmision import leer_ajustes_clips_chat
from guyrapu.core.idioma import _
from guyrapu.obs import obs_cliente, obs_clips
from guyrapu.obs import grabaciones
from guyrapu.obs.obs_panel import GestorPanelObs
from guyrapu.ui.accesibilidad import anunciar
from guyrapu.voice import sound_player

logger = diagnostico.obtener_logger(__name__)


def _avisar(frase, sonido):
    """Anuncia y suena en el hilo de la interfaz."""
    def _decir():
        anunciar(frase)
        sound_player.reproducir(sonido)
    wx.CallAfter(_decir)


def _ejecutar_en_obs(operacion):
    """Conecta, ejecuta la operación y avisa el resultado fuera del hilo."""
    def _trabajar():
        gestor = GestorPanelObs()
        try:
            gestor.conectar()
            frase, sonido = operacion(gestor)
        except Exception as error:
            frase, sonido = obs_cliente.mensaje_de_fallo_obs(error), "error"
        finally:
            try:
                gestor.cerrar()
            except Exception as error:
                logger.debug("no se pudo cerrar el gestor de OBS: %s", error)
        _avisar(frase, sonido)
    diagnostico.crear_hilo(_trabajar, "ClipsObs").start()


def _anotar_clip(ruta):
    if ruta:
        grabaciones.anotar(ruta, tipo="clip")


def _guardar_el_clip(cliente):
    ruta = obs_clips.guardar(cliente)
    _anotar_clip(ruta)
    return _(obs_clips.MENSAJE_CLIP_GUARDADO).format(
        archivo=Path(ruta).name), "clip"


def _operacion(gestor):
    cliente = getattr(gestor, "_cliente", gestor)
    segundos = obs_clips.leer_segundos()
    if not segundos:
        return _(obs_clips.MENSAJE_DESACTIVADOS), "error"
    estado = obs_clips.leer_estado(cliente, segundos)
    if not estado.soportado:
        return _(obs_clips.MENSAJE_NO_DISPONIBLE), "error"
    decision = obs_clips.decidir(
        estado.salida_activa, estado.buffer_activo, estado.preparado)
    if decision == obs_clips.GUARDAR:
        return _guardar_el_clip(cliente)
    if decision == obs_clips.RECHAZAR:
        return _(obs_clips.MENSAJE_SALIDA_ACTIVA), "error"
    if decision == obs_clips.PREPARAR:
        obs_clips.preparar(cliente, segundos)
    else:
        obs_clips.iniciar(cliente)
    return (_(obs_clips.MENSAJE_CLIPS_LISTOS).format(segundos=segundos),
            "clip")


def _operacion_chat(gestor, autor):
    """Guarda el clip solo si el búfer ya está en marcha; nunca lo prepara."""
    cliente = getattr(gestor, "_cliente", gestor)
    segundos = obs_clips.leer_segundos()
    if not segundos:
        return None
    estado = obs_clips.leer_estado(cliente, segundos)
    if not estado.buffer_activo:
        return None
    ruta = obs_clips.guardar(cliente)
    _anotar_clip(ruta)
    return (_(obs_clips.MENSAJE_CLIP_GUARDADO_POR).format(
        autor=autor, archivo=Path(ruta).name), "clip")


def _terminar(al_terminar, guardado):
    if al_terminar is None:
        return
    try:
        wx.CallAfter(al_terminar, guardado)
    except Exception as error:
        logger.debug("no se pudo avisar el fin del clip del chat: %s", error)


def _ejecutar_chat(operacion, al_terminar):
    def _trabajar():
        gestor = None
        resultado = None
        try:
            gestor = GestorPanelObs()
            gestor.conectar()
            resultado = operacion(gestor)
        except Exception as error:
            logger.debug("el clip pedido desde el chat no se guardó: %s", error)
        finally:
            if gestor is not None:
                try:
                    gestor.cerrar()
                except Exception as error:
                    logger.debug("no se pudo cerrar el gestor de OBS: %s", error)
        if resultado is not None:
            _avisar(*resultado)
        _terminar(al_terminar, resultado is not None)
    diagnostico.crear_hilo(_trabajar, "ClipsChat").start()


def guardar_clip_del_chat(autor, al_terminar=None):
    """Atiende un !clip del chat sin preparar ni encender el búfer."""
    ajustes = leer_ajustes_clips_chat()
    if not ajustes.activo or not obs_clips.leer_segundos():
        _terminar(al_terminar, False)
        return
    try:
        _ejecutar_chat(lambda gestor: _operacion_chat(gestor, autor),
                       al_terminar)
    except Exception as error:
        logger.debug("no se pudo lanzar el clip del chat: %s", error)
        _terminar(al_terminar, False)


def guardar_clip(frame):
    """Guarda el último tramo del directo o prepara el búfer si hace falta."""
    _ejecutar_en_obs(_operacion)
