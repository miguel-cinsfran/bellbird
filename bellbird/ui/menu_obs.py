"""Menú OBS de la barra principal.

Qué comandos de OBS tiene la barra y cómo se mantiene al día su estado.
"""

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.obs import obs_entradas_audio
from bellbird.obs import obs_ventana
from bellbird.ui.accesibilidad import anunciar


def mostrar_obs() -> None:
    """Trae al frente la ventana principal de OBS, si está abierto."""
    texto = obs_ventana.mostrar()
    if texto:
        anunciar(texto)


def abrir_obs(frame) -> None:
    """Abre el panel de OBS en su pestaña Transmisión."""
    from bellbird.ui import obs_ventana

    obs_ventana.abrir_obs(
        frame, frame, pestana=obs_ventana.PESTANA_TRANSMISION)


def _agregar_comandos(m, frame):
    """Arma los comandos del menú OBS en su orden."""
    frame.mi_obs_panel = m.Append(
        wx.ID_ANY, _("Panel de &OBS…") + frame._accel("abrir_obs"))
    frame._bind_menu(frame.mi_obs_panel, abrir_obs, frame)
    frame.mi_obs_micro = m.AppendCheckItem(
        wx.ID_ANY, _("Silenciar &micrófono de OBS") + frame._accel("obs_micro"))
    frame.mi_micro_obs = m.Append(wx.ID_ANY, _("&Elegir micrófono…"))
    frame.mi_mostrar_obs = m.Append(
        wx.ID_ANY, _("Mos&trar OBS") + frame._accel("mostrar_obs"))
    frame.mi_obs_grabar = m.Append(
        wx.ID_ANY,
        _("Iniciar o detener g&rabación") + frame._accel("obs_grabar"))
    frame.mi_obs_pausar_grabacion = m.Append(
        wx.ID_ANY,
        _("Pa&usar o reanudar grabación") + frame._accel("obs_pausar_grabacion"))
    frame.mi_obs_guardar_clip = m.Append(
        wx.ID_ANY, _("Guardar cl&ip") + frame._accel("guardar_clip"))
    m.AppendSeparator()
    frame.mi_avisos_sobrecarga = m.AppendCheckItem(
        wx.ID_ANY,
        _("&Avisar si OBS se sobrecarga") + frame._accel("avisos_sobrecarga"))
    frame.mi_avisos_sobrecarga.Check(
        bool(frame._config.get("avisar_sobrecarga", True)))


def construir(frame, mb):
    m = wx.Menu()
    _agregar_comandos(m, frame)
    mb.Append(m, _("&OBS"))
    _enlazar(frame, m)


def _enlazar(frame, m):
    """Conecta el menú OBS ya armado con sus manejadores."""
    from bellbird.ui import comandos_clips
    from bellbird.ui import comandos_grabacion
    from bellbird.ui import gui_microfono
    frame.Bind(wx.EVT_MENU, frame._on_obs_micro, frame.mi_obs_micro)
    frame._bind_menu(frame.mi_micro_obs, gui_microfono.abrir_microfono_obs, frame)
    frame.Bind(wx.EVT_MENU_OPEN, lambda e: _al_abrir_obs(frame, m, e))
    frame._bind_menu(frame.mi_mostrar_obs, mostrar_obs)
    frame._bind_menu(frame.mi_obs_grabar,
                     comandos_grabacion.alternar_grabacion, frame)
    frame._bind_menu(frame.mi_obs_pausar_grabacion,
                     comandos_grabacion.alternar_pausa_grabacion, frame)
    frame._bind_menu(frame.mi_obs_guardar_clip,
                     comandos_clips.guardar_clip, frame)
    frame._bind_menu(frame.mi_avisos_sobrecarga,
                     frame._alternar_aviso_sobrecarga)


def _al_abrir_obs(frame, menu, evento):
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
