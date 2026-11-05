"""Casilla que activa y devuelve la monitorización del micrófono de OBS."""

from __future__ import annotations

import threading

import wx

from guyrapu.core import diagnostico
from guyrapu.core.idioma import _
from guyrapu.obs import escucha_microfono
from guyrapu.ui.accesibilidad import anunciar

logger = diagnostico.obtener_logger(__name__)


def _con_fuente(fuente, frase):
    # Traductores: {fuente} es la fuente de audio y {frase} el resultado.
    return _("{fuente}: {frase}").format(fuente=fuente, frase=frase)


class ControlEscucha:
    """Casilla que refleja y alterna la escucha de la fuente elegida en OBS."""

    def __init__(self, casilla, gestor, operaciones, fuente,
                 al_cambiar=None):
        self._casilla = casilla
        self._gestor = gestor
        self._operaciones = operaciones
        self._fuente_elegida = fuente
        self._al_cambiar = al_cambiar or (lambda _fuente: None)
        self.activa = False
        self._fuente = ""
        self._anterior = None
        casilla.Bind(wx.EVT_CHECKBOX, self.alternar)

    def alternar(self, event=None):
        querer = self._casilla.GetValue()
        self._casilla.SetValue(self.activa)
        if not querer:
            self._operaciones.en_hilo(self._restaurar, self._desactivada)
            return
        fuente = self._fuente_elegida()
        if not fuente:
            self._sin_fuente()
            return
        self._operaciones.en_hilo(
            lambda: self._preparar(fuente), self._activada)

    def _preparar(self, fuente):
        return fuente, escucha_microfono.activar(fuente)

    def _sin_fuente(self):
        anunciar(_("Elige una fuente de audio."))
        self._casilla.SetFocus()

    def _activada(self, resultado):
        fuente, anterior = resultado
        if not fuente:
            self._sin_fuente()
            return
        self._fuente = fuente
        self._anterior = anterior
        self.activa = True
        self._casilla.SetValue(True)
        anunciar(_con_fuente(fuente, escucha_microfono.frase_activada(anterior)))
        self._casilla.SetFocus()
        self._al_cambiar(fuente)

    def _restaurar(self):
        escucha_microfono.restaurar(self._fuente, self._anterior)

    def _desactivada(self, _resultado):
        fuente = self._fuente
        anterior = self._anterior
        self.activa = False
        self._fuente = ""
        self._anterior = None
        self._casilla.SetValue(False)
        anunciar(_con_fuente(
            fuente, escucha_microfono.frase_desactivada(anterior)))
        self._casilla.SetFocus()
        self._al_cambiar(fuente)

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
