"""Menú Transmisión de la barra principal.

Qué comandos del directo tiene el menú Transmisión y cómo se mantiene al día
su estado.
"""

import wx

from guyrapu.core.idioma import _
from guyrapu.obs import transmision_directa


def abrir_restream(frame) -> None:
    """Abre la ventana de Restream con la cuenta y los canales de la app."""
    from guyrapu.core import paths
    from guyrapu.restream import cuenta
    from guyrapu.ui import restream_ventana

    def canales():
        return [(canal.id, canal.texto) for canal in cuenta.canales()]

    restream_ventana.abrir_restream(
        frame, cuenta.sesion(), canales, paths.perfiles_restream(),
        al_conectar=cuenta.conectar, al_reautorizar=cuenta.conectar,
        al_desconectar=cuenta.desconectar, destinos=cuenta.canales,
        perfil=cuenta.perfil, eliminar=cuenta.eliminar_canal,
        eventos=cuenta.eventos, estadisticas=cuenta.estadisticas)


def _pulsar_directo(frame):
    """El comando del menú hace lo mismo que el botón de la ventana."""
    frame._boton_directo.pulsar()


def construir(frame, mb):
    m = wx.Menu()
    etiqueta, _nombre = transmision_directa.etiqueta(False)
    frame.mi_directo = m.Append(wx.ID_ANY, etiqueta)
    frame._bind_menu(frame.mi_directo, _pulsar_directo, frame)
    frame.mi_restream = m.Append(
        wx.ID_ANY, _("Re&stream…") + frame._accel("abrir_restream"))
    frame._bind_menu(frame.mi_restream, abrir_restream, frame)
    frame.mi_grabar_al_transmitir = m.AppendCheckItem(
        wx.ID_ANY, _("&Grabar también al transmitir"))
    frame.mi_grabar_al_transmitir.Check(
        bool(frame._config.get("grabar_al_transmitir", False)))
    mb.Append(m, _("&Transmisión"))
    _enlazar(frame, m)
    frame._actualizar_boton_directo()


def _enlazar(frame, m):
    """Conecta el menú Transmisión ya armado con sus manejadores."""
    from guyrapu.ui import gui_transmitir
    frame._bind_menu(frame.mi_grabar_al_transmitir,
                     gui_transmitir.alternar_grabar_al_transmitir, frame)
