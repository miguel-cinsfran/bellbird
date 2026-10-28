"""Prueba de voz de la página Voces.

Hace sonar una voz de prueba y cierra su motor. No conoce la página ni el
diálogo: recibe los valores ya leídos de los controles.
"""

from __future__ import annotations

import time

import wx

from ytchat.core import diagnostico
from ytchat.core.idioma import _
from ytchat.ui.accesibilidad import anunciar

logger = diagnostico.obtener_logger(__name__)


class PruebaVoz:
    """Motor de la prueba de voz, compartido por Prism y ElevenLabs."""

    def __init__(self):
        self._motor_prueba = None
        self._probando_eleven = False

    def probar_prism(self, motor, indice_voz, velocidad, volumen, tono):
        from ytchat.voice import motores

        self.cerrar()
        try:
            prueba = motores.MotorPrism(motor)
        except motores.MotorNoDisponible:
            anunciar(_("No se pudo iniciar el motor de voz elegido."))
            return
        self._motor_prueba = prueba
        try:
            prueba.elegir_voz(indice_voz)
            prueba.fijar_velocidad(velocidad)
            prueba.fijar_volumen(volumen)
            prueba.fijar_tono(tono)
            prueba.hablar(_("Así suena esta voz."))
        except Exception as exc:
            logger.warning("Prueba de voz: %s", exc)

    def probar_elevenlabs(self, clave, voz, velocidad, volumen):
        if self._probando_eleven:
            return
        self._probando_eleven = True
        diagnostico.crear_hilo(
            lambda: self._sonar_prueba_elevenlabs(clave, voz, velocidad, volumen),
            "ProbarVozEleven").start()

    def _sonar_prueba_elevenlabs(self, clave, voz, velocidad, volumen) -> None:
        # El motor de la prueba se crea, usa y cierra dentro de su hilo.
        from ytchat.voice import escala_voz
        from ytchat.voice import motor_elevenlabs

        prueba = None
        try:
            prueba = motor_elevenlabs.MotorElevenLabs(clave)
            idx = escala_voz.resolver_voz(voz, prueba.voces())
            prueba.elegir_voz(0 if idx is None else idx)
            prueba.fijar_velocidad(velocidad)
            prueba.fijar_volumen(volumen)
            prueba.hablar(_("Así suena esta voz."))
            while prueba.hablando():
                time.sleep(0.05)
        except Exception as exc:
            wx.CallAfter(anunciar, str(exc))
        finally:
            if prueba is not None:
                try:
                    prueba.cerrar()
                except Exception as exc:
                    logger.debug("Cerrar la prueba de ElevenLabs: %s", exc)
            wx.CallAfter(self._fin_prueba_elevenlabs)

    def _fin_prueba_elevenlabs(self) -> None:
        self._probando_eleven = False

    def cerrar(self) -> None:
        motor = self._motor_prueba
        if motor is None:
            return
        self._motor_prueba = None
        try:
            motor.cerrar()
        except Exception as exc:
            logger.debug("Cerrar motor de prueba: %s", exc)
