"""Avisos importantes: sonido, anuncio y, si se pidió, cuadro de Windows.

Una sola entrada para los resultados de lo que el usuario acaba de iniciar.
Con la casilla de Preferencias apagada se comporta como siempre (sonido y
anuncio); encendida, abre un cuadro con un solo botón «Aceptar» y deja que el
lector lo lea, sin anunciarlo dos veces. Nunca hay más de un cuadro abierto.
Se puede llamar desde cualquier hilo: todo lo de wx se reenvía con
`wx.CallAfter`.
"""

from __future__ import annotations

import threading

import wx

from guyrapu.core import config
from guyrapu.core.idioma import _
from guyrapu.ui import confirmar
from guyrapu.ui.accesibilidad import anunciar
from guyrapu.voice import sound_player

CUADRO = "cuadro"
ANUNCIO = "anuncio"

_cerrojo = threading.Lock()
_cuadro_abierto = False


def decidir(mostrar_cuadro: bool, cuadro_abierto: bool) -> str:
    """Elige entre cuadro y anuncio. Función pura, con sus dos casos."""
    if mostrar_cuadro and not cuadro_abierto:
        return CUADRO
    return ANUNCIO


def _casilla_activa() -> bool:
    """La casilla de Preferencias, General, leída de la ventana principal."""
    try:
        from guyrapu.ui import gui
        frame = getattr(gui, "_gui_frame", None)
        if frame is None:
            return False
        return bool(frame._config.get("avisos_cuadro", False))
    except Exception:
        return False


def _padre():
    """La ventana activa de la app o, si no hay, la principal."""
    try:
        activa = wx.GetActiveWindow()
    except Exception:
        activa = None
    if activa is not None:
        return activa
    try:
        from guyrapu.ui import gui
        frame = getattr(gui, "_gui_frame", None)
        if frame is not None:
            return frame
        app = wx.GetApp()
        return app.GetTopWindow() if app is not None else None
    except Exception:
        return None


def _mostrar(texto: str, error: bool) -> None:
    global _cuadro_abierto
    try:
        confirmar.avisar(
            _padre(), texto, config.APP_NAME, _("Aceptar"),
            icono=confirmar.ICON_ERROR if error else confirmar.ICON_INFORMATION)
    except Exception:
        # Si el cuadro no llegó a abrirse, el aviso no se pierde: se anuncia.
        anunciar(texto)
    finally:
        with _cerrojo:
            _cuadro_abierto = False


def avisar(texto: str, sonido: str | None = None, *, error: bool = False) -> None:
    """Reproduce el sonido y anuncia o muestra el texto, según la casilla."""
    global _cuadro_abierto
    if sonido:
        sound_player.reproducir(sonido)
    if not texto:
        return
    with _cerrojo:
        decision = decidir(_casilla_activa(), _cuadro_abierto)
        if decision == CUADRO:
            _cuadro_abierto = True
    if decision == ANUNCIO:
        anunciar(texto)
        return
    try:
        wx.CallAfter(_mostrar, texto, error)
    except Exception:
        with _cerrojo:
            _cuadro_abierto = False
        anunciar(texto)
