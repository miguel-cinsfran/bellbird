"""Botones de grabación del panel de transmisión.

Iniciar o detener la grabación y pausarla o reanudarla, con las etiquetas,
los anuncios y los sonidos que ya usa el panel.
"""

from __future__ import annotations

import wx

from bellbird.core.idioma import N_, _
from bellbird.obs import obs_estado
from bellbird.ui.accesibilidad import anunciar
from bellbird.ui.preferencias_comun import mostrar_control, nombre_de_etiqueta
from bellbird.voice import sound_player


_INICIAR_GRABACION = N_("Iniciar &grabación")
_DETENER_GRABACION = N_("Detener &grabación")
_PAUSAR_GRABACION = N_("&Pausar grabación")
_REANUDAR_GRABACION = N_("&Reanudar grabación")


class ControlGrabacion:
    """Botones de grabación del panel: iniciar o detener, y pausar o reanudar."""

    def __init__(self, padre, operaciones, gestor, al_cambiar, foco):
        self._operaciones = operaciones
        self._gestor = gestor
        self._al_cambiar = al_cambiar
        self._foco = foco
        self.grabando = False
        self.en_pausa = False
        self.boton = wx.Button(padre, label=_(_INICIAR_GRABACION),
                               name=nombre_de_etiqueta(_(_INICIAR_GRABACION)))
        self.pausar = wx.Button(padre, label=_(_PAUSAR_GRABACION),
                               name=nombre_de_etiqueta(_(_PAUSAR_GRABACION)))
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
            self._gestor.alternar_grabacion, self._alternada)

    def _alternada(self, activa):
        self.fijar(activa, False)
        accion = "grabacion_iniciada" if activa else "grabacion_detenida"
        self._resultado(accion)

    def _alternar_pausa(self, event):
        self._operaciones.en_hilo(
            self._gestor.alternar_pausa_grabacion, self._pausa_alternada)

    def _pausa_alternada(self, en_pausa):
        self.fijar(self.grabando, en_pausa)
        accion = "grabacion_en_pausa" if en_pausa else "grabacion_reanudada"
        self._resultado(accion)

    def _resultado(self, accion):
        sound_player.reproducir(obs_estado.sonido_resultado(accion))
        anunciar(obs_estado.frase_resultado(accion))
        self._al_cambiar()
