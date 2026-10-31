"""Página Cámara del diálogo de Preferencias.

Dueña de sus controles y de su guardado propio.
"""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.obs import obs_camara
from bellbird.obs import obs_cliente
from bellbird.ui.accesibilidad import anunciar
from bellbird.ui.preferencias_comun import (
    crear_panel, fila_label, opciones_con_elegida)


logger = diagnostico.obtener_logger(__name__)


class PaginaCamara:
    """Página Cámara: avisos de encuadre, cámara e inversión."""

    def __init__(self, ventana, config):
        self._ventana = ventana
        self._config = config

    def construir(self, parent):
        p = crear_panel(parent, "PagCamara")
        vs = wx.BoxSizer(wx.VERTICAL)

        self.chk_avisar_encuadre = wx.CheckBox(
            p, label=_("A&visar si el rostro sale del encuadre"),
            name="AvisarEncuadre")
        self.chk_avisar_encuadre.SetValue(
            bool(self._config.get("avisar_encuadre", False)))
        vs.Add(self.chk_avisar_encuadre, 0, wx.ALL, 10)

        vs.Add(fila_label(p, _("Cá&mara de OBS:")),
               0, wx.LEFT | wx.RIGHT, 10)
        guardada = str(self._config.get("camara_fuente", "") or "")
        opciones = opciones_con_elegida(
            _("Elegir automáticamente"), guardada, [])
        self.cho_camara_obs = wx.Choice(
            p, choices=opciones, name=_("Cámara de OBS"))
        self.cho_camara_obs.SetSelection(1 if guardada else 0)
        vs.Add(self.cho_camara_obs, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.btn_buscar_camaras = wx.Button(
            p, label=_("&Buscar cámaras en OBS"),
            name=_("Buscar cámaras en OBS"))
        vs.Add(self.btn_buscar_camaras, 0, wx.ALL, 10)
        self.btn_buscar_camaras.Bind(wx.EVT_BUTTON, self._buscar_camaras)

        self.chk_invertir_camara = wx.CheckBox(
            p, label=_("&Invertir izquierda y derecha"),
            name="InvertirCamara")
        self.chk_invertir_camara.SetValue(
            bool(self._config.get("camara_invertir", False)))
        vs.Add(self.chk_invertir_camara, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        p.SetSizer(vs)
        return p

    def _buscar_camaras(self, event):
        # Consultar OBS puede tardar o no responder, por eso nunca corre en la interfaz.
        def consultar():
            cliente = None
            try:
                cliente = obs_cliente.ClienteObs(obs_cliente.leer_ajustes())
                cliente.conectar()
                wx.CallAfter(
                    self._camaras_encontradas,
                    obs_camara.fuentes_video(cliente))
            except Exception as exc:
                wx.CallAfter(anunciar, obs_cliente.mensaje_de_fallo_obs(exc))
            finally:
                if cliente is not None:
                    try:
                        cliente.cerrar()
                    except Exception as error:
                        logger.debug("no se pudo cerrar el cliente de OBS: %s", error)

        diagnostico.crear_hilo(consultar, "CamarasPrefs").start()

    def _camaras_encontradas(self, fuentes):
        if not self._ventana:   # el diálogo pudo cerrarse mientras OBS respondía
            return
        elegida = self.cho_camara_obs.GetStringSelection()
        opciones = opciones_con_elegida(
            _("Elegir automáticamente"), elegida, fuentes)
        # La fuente guardada se conserva aunque OBS no responda o ya no la vea.
        self.cho_camara_obs.Set(opciones)
        self.cho_camara_obs.SetStringSelection(elegida or opciones[0])
        if len(fuentes) == 1:
            anunciar(_("Se encontró una cámara en OBS."))
        elif fuentes:
            anunciar(_("Se encontraron {cantidad} cámaras en OBS.").format(
                cantidad=len(fuentes)))
        else:
            anunciar(_("No hay ninguna cámara en OBS."))

    def guardar(self, fijar, en_memoria):
        avisar = bool(self.chk_avisar_encuadre.GetValue())
        fijar("transmision", "avisar_encuadre", "true" if avisar else "false")
        en_memoria["avisar_encuadre"] = avisar
        fuente = ("" if self.cho_camara_obs.GetSelection() == 0
                  else self.cho_camara_obs.GetStringSelection())
        fijar("transmision", "camara_fuente", fuente)
        en_memoria["camara_fuente"] = fuente
        invertir = bool(self.chk_invertir_camara.GetValue())
        fijar("transmision", "camara_invertir", "true" if invertir else "false")
        en_memoria["camara_invertir"] = invertir
