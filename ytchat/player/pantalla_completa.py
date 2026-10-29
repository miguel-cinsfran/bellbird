"""Ventana sin bordes a pantalla completa para el vídeo del reproductor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import wx

from ytchat.core import config as _cfg
from ytchat.core import diagnostico
from ytchat.core.idioma import _
from ytchat.ui.accesibilidad import nombre_accesible

logger = diagnostico.obtener_logger(__name__)


@dataclass
class AccionesPantalla:
    """Acciones del panel que la pantalla completa pide con teclas o cierre."""
    salir: Callable[[], None]
    pausa: Callable[[], None]
    buscar_rel: Callable[[int], None]
    volumen: Callable[[int], None]
    silenciar: Callable[[], None]
    buscar_porcentaje: Callable[[int], None]


def accion_de_tecla(codigo: int, mods: int,
                    acciones: AccionesPantalla) -> Callable | None:
    """Qué hace una tecla suelta (estilo VLC/YouTube), o None.

    Con modificadores, o con una tecla que no está en la cadena, devuelve
    None para que la tecla siga su camino con `event.Skip()`.
    """
    if mods == wx.MOD_NONE:
        if codigo in (wx.WXK_SPACE, wx.WXK_MEDIA_PLAY_PAUSE):
            return acciones.pausa
        if codigo == wx.WXK_LEFT:
            return lambda: acciones.buscar_rel(-10_000)
        if codigo == wx.WXK_RIGHT:
            return lambda: acciones.buscar_rel(+10_000)
        if codigo == wx.WXK_UP:
            return lambda: acciones.volumen(+5)
        if codigo == wx.WXK_DOWN:
            return lambda: acciones.volumen(-5)
        if codigo == ord("M"):
            return acciones.silenciar
        if codigo == ord("F"):
            return acciones.salir
        if ord("0") <= codigo <= ord("9"):
            return lambda: acciones.buscar_porcentaje((codigo - ord("0")) * 10)
        if wx.WXK_NUMPAD0 <= codigo <= wx.WXK_NUMPAD9:
            return lambda: acciones.buscar_porcentaje(
                (codigo - wx.WXK_NUMPAD0) * 10)
    return None


class PantallaCompleta(wx.Frame):
    """Ventana sin bordes a pantalla completa para el vídeo.

    Atiende Escape, F11, los atajos del reproductor de Preferencias y las
    teclas de VLC y YouTube (espacio, flechas, M, F y 0 a 9), porque los
    aceleradores del menú principal no llegan a esta ventana y sin eso
    sería una trampa de teclado.
    """

    def __init__(self, atajos: dict, acciones: AccionesPantalla):
        # Título = el de la ventana principal, no un genérico: es lo que
        # anuncia el lector y lo que sale en Alt+Tab al entrar.
        try:
            principal = wx.GetApp().GetTopWindow()
            titulo = (principal.GetTitle() if principal else "") or _cfg.APP_NAME
        except Exception:
            titulo = _cfg.APP_NAME
        super().__init__(None, title=titulo, name="PantallaCompleta")
        self._atajos = atajos
        self._acciones = acciones
        self.SetBackgroundColour(wx.BLACK)
        self.video = wx.Window(self, name="VideoPantallaCompleta")
        self.video.SetBackgroundColour(wx.BLACK)
        # Traductores: nombre del vídeo a pantalla completa; describe sus teclas.
        nombre_accesible(
            self.video,
            _("Vídeo a pantalla completa. Espacio pausa, flechas buscan y ajustan "
              "volumen, Escape sale."))
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.video.Bind(wx.EVT_LEFT_DCLICK,
                        lambda e: self._acciones.salir())
        self.ShowFullScreen(True)
        # Foco al vídeo: recibe el teclado y da nombre accesible al lector.
        self.video.SetFocus()

    def _on_key(self, event):
        k = event.GetKeyCode()
        mods = event.GetModifiers()
        logger.debug("TECLA origen=pantalla_completa codigo=%s mods=%s", k, mods)
        if k in (wx.WXK_ESCAPE, wx.WXK_F11):
            self._acciones.salir()
            return
        accion = self._atajos.get((mods, k))
        if accion is not None:
            accion()
            return
        accion = accion_de_tecla(k, mods, self._acciones)
        if accion is not None:
            accion()
            return
        event.Skip()

    def _on_close(self, event):
        # Alt+F4: salir por el mismo camino que Escape/F11. Si se destruyera sin
        # avisar, el panel seguiría apuntando aquí y el vídeo quedaría dibujando
        # en una ventana muerta (y el siguiente toggle petaría).
        self._acciones.salir()
