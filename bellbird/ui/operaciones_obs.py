"""Operaciones de OBS en un hilo para un cuadro de diálogo."""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.obs import obs_cliente
from bellbird.ui.accesibilidad import anunciar
from bellbird.voice import sound_player

logger = diagnostico.obtener_logger(__name__)


class OperacionesObs:

    def __init__(self, ventana, activar, escribir_fallo, enfocar_tras_fallo,
                 tras_operacion=None):
        self._activar = activar
        self._escribir_fallo = escribir_fallo
        self._enfocar_tras_fallo = enfocar_tras_fallo
        self._tras_operacion = tras_operacion or (lambda resultado: None)
        self.cerrando = False
        self.en_vuelo = False
        self._temporizador_consulta = wx.Timer(ventana)
        ventana.Bind(wx.EVT_TIMER, self._anunciar_consulta,
                     self._temporizador_consulta)
        ventana.Bind(wx.EVT_WINDOW_DESTROY, self._al_destruir)

    def en_hilo(self, funcion, al_terminar=None):
        self._activar(False)
        self.en_vuelo = True
        self._temporizador_consulta.StartOnce(400)
        def ejecutar():
            try:
                resultado = funcion()
            except obs_cliente.ObsError as error:
                wx.CallAfter(self.fallo, str(error))
            except Exception as error:
                # Cualquier otro fallo (la fuente ya no existe en OBS y
                # obs_panel devuelve None, falta web/chat.html…) mataba el
                # hilo sin avisar y dejaba el diálogo con todo desactivado.
                logger.warning("operación OBS: %r", error)
                wx.CallAfter(self.fallo, obs_cliente.mensaje_de_fallo_obs(error))
            else:
                wx.CallAfter(self._terminar, resultado, al_terminar)
        diagnostico.crear_hilo(ejecutar, "TransmisionOBS").start()

    def _terminar(self, resultado, al_terminar):
        self._temporizador_consulta.Stop()
        self.en_vuelo = False
        if self.cerrando:
            return
        self._activar(True)
        self._tras_operacion(resultado)
        if al_terminar:
            al_terminar(resultado)

    def fallo(self, mensaje):
        self._temporizador_consulta.Stop()
        self.en_vuelo = False
        if self.cerrando:
            return
        self._activar(False)
        self._escribir_fallo(mensaje)
        sound_player.reproducir("error")
        anunciar(mensaje)
        self._enfocar_tras_fallo()

    def cerrar(self):
        self.cerrando = True
        self._temporizador_consulta.Stop()

    def _anunciar_consulta(self, event):
        if self.en_vuelo and not self.cerrando:
            # Puede repetirse mientras espera la operación y no debe interrumpir.
            anunciar(_("Consultando OBS"), False)

    def _al_destruir(self, event):
        # Un hilo puede aterrizar después del Destroy; sin esta marca tocaba
        # controles ya muertos y wx levantaba RuntimeError.
        self.cerrando = True
        self._temporizador_consulta.Stop()
        event.Skip()
