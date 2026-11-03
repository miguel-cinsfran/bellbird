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


def mostrar_obs() -> None:
    """Trae al frente la ventana principal de OBS, si está abierto."""
    texto = obs_ventana.mostrar()
    if texto:
        anunciar(texto)


def abrir_restream(frame) -> None:
    """Abre la ventana de Restream con la cuenta y los canales de la app."""
    from bellbird.core import paths
    from bellbird.restream import cuenta
    from bellbird.ui import restream_ventana

    def canales():
        return [(canal.id, canal.texto) for canal in cuenta.canales()]

    restream_ventana.abrir_restream(
        frame, cuenta.sesion(), canales, paths.perfiles_restream(),
        al_conectar=cuenta.conectar,
        al_reautorizar=cuenta.conectar,
        al_desconectar=cuenta.desconectar,
        destinos=cuenta.canales,
        perfil=cuenta.perfil,
        eliminar=cuenta.eliminar_canal)


def abrir_obs(frame) -> None:
    """Abre el panel de OBS en su pestaña Transmisión."""
    from bellbird.ui import obs_ventana

    obs_ventana.abrir_obs(
        frame, frame, pestana=obs_ventana.PESTANA_TRANSMISION)


def abrir_escena(frame) -> None:
    """Abre el panel de OBS en la pestaña Escena."""
    from bellbird.ui import obs_ventana

    obs_ventana.abrir_obs(
        frame, frame, pestana=obs_ventana.PESTANA_ESCENA)


def abrir_grabacion(frame) -> None:
    """Abre el panel de OBS en la pestaña Grabación."""
    from bellbird.ui import obs_ventana

    obs_ventana.abrir_obs(
        frame, frame, pestana=obs_ventana.PESTANA_GRABACION)


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


def _agregar_ventanas(frame, m):
    """Los comandos que abren las ventanas de transmisión."""
    frame.mi_transmision = m.Append(
        wx.ID_ANY, _("&Panel de transmisión…") + frame._accel("abrir_transmision"))
    frame.mi_restream = m.Append(
        wx.ID_ANY, _("Re&stream…") + frame._accel("abrir_restream"))
    frame._bind_menu(frame.mi_restream, abrir_restream, frame)
    frame.mi_obs_panel = m.Append(
        wx.ID_ANY, _("Panel de &OBS…") + frame._accel("abrir_obs"))
    frame._bind_menu(frame.mi_obs_panel, abrir_obs, frame)
    frame.mi_escena = m.Append(
        wx.ID_ANY, _("Esce&na…") + frame._accel("abrir_escena"))
    frame._bind_menu(frame.mi_escena, abrir_escena, frame)
    frame.mi_grabacion = m.Append(
        wx.ID_ANY, _("Gra&bación…") + frame._accel("abrir_grabacion"))
    frame._bind_menu(frame.mi_grabacion, abrir_grabacion, frame)


def _agregar_avisos(frame, m):
    """Las casillas de avisos al transmitir."""
    frame.mi_avisos_sobrecarga = m.AppendCheckItem(
        wx.ID_ANY,
        _("&Avisar si OBS se sobrecarga") + frame._accel("avisos_sobrecarga"))
    frame.mi_avisos_sobrecarga.Check(bool(frame._config.get("avisar_sobrecarga", True)))
    frame.mi_grabar_al_transmitir = m.AppendCheckItem(
        wx.ID_ANY, _("&Grabar también al transmitir"))
    frame.mi_grabar_al_transmitir.Check(bool(frame._config.get("grabar_al_transmitir", False)))


def construir(frame, mb):
    m = wx.Menu()
    _agregar_ventanas(frame, m)
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
    _agregar_avisos(frame, m)
    _agregar_encuadre(frame, m)
    mb.Append(m, _("&Transmisión"))
    _enlazar(frame, m)


def _enlazar(frame, m):
    """Conecta el menú Transmisión ya armado con sus manejadores."""
    from bellbird.ui import comandos_grabacion
    from bellbird.ui import gui_microfono
    from bellbird.ui import gui_transmitir
    frame.Bind(wx.EVT_MENU,
              lambda e: wx.CallAfter(frame._on_transmision, None),
              frame.mi_transmision)
    frame.Bind(wx.EVT_MENU, frame._on_obs_micro, frame.mi_obs_micro)
    frame._bind_menu(frame.mi_micro_obs, gui_microfono.abrir_microfono_obs, frame)
    frame.Bind(wx.EVT_MENU_OPEN, lambda e: _al_abrir_transmision(frame, m, e))
    frame._bind_menu(frame.mi_mostrar_obs, mostrar_obs)
    frame._bind_menu(frame.mi_obs_grabar,
                     comandos_grabacion.alternar_grabacion, frame)
    frame._bind_menu(frame.mi_obs_pausar_grabacion,
                     comandos_grabacion.alternar_pausa_grabacion, frame)
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
