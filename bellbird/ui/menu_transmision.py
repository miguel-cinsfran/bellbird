"""Menú Transmisión de la barra principal.

Qué comandos tiene el menú Transmisión y cómo se mantiene al día su estado.
"""

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.obs import obs_entradas_audio
from bellbird.obs import obs_ventana
from bellbird.ui import encuadre_camara
from bellbird.ui.accesibilidad import anunciar


def _mostrar_obs() -> None:
    """Trae al frente la ventana principal de OBS, si está abierto."""
    texto = obs_ventana.mostrar()
    if texto:
        anunciar(texto)


def _agregar_encuadre(frame, m):
    """La sección de encuadre: anuncio a pedido y casilla de avisos."""
    m.AppendSeparator()
    frame.mi_anunciar_encuadre = m.Append(
        wx.ID_ANY, _("Anunciar en&cuadre de cámara") + frame._accel("anunciar_encuadre"))
    frame.mi_avisos_encuadre = m.AppendCheckItem(
        wx.ID_ANY, _("A&visar si el rostro sale del encuadre") + frame._accel("avisos_encuadre"))
    frame.mi_avisos_encuadre.Check(bool(frame._config.get("avisar_encuadre", False)))
    frame._bind_menu(frame.mi_anunciar_encuadre,
                     encuadre_camara.anunciar_encuadre, frame)
    frame._bind_menu(frame.mi_avisos_encuadre,
                     encuadre_camara.alternar_avisos, frame)
    encuadre_camara.sincronizar(frame)


def construir(frame, mb):
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
    _agregar_encuadre(frame, m)
    mb.Append(m, _("&Transmisión"))
    _enlazar(frame, m)


def _enlazar(frame, m):
    """Conecta el menú Transmisión ya armado con sus manejadores."""
    from bellbird.ui import gui_microfono
    from bellbird.ui import gui_transmitir
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
