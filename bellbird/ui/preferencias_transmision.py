"""Página Transmisión del diálogo de Preferencias.

Dueña de sus controles y de su guardado propio. El diálogo la construye
por composición y copia solo los controles que lee su tabla de opciones
simples.
"""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.obs import obs_activacion
from bellbird.obs import obs_cliente
from bellbird.obs.obs_panel import GestorPanelObs
from bellbird.ui.accesibilidad import ContadorAccesible, anunciar
from bellbird.ui.preferencias_comun import (
    crear_panel, fila_label, opciones_con_elegida)


logger = diagnostico.obtener_logger(__name__)


class PaginaTransmision:
    """Página Transmisión: aviso de sobrecarga, puerto y micrófono de OBS."""

    def __init__(self, ventana, config):
        self._ventana = ventana
        self._config = config

    def construir(self, parent):
        p = crear_panel(parent, "PagTransmision")
        vs = wx.BoxSizer(wx.VERTICAL)

        self.chk_avisar_sobrecarga = wx.CheckBox(
            p, label=_("A&visar cuando OBS no da abasto"),
            name="AvisarSobrecargaObs")
        vs.Add(self.chk_avisar_sobrecarga, 0, wx.ALL, 10)

        vs.Add(fila_label(p, _("&Puerto del panel de chat:")),
               0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.sp_puerto_overlay = ContadorAccesible(
            p, min=1024, max=65535,
            name=_("Puerto del panel de chat"))
        vs.Add(self.sp_puerto_overlay, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(fila_label(p, _("&Micrófono de OBS:")),
               0, wx.LEFT | wx.RIGHT, 10)
        guardado = str(self._config.get("obs_microfono", ""))
        opciones = opciones_con_elegida(
            _("Elegir automáticamente"), guardado, [])
        self.cho_microfono_obs = wx.Choice(p, choices=opciones, name=_("Micrófono de OBS"))
        self.cho_microfono_obs.SetSelection(1 if guardado else 0)
        vs.Add(self.cho_microfono_obs, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.btn_buscar_microfonos = wx.Button(
            p, label=_("&Buscar micrófonos en OBS"),
            name=_("Buscar micrófonos en OBS"))
        vs.Add(self.btn_buscar_microfonos, 0, wx.ALL, 10)
        self.btn_buscar_microfonos.Bind(wx.EVT_BUTTON, self._buscar_microfonos)

        self.btn_activar_servidor_websocket_obs = wx.Button(
            p, label=_("&Activar servidor WebSocket de OBS"),
            name=_("Activar servidor WebSocket de OBS"))
        vs.Add(self.btn_activar_servidor_websocket_obs, 0, wx.ALL, 10)
        self.btn_activar_servidor_websocket_obs.Bind(
            wx.EVT_BUTTON, self._activar_servidor_websocket_obs)

        p.SetSizer(vs)
        return p

    def _buscar_microfonos(self, event):
        # Consultar OBS puede tardar o no responder, por eso nunca corre en la interfaz.
        def consultar():
            gestor = None
            try:
                gestor = GestorPanelObs(ajustes=obs_cliente.leer_ajustes())
                gestor.conectar()
                wx.CallAfter(self._microfonos_encontrados, gestor.fuentes_audio())
            except Exception as exc:
                wx.CallAfter(anunciar, obs_cliente.mensaje_de_fallo_obs(exc))
            finally:
                if gestor is not None:
                    try:
                        gestor.cerrar()
                    except Exception as error:
                        logger.debug("no se pudo cerrar el gestor de OBS: %s", error)

        diagnostico.crear_hilo(consultar, "MicrofonosPrefs").start()

    def _microfonos_encontrados(self, fuentes):
        if not self._ventana:   # el diálogo pudo cerrarse mientras OBS respondía
            return
        elegido = self.cho_microfono_obs.GetStringSelection()
        opciones = opciones_con_elegida(
            _("Elegir automáticamente"), elegido, fuentes)
        # La fuente guardada se conserva aunque OBS no responda o ya no la vea.
        self.cho_microfono_obs.Set(opciones)
        self.cho_microfono_obs.SetStringSelection(elegido or opciones[0])
        anunciar(_("Se encontraron {cantidad} micrófonos en OBS").format(cantidad=len(fuentes)))

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
                mensaje = _("No se pudo activar el servidor websocket de OBS: {exc}").format(exc=exc)
            wx.CallAfter(anunciar, mensaje)

        diagnostico.crear_hilo(activar, "ActivarWebsocketObs").start()

    def guardar(self, fijar, en_memoria):
        microfono_obs = ("" if self.cho_microfono_obs.GetSelection() == 0
                         else self.cho_microfono_obs.GetStringSelection())
        fijar("obs", "microfono", microfono_obs)
        en_memoria["obs_microfono"] = microfono_obs
