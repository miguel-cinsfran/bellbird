"""Casilla que activa y devuelve la monitorización del micrófono de OBS."""

from __future__ import annotations

import threading

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.obs import escucha_microfono, obs_entradas_audio, prueba_microfono
from bellbird.ui.accesibilidad import anunciar

logger = diagnostico.obtener_logger(__name__)


class ControlEscucha:
    """Casilla que refleja y alterna la escucha del micrófono en OBS."""

    def __init__(self, casilla, gestor, operaciones, preferido):
        self._casilla = casilla
        self._gestor = gestor
        self._operaciones = operaciones
        self._preferido = preferido
        self.activa = False
        self._fuente = ""
        self._anterior = None
        casilla.Bind(wx.EVT_CHECKBOX, self.alternar)

    def alternar(self, event):
        querer = self._casilla.GetValue()
        self._casilla.SetValue(self.activa)
        if querer:
            preferido = self._preferido()
            self._operaciones.en_hilo(
                lambda: self._preparar(preferido), self._activada)
        else:
            self._operaciones.en_hilo(self._restaurar, self._desactivada)

    def _preparar(self, preferido):
        fuente = prueba_microfono.preparar(self._gestor, preferido)[0]
        if not fuente:
            return "", None
        return fuente, escucha_microfono.activar(fuente)

    def _activada(self, resultado):
        fuente, anterior = resultado
        if not fuente:
            anunciar(_(obs_entradas_audio.AVISO_SIN_MICROFONO))
            self._casilla.SetFocus()
            return
        self._fuente = fuente
        self._anterior = anterior
        self.activa = True
        self._casilla.SetValue(True)
        anunciar(escucha_microfono.frase_activada(anterior))
        self._casilla.SetFocus()

    def _restaurar(self):
        escucha_microfono.restaurar(self._fuente, self._anterior)

    def _desactivada(self, _resultado):
        anterior = self._anterior
        self.activa = False
        self._fuente = ""
        self._anterior = None
        self._casilla.SetValue(False)
        anunciar(escucha_microfono.frase_desactivada(anterior))
        self._casilla.SetFocus()

    def al_cerrar(self):
        """Devuelve la monitorización al cerrar, sin anunciar y sin demorar."""
        if not self.activa:
            return
        hilo = threading.Thread(
            target=self._restaurar_al_cerrar,
            args=(self._fuente, self._anterior))
        hilo.start()

    def _restaurar_al_cerrar(self, fuente, anterior):
        try:
            escucha_microfono.restaurar(fuente, anterior)
        except Exception as exc:
            logger.debug("No se pudo devolver la monitorización al cerrar "
                         "el panel de OBS: %s", exc)
