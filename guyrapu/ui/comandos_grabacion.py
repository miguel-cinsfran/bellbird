"""Comandos de grabación del menú OBS, sin abrir el panel."""

import wx

from guyrapu.core import diagnostico
from guyrapu.core.idioma import _
from guyrapu.obs import grabaciones, obs_cliente, obs_estado, obs_grabacion
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
    diagnostico.crear_hilo(_trabajar, "GrabacionObs").start()


def alternar_grabacion(frame):
    """Inicia o detiene la grabación de OBS, como el botón del panel."""
    def _operacion(gestor):
        activa, ruta = gestor.alternar_grabacion_con_ruta()
        accion = "grabacion_iniciada" if activa else "grabacion_detenida"
        frase = (obs_estado.frase_resultado(accion) if activa
                 else grabaciones.anotar_y_decir(ruta))
        return frase, obs_estado.sonido_resultado(accion)
    _ejecutar_en_obs(_operacion)


def alternar_pausa_grabacion(frame):
    """Pausa o reanuda la grabación; sin ninguna en curso, lo dice."""
    def _operacion(gestor):
        if not gestor.estado_grabacion().get("outputActive"):
            return _("No hay ninguna grabación en curso."), "error"
        cambio, en_pausa = gestor.alternar_pausa_grabacion()
        if cambio is None:
            return obs_grabacion.frase_fallo_pausa(en_pausa), "error"
        accion = "grabacion_en_pausa" if cambio else "grabacion_reanudada"
        return (obs_estado.frase_resultado(accion),
                obs_estado.sonido_resultado(accion))
    _ejecutar_en_obs(_operacion)
