"""Menú Transmisión de la barra principal.

Qué comandos tiene el menú Transmisión y cómo se mantiene al día su estado.
"""

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.obs import obs_entradas_audio
from bellbird.obs import obs_ventana
from bellbird.ui.accesibilidad import anunciar


def _mostrar_obs() -> None:
    """Trae al frente la ventana principal de OBS, si está abierto."""
    texto = obs_ventana.mostrar()
    if texto:
        anunciar(texto)


def construir(frame, mb):
    from bellbird.ui import gui_microfono
    from bellbird.ui import gui_transmitir
    m = wx.Menu()
    frame.mi_transmision = m.Append(
        wx.ID_ANY, _("&Panel de transmisión…") + frame._accel("abrir_transmision"))
    frame.mi_obs_micro = m.AppendCheckItem(
        wx.ID_ANY, _("Silenciar el &micrófono de OBS") + frame._accel("obs_micro"))
    frame.mi_micro_obs = m.Append(wx.ID_ANY, _("&Elegir micrófono…"))
    frame.mi_mostrar_obs = m.Append(
        wx.ID_ANY, _("Mostrar &OBS") + frame._accel("mostrar_obs"))
    frame.mi_avisos_sobrecarga = m.AppendCheckItem(
        wx.ID_ANY,
        _("&Avisar cuando OBS no da abasto") + frame._accel("avisos_sobrecarga"))
    frame.mi_avisos_sobrecarga.Check(bool(frame._config.get("avisar_sobrecarga", True)))
    frame.mi_grabar_al_transmitir = m.AppendCheckItem(
        wx.ID_ANY, _("&Grabar también al transmitir"))
    frame.mi_grabar_al_transmitir.Check(bool(frame._config.get("grabar_al_transmitir", False)))
    mb.Append(m, _("&Transmisión"))
    frame.Bind(wx.EVT_MENU,
              lambda e: wx.CallAfter(frame._on_transmision, None),
              frame.mi_transmision)
    frame.Bind(wx.EVT_MENU, frame._on_obs_micro, frame.mi_obs_micro)
    frame._bind_menu(frame.mi_micro_obs, gui_microfono.abrir_microfono_obs, frame)
    frame.Bind(wx.EVT_MENU_OPEN, lambda e: _al_abrir_transmision(frame, m, e))
    frame._bind_menu(frame.mi_mostrar_obs, _mostrar_obs)
    frame._bind_menu(frame.mi_avisos_sobrecarga, frame._alternar_aviso_sobrecarga)
    frame._bind_menu(frame.mi_grabar_al_transmitir,
                     gui_transmitir.alternar_grabar_al_transmitir, frame)


def _al_abrir_transmision(frame, menu, evento):
    evento.Skip()
    if evento.GetMenu() is not menu:
        return
    if getattr(frame, "_consultando_micro", False):
        return
    frame._consultando_micro = True
    preferido = frame._config.get("obs_microfono", "")
    def _consultar():
        try:
            estado = obs_entradas_audio.estado_microfono(preferido)
        finally:
            frame._consultando_micro = False
        if estado is not None:
            wx.CallAfter(frame.mi_obs_micro.Check, estado)
    diagnostico.crear_hilo(_consultar, "MicrofonoEstado").start()
