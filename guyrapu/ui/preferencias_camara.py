"""Página Cámara del diálogo de Preferencias.

Dueña de sus controles y de su guardado propio.
"""

from __future__ import annotations

import wx

from guyrapu.camera import tono_guia
from guyrapu.core import diagnostico
from guyrapu.core.idioma import _
from guyrapu.obs import obs_camara
from guyrapu.obs import obs_cliente
from guyrapu.ui.agregar_camara import cerrar_cliente
from guyrapu.ui.preferencias_comun import (
    crear_panel, fila_label, opciones_con_elegida)
from guyrapu.voice import sonido_memoria

logger = diagnostico.obtener_logger(__name__)


class PaginaCamara:
    """Página Cámara: avisos de encuadre, cámara e inversión."""

    def __init__(self, ventana, config):
        self._ventana = ventana
        self._config = config
        self._consultadas = False

    def construir(self, parent):
        p = crear_panel(parent, "PagCamara")
        vs = wx.BoxSizer(wx.VERTICAL)
        self._avisos(p, vs)
        self._camara(p, vs)
        self._invertir(p, vs)
        self._sonido(p, vs)
        self._atajos_globales(p, vs)
        p.SetSizer(vs)
        p.Bind(wx.EVT_SHOW, self._al_mostrar)
        return p

    def _avisos(self, p, vs):
        self.chk_avisar_encuadre = wx.CheckBox(
            p, label=_("A&visar si el rostro sale del encuadre"),
            name="AvisarEncuadre")
        self.chk_avisar_encuadre.SetValue(
            bool(self._config.get("avisar_encuadre", False)))
        vs.Add(self.chk_avisar_encuadre, 0, wx.ALL, 10)

    def _camara(self, p, vs):
        vs.Add(fila_label(p, _("Cá&mara de OBS:")),
               0, wx.LEFT | wx.RIGHT, 10)
        guardada = str(self._config.get("camara_fuente", "") or "")
        opciones = opciones_con_elegida(
            _("Elegir automáticamente"), guardada, [])
        self.cho_camara_obs = wx.Choice(
            p, choices=opciones, name=_("Cámara de OBS"))
        self.cho_camara_obs.SetSelection(1 if guardada else 0)
        vs.Add(self.cho_camara_obs, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _invertir(self, p, vs):
        self.chk_invertir_camara = wx.CheckBox(
            p, label=_("&Invertir izquierda y derecha"),
            name="InvertirCamara")
        self.chk_invertir_camara.SetValue(
            bool(self._config.get("camara_invertir", False)))
        vs.Add(self.chk_invertir_camara, 0, wx.ALL, 10)

    def _sonido(self, p, vs):
        vs.Add(fila_label(p, _("&Sonido de la guía:")),
               0, wx.LEFT | wx.RIGHT, 10)
        timbre = tono_guia.normalizar_timbre(
            self._config.get("guia_timbre", "normal"))
        self.cho_sonido_guia = wx.Choice(
            p, choices=[_("Normal"), _("Cálido"), _("8 bits")],
            name=_("Sonido de la guía"))
        self.cho_sonido_guia.SetSelection(tono_guia.TIMBRES.index(timbre))
        vs.Add(self.cho_sonido_guia, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.cho_sonido_guia.Bind(wx.EVT_CHOICE, self._elegir_sonido)

    def _atajos_globales(self, p, vs):
        self.chk_camara_atajos_globales = wx.CheckBox(
            p, label=_("Usar atajos de cámara en cualquier a&plicación"),
            name="CamaraAtajosGlobales")
        self.chk_camara_atajos_globales.SetValue(
            bool(self._config.get("camara_atajos_globales", False)))
        vs.Add(self.chk_camara_atajos_globales, 0,
               wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _elegir_sonido(self, event):
        timbre = tono_guia.TIMBRES[self.cho_sonido_guia.GetSelection()]
        sonido_memoria.reproducir(tono_guia.muestra(timbre))

    def _al_mostrar(self, evento):
        """Consulta OBS la primera vez que la página queda a la vista."""
        evento.Skip()
        if not evento.IsShown() or self._consultadas:
            return
        self._consultadas = True
        self._consultar_camaras()

    def _consultar_camaras(self):
        # Consultar OBS puede tardar o no responder, por eso nunca corre en la interfaz.
        def consultar():
            cliente = None
            try:
                cliente = obs_cliente.ClienteObs(obs_cliente.leer_ajustes())
                cliente.conectar()
                fuentes = obs_camara.fuentes_video(cliente)
            except Exception as exc:
                logger.debug("no se pudieron leer las cámaras de OBS: %s", exc)
                return
            finally:
                cerrar_cliente(cliente)
            wx.CallAfter(self._aplicar_fuentes, fuentes)

        diagnostico.crear_hilo(consultar, "CamarasPrefs").start()

    def _aplicar_fuentes(self, fuentes):
        if self._ventana is not None and not self._ventana:
            return
        self._llenar_camaras(fuentes)

    def _llenar_camaras(self, fuentes):
        elegida = self.cho_camara_obs.GetStringSelection()
        opciones = opciones_con_elegida(
            _("Elegir automáticamente"), elegida, fuentes)
        # La fuente guardada se conserva aunque OBS no responda o ya no la vea.
        self.cho_camara_obs.Set(opciones)
        self.cho_camara_obs.SetStringSelection(elegida or opciones[0])

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
        timbre = tono_guia.TIMBRES[self.cho_sonido_guia.GetSelection()]
        fijar("transmision", "guia_timbre", timbre)
        en_memoria["guia_timbre"] = timbre
        self._guardar_atajos_globales(fijar, en_memoria)

    def _guardar_atajos_globales(self, fijar, en_memoria):
        globales = bool(self.chk_camara_atajos_globales.GetValue())
        fijar("transmision", "camara_atajos_globales",
              "true" if globales else "false")
        en_memoria["camara_atajos_globales"] = globales
