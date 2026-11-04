"""Menú Transmisión de la barra principal.

Qué comandos del directo tiene el menú Transmisión y cómo se mantiene al día
su estado.
"""

import wx

from bellbird.core.idioma import _
from bellbird.ui import encuadre_camara


def abrir_restream(frame) -> None:
    """Abre la ventana de Restream con la cuenta y los canales de la app."""
    from bellbird.core import paths
    from bellbird.restream import cuenta
    from bellbird.ui import restream_ventana

    def canales():
        return [(canal.id, canal.texto) for canal in cuenta.canales()]

    restream_ventana.abrir_restream(
        frame, cuenta.sesion(), canales, paths.perfiles_restream(),
        al_conectar=cuenta.conectar, al_reautorizar=cuenta.conectar,
        al_desconectar=cuenta.desconectar, destinos=cuenta.canales,
        perfil=cuenta.perfil, eliminar=cuenta.eliminar_canal,
        eventos=cuenta.eventos, estadisticas=cuenta.estadisticas)


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
    frame.mi_restream = m.Append(
        wx.ID_ANY, _("Re&stream…") + frame._accel("abrir_restream"))
    frame._bind_menu(frame.mi_restream, abrir_restream, frame)
    frame.mi_grabar_al_transmitir = m.AppendCheckItem(
        wx.ID_ANY, _("&Grabar también al transmitir"))
    frame.mi_grabar_al_transmitir.Check(
        bool(frame._config.get("grabar_al_transmitir", False)))
    _agregar_encuadre(frame, m)
    mb.Append(m, _("&Transmisión"))
    _enlazar(frame, m)


def _enlazar(frame, m):
    """Conecta el menú Transmisión ya armado con sus manejadores."""
    from bellbird.ui import gui_transmitir
    frame._bind_menu(frame.mi_grabar_al_transmitir,
                     gui_transmitir.alternar_grabar_al_transmitir, frame)
