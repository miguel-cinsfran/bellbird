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
from guyrapu.ui import agregar_camara
from guyrapu.ui.accesibilidad import anunciar
from guyrapu.ui.agregar_camara import cerrar_cliente
from guyrapu.ui.preferencias_comun import (
    crear_panel, fila_label, opciones_con_elegida)
from guyrapu.voice import sonido_memoria


class PaginaCamara:
    """Página Cámara: avisos de encuadre, cámara e inversión."""

    def __init__(self, ventana, config):
        self._ventana = ventana
        self._config = config

    def construir(self, parent):
        p = crear_panel(parent, "PagCamara")
        vs = wx.BoxSizer(wx.VERTICAL)
        self._avisos(p, vs)
        self._camara(p, vs)
        self._invertir(p, vs)
        self._sonido(p, vs)
        p.SetSizer(vs)
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
        self.btn_buscar_camaras = wx.Button(
            p, label=_("&Buscar cámaras en OBS"),
            name=_("Buscar cámaras en OBS"))
        vs.Add(self.btn_buscar_camaras, 0, wx.ALL, 10)
        self.btn_buscar_camaras.Bind(wx.EVT_BUTTON, self._buscar_camaras)
        self._boton_agregar(p, vs)

    def _boton_agregar(self, p, vs):
        self.btn_agregar_camara = wx.Button(
            p, label=_("&Agregar cámara a OBS…"),
            name=_("Agregar cámara a OBS…"))
        vs.Add(self.btn_agregar_camara, 0,
               wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_agregar_camara.Bind(
            wx.EVT_BUTTON,
            lambda evento: agregar_camara.agregar(
                self._ventana, self._llenar_camaras))

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

    def _elegir_sonido(self, event):
        timbre = tono_guia.TIMBRES[self.cho_sonido_guia.GetSelection()]
        sonido_memoria.reproducir(tono_guia.muestra(timbre))

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
                cerrar_cliente(cliente)

        diagnostico.crear_hilo(consultar, "CamarasPrefs").start()

    def _llenar_camaras(self, fuentes):
        elegida = self.cho_camara_obs.GetStringSelection()
        opciones = opciones_con_elegida(
            _("Elegir automáticamente"), elegida, fuentes)
        # La fuente guardada se conserva aunque OBS no responda o ya no la vea.
        self.cho_camara_obs.Set(opciones)
        self.cho_camara_obs.SetStringSelection(elegida or opciones[0])

    def _camaras_encontradas(self, fuentes):
        if not self._ventana:   # el diálogo pudo cerrarse mientras OBS respondía
            return
        self._llenar_camaras(fuentes)
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
        timbre = tono_guia.TIMBRES[self.cho_sonido_guia.GetSelection()]
        fijar("transmision", "guia_timbre", timbre)
        en_memoria["guia_timbre"] = timbre
