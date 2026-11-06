"""Página Transmisión del diálogo de Preferencias.

Dueña de sus controles y de su guardado propio. El diálogo la construye
por composición y copia solo los controles que lee su tabla de opciones
simples.
"""

from __future__ import annotations

import wx

from guyrapu.core import diagnostico
from guyrapu.core.comando_clip import COMANDO as COMANDO_CLIP
from guyrapu.core.idioma import N_, _
from guyrapu.obs import obs_activacion
from guyrapu.obs import obs_cliente
from guyrapu.ui.accesibilidad import ContadorAccesible, anunciar
from guyrapu.ui.preferencias_comun import crear_panel, fila_label


logger = diagnostico.obtener_logger(__name__)

OPCIONES_CLIPS = (
    (0, N_("Desactivados")),
    (30, N_("30 segundos")),
    (60, N_("60 segundos")),
)


class PaginaTransmision:
    """Página Transmisión: aviso de sobrecarga, puerto y micrófono de OBS."""

    def __init__(self, ventana, config):
        self._ventana = ventana
        self._config = config

    def _casillas_de_aviso(self, p, vs):
        avisar = wx.CheckBox(
            p, label=_("A&visar si OBS se sobrecarga"),
            name="AvisarSobrecargaObs")
        vs.Add(avisar, 0, wx.ALL, 10)
        titulo = wx.CheckBox(
            p, label=_("Mostrar en el &título de la ventana si se transmite o se graba"),
            name="TituloEstadoObs")
        vs.Add(titulo, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        return avisar, titulo

    def _agregar_clips(self, p, vs):
        """Lista la duración del búfer que OBS prepara al iniciar el directo."""
        vs.Add(fila_label(p, _("C&lips:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.cho_clips = wx.Choice(
            p, choices=[_(texto) for _segundos, texto in OPCIONES_CLIPS],
            name=_("Clips"))
        valores = [segundos for segundos, _texto in OPCIONES_CLIPS]
        try:
            guardado = int(self._config.get("clips", 30))
        except (TypeError, ValueError):
            guardado = 30
        self.cho_clips.SetSelection(
            valores.index(guardado) if guardado in valores else 1)
        vs.Add(self.cho_clips, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_clips_chat = wx.CheckBox(
            p,
            label=_("Permitir {comando} en el c&hat").format(
                comando=COMANDO_CLIP),
            name=_("Permitir {comando} en el chat").format(
                comando=COMANDO_CLIP))
        self.chk_clips_chat.SetValue(bool(self._config.get("clips_chat", True)))
        vs.Add(self.chk_clips_chat, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(fila_label(p, _("Espe&ra entre clips del chat (minutos):")),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_clips_chat_espera = ContadorAccesible(
            p, min=1, max=60,
            name=_("Espera entre clips del chat"))
        try:
            minutos = int(self._config.get("clips_chat_espera", 1))
        except (TypeError, ValueError):
            minutos = 1
        self.sp_clips_chat_espera.SetValue(min(60, max(1, minutos)))
        vs.Add(self.sp_clips_chat_espera, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _agregar_puerto(self, p, vs):
        vs.Add(fila_label(p, _("&Puerto del chat en el vídeo:")),
               0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.sp_puerto_overlay = ContadorAccesible(
            p, min=1024, max=65535,
            name=_("Puerto del chat en el vídeo"))
        vs.Add(self.sp_puerto_overlay, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def construir(self, parent):
        p = crear_panel(parent, "PagTransmision")
        vs = wx.BoxSizer(wx.VERTICAL)

        self.chk_avisar_sobrecarga, self.chk_titulo_estado_obs = self._casillas_de_aviso(p, vs)

        self._agregar_clips(p, vs)

        self._agregar_puerto(p, vs)

        self.btn_activar_servidor_websocket_obs = wx.Button(
            p, label=_("&Activar servidor WebSocket de OBS"),
            name=_("Activar servidor WebSocket de OBS"))
        vs.Add(self.btn_activar_servidor_websocket_obs, 0, wx.ALL, 10)
        self.btn_activar_servidor_websocket_obs.Bind(
            wx.EVT_BUTTON, self._activar_servidor_websocket_obs)

        p.SetSizer(vs)
        return p

    def _activar_servidor_websocket_obs(self, event):
        def activar():
            try:
                accion, mensaje = obs_activacion.decidir_activacion(
                    obs_activacion.obs_esta_en_ejecucion(),
                    obs_cliente.leer_ajustes())
                if accion == obs_activacion.ACTIVAR:
                    mensaje = obs_activacion.activar_servidor(
                        obs_cliente.RUTA_CONFIG_OBS)
            except Exception as exc:
                logger.warning("No se pudo activar el servidor websocket de OBS: %s", exc)
                mensaje = _("No se pudo activar el servidor WebSocket de OBS: {exc}").format(exc=exc)
            wx.CallAfter(anunciar, mensaje)

        diagnostico.crear_hilo(activar, "ActivarWebsocketObs").start()

    def guardar(self, fijar, en_memoria):
        segundos = OPCIONES_CLIPS[max(0, self.cho_clips.GetSelection())][0]
        fijar("transmision", "clips", str(segundos))
        en_memoria["clips"] = segundos
        clips_chat = self.chk_clips_chat.GetValue()
        fijar("transmision", "clips_chat", "true" if clips_chat else "false")
        en_memoria["clips_chat"] = clips_chat
        minutos = int(self.sp_clips_chat_espera.GetValue())
        fijar("transmision", "clips_chat_espera", str(minutos))
        en_memoria["clips_chat_espera"] = minutos
