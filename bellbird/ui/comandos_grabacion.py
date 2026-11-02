"""Comandos de grabación del menú Transmisión, sin abrir el panel."""

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.obs import obs_cliente, obs_estado
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
            accion = operacion(gestor)
        except Exception as error:
            frase, sonido = obs_cliente.mensaje_de_fallo_obs(error), "error"
        else:
            frase = (_("No hay ninguna grabación en curso.") if accion is None
                     else obs_estado.frase_resultado(accion))
            sonido = ("error" if accion is None
                      else obs_estado.sonido_resultado(accion))
        finally:
            try:
                gestor.cerrar()
            except Exception as error:
                logger.debug("no se pudo cerrar el gestor de OBS: %s", error)
        _avisar(frase, sonido)
    diagnostico.crear_hilo(_trabajar, "GrabacionObs").start()


def alternar_grabacion(frame):
    """Inicia o detiene la grabación de OBS, como el botón del panel."""
    _ejecutar_en_obs(lambda gestor: (
        "grabacion_iniciada" if gestor.alternar_grabacion()
        else "grabacion_detenida"))


def alternar_pausa_grabacion(frame):
    """Pausa o reanuda la grabación; sin ninguna en curso, lo dice."""
    def _operacion(gestor):
        if not gestor.estado_grabacion().get("outputActive"):
            return None
        return ("grabacion_en_pausa" if gestor.alternar_pausa_grabacion()
                else "grabacion_reanudada")
    _ejecutar_en_obs(_operacion)
