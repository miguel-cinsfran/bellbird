"""Botones de grabación del panel de transmisión.

Iniciar o detener la grabación y pausarla o reanudarla, con las etiquetas,
los anuncios y los sonidos que ya usa el panel.
"""

from __future__ import annotations

import wx

from guyrapu.core.idioma import N_, _
from guyrapu.obs import grabaciones, obs_estado, obs_grabacion
from guyrapu.ui import aviso_importante
from guyrapu.ui.accesibilidad import anunciar
from guyrapu.ui.preferencias_comun import mostrar_control, nombre_de_etiqueta
from guyrapu.voice import sound_player


_INICIAR_GRABACION = N_("Iniciar &grabación")
_DETENER_GRABACION = N_("Detener &grabación")
_PAUSAR_GRABACION = N_("&Pausar grabación")
_REANUDAR_GRABACION = N_("&Reanudar grabación")


def _avisar(frase, sonido, *, error=False):
    """Avisa por el camino central, o por el local si el cuadro está apagado."""
    if aviso_importante._casilla_activa():
        aviso_importante.avisar(frase, sonido, error=error)
        return
    sound_player.reproducir(sonido)
    anunciar(frase)


def _crear_botones(padre):
    boton = wx.Button(padre, label=_(_INICIAR_GRABACION),
                      name=nombre_de_etiqueta(_(_INICIAR_GRABACION)))
    pausar = wx.Button(padre, label=_(_PAUSAR_GRABACION),
                       name=nombre_de_etiqueta(_(_PAUSAR_GRABACION)))
    return boton, pausar


class ControlGrabacion:
    """Botones de grabación del panel: iniciar o detener, y pausar o reanudar."""

    def __init__(self, padre, operaciones, gestor, al_cambiar, foco):
        self._operaciones = operaciones
        self._gestor = gestor
        self._al_cambiar = al_cambiar
        self._foco = foco
        self.grabando = False
        self.en_pausa = False
        self.boton, self.pausar = _crear_botones(padre)
        self.boton.Bind(wx.EVT_BUTTON, self._alternar)
        self.pausar.Bind(wx.EVT_BUTTON, self._alternar_pausa)

    def fijar(self, grabando, en_pausa):
        self.grabando = bool(grabando)
        self.en_pausa = bool(en_pausa)
        etiqueta = (_DETENER_GRABACION if self.grabando else _INICIAR_GRABACION)
        self.boton.SetLabel(_(etiqueta))
        self.boton.SetName(nombre_de_etiqueta(_(etiqueta)))
        etiqueta = (_REANUDAR_GRABACION if self.en_pausa
                    else _PAUSAR_GRABACION)
        self.pausar.SetLabel(_(etiqueta))
        self.pausar.SetName(nombre_de_etiqueta(_(etiqueta)))
        mostrar_control(self.pausar, self.grabando, self._foco)

    def _alternar(self, event):
        self._operaciones.en_hilo(
            self._gestor.alternar_grabacion_con_ruta, self._alternada)

    def _alternada(self, resultado):
        activa, ruta = resultado
        self.fijar(activa, False)
        if activa:
            self._resultado("grabacion_iniciada")
            return
        _avisar(grabaciones.anotar_y_decir(ruta),
                obs_estado.sonido_resultado("grabacion_detenida"))
        self._al_cambiar()

    def _alternar_pausa(self, event):
        self._operaciones.en_hilo(
            self._gestor.alternar_pausa_grabacion, self._pausa_alternada)

    def _pausa_alternada(self, resultado):
        cambio, en_pausa = resultado
        if cambio is None:
            _avisar(obs_grabacion.frase_fallo_pausa(en_pausa), "error",
                    error=True)
            return
        self.fijar(self.grabando, cambio)
        accion = "grabacion_en_pausa" if cambio else "grabacion_reanudada"
        self._resultado(accion)

    def _resultado(self, accion):
        _avisar(obs_estado.frase_resultado(accion),
                obs_estado.sonido_resultado(accion))
        self._al_cambiar()
