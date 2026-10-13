"""Botón directo de transmisión en la ventana principal, con wx.

Crea el botón en el panel que le pasan y concentra la lógica de wx
(visibilidad, etiqueta, nombre accesible, foco y repintado). El trabajo
de fondo (preparar OBS, confirmar, supervisar, finalizar) usa
`transmision_directa`, sin decidir nada en el marco: este solo crea el
botón, lo mete en la fila y le pide `actualizar`.
"""

from __future__ import annotations

import wx

from ytchat.core import diagnostico
from ytchat.obs import obs_cliente
from ytchat.obs import obs_lanzador
from ytchat.obs import transmision_directa
from ytchat.obs.obs_panel import GestorPanelObs
from ytchat.ui.gui import _T, _pintar, anunciar
from ytchat.voice import sound_player as _snd


class BotonDirecto:
    """Botón «Transmitir en directo» / «Finalizar directo»."""

    def __init__(self, panel, btn_conectar, marco):
        etiqueta, nombre = transmision_directa.etiqueta(False)
        self._marco = marco
        self._conectar = btn_conectar
        self._transmitiendo = False
        self.boton = wx.Button(panel, label=etiqueta, name=nombre)
        _pintar(self.boton, _T.primary, _T.primary_t)
        self.boton.SetFont(self.boton.GetFont().Bold())
        self.boton.Bind(wx.EVT_BUTTON, self._al_pulsar)

    def actualizar(self, conectado, conectando, propio, transmitiendo):
        """Aplica visibilidad, etiqueta y nombre; repinta la fila.

        Oculto sale del orden de Tab; si tenía el foco, este vuelve a
        Conectar para no quedar en un control invisible.
        """
        self._transmitiendo = bool(transmitiendo)
        etiqueta, nombre = transmision_directa.etiqueta(transmitiendo)
        self.boton.SetLabel(etiqueta)
        self.boton.SetName(nombre)
        if transmision_directa.boton_visible(conectado, conectando, propio,
                                             transmitiendo):
            self.boton.Show()
        else:
            if self.boton.HasFocus():
                self._conectar.SetFocus()
            self.boton.Hide()
        self.boton.GetParent().Layout()

    def _al_pulsar(self, event):
        if self._transmitiendo:
            self._finalizar()
        else:
            self._transmitir()

    def _transmitir(self):
        marco = self._marco
        from ytchat.obs import obs_destinos
        destino = marco._config.get("transmision_destino", "") or ""
        if destino not in obs_destinos.DESTINOS:
            destino = ""
        usuario = ""
        if not destino:
            anunciar("Elige a dónde transmitir en la ventana Transmisión.")
            marco._on_transmision(None)
            return
        if destino == "TikTok":
            usuario = marco._config.get("tiktok_usuario", "") or ""
            if not usuario:
                anunciar("Escribe tu usuario de TikTok en la ventana "
                          "Transmisión.")
                marco._on_transmision(None)
                return
        _snd.reproducir("conectando")
        anunciar("Revisando OBS antes de transmitir.")
        self.boton.Disable()

        def _revisar():
            try:
                preparacion = transmision_directa.preparar(
                    GestorPanelObs(), destino, obs_lanzador.asegurar_obs,
                    lambda frase: wx.CallAfter(anunciar, frase))
            except Exception as error:
                wx.CallAfter(self._revision_fallida, error)
            else:
                wx.CallAfter(self._revision_lista, preparacion, destino,
                             usuario)

        diagnostico.crear_hilo(_revisar, "BotonDirectoRevisar").start()

    def _revision_fallida(self, error):
        if not self._marco._alive:
            return
        self.boton.Enable()
        _snd.reproducir("error")
        anunciar(obs_cliente.mensaje_de_fallo_obs(error))

    def _revision_lista(self, preparacion, destino, usuario):
        marco = self._marco
        if not marco._alive:
            return
        self.boton.Enable()
        if preparacion.ya_transmitiendo:
            marco._obs_transmitiendo = True
            anunciar("OBS ya está transmitiendo. Con este mismo botón "
                      "puedes finalizar el directo.")
            marco._actualizar_boton_directo()
            return
        from ytchat.ui.gui_transmision import confirmar_transmision
        if not confirmar_transmision(marco, preparacion.revision):
            anunciar("No se transmitió.")
            return
        marco._supervisar_transmision("iniciar", destino, usuario)
        marco._actualizar_boton_directo()

    def _finalizar(self):
        marco = self._marco
        dialogo = wx.MessageDialog(
            marco,
            "¿Finalizar el directo? Quienes te están viendo dejarán de verte.",
            "Finalizar directo", wx.YES_NO | wx.NO_DEFAULT)
        try:
            dialogo.SetYesNoLabels("&Finalizar directo",
                                   "&Seguir transmitiendo")
            seguir = dialogo.ShowModal() != wx.ID_YES
        finally:
            dialogo.Destroy()
        if seguir:
            anunciar("Sigues transmitiendo.")
            return
        if marco._supervisar_transmision("activo"):
            marco._supervisar_transmision("detener")
            marco._actualizar_boton_directo()
            return

        def _detener():
            try:
                transmision_directa.finalizar(GestorPanelObs())
            except Exception as error:
                wx.CallAfter(self._finalizada_con_error, error)
            else:
                wx.CallAfter(self._finalizada)

        diagnostico.crear_hilo(_detener, "BotonDirectoFinalizar").start()

    def _finalizada(self):
        marco = self._marco
        if not marco._alive:
            return
        marco._obs_transmitiendo = False
        _snd.reproducir("desconectado")
        anunciar("Transmisión detenida.")
        marco._actualizar_boton_directo()

    def _finalizada_con_error(self, error):
        if not self._marco._alive:
            return
        _snd.reproducir("error")
        anunciar(obs_cliente.mensaje_de_fallo_obs(error))
