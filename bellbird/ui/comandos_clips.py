"""Comando Guardar clip del menú OBS, sin abrir el panel."""

from pathlib import Path

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.obs import obs_cliente, obs_clips
from bellbird.obs.obs_panel import GestorPanelObs
from bellbird.ui.accesibilidad import anunciar
from bellbird.voice import sound_player

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
        ruta = obs_clips.guardar(cliente)
        return _(obs_clips.MENSAJE_CLIP_GUARDADO).format(
            archivo=Path(ruta).name), "clip"
    if decision == obs_clips.RECHAZAR:
        return _(obs_clips.MENSAJE_SALIDA_ACTIVA), "error"
    if decision == obs_clips.PREPARAR:
        obs_clips.preparar(cliente, segundos)
    else:
        obs_clips.iniciar(cliente)
    return (_(obs_clips.MENSAJE_CLIPS_LISTOS).format(segundos=segundos),
            "clip")


def guardar_clip(frame):
    """Guarda el último tramo del directo o prepara el búfer si hace falta."""
    _ejecutar_en_obs(_operacion)
