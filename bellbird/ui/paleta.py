"""Pinta cada ventana con la paleta crema y salvia, por un solo camino.

Recorre la ventana y sus hijos en profundidad y pinta según la clase del
control: la ventana, paneles y grupos llevan el crema, los campos el
blanco, los botones su tono y los textos el gris oscuro. Solo pone el
fondo o el texto que el control no tenga ya puestos, así respeta todo
color con papel propio (notas en `dim`, errores en `red`, el vídeo en
negro). El título del recuadro y el botón por defecto de la ventana
tienen papel fijo y salen siempre. Con el contraste alto de Windows no
hace nada: mandan los colores del sistema.
"""

from __future__ import annotations

import wx

from bellbird.ui import tema
from bellbird.ui.tema import _T

_FONDO = (wx.Dialog, wx.Frame, wx.Panel, wx.ScrolledWindow)
_CAMPOS = (wx.TextCtrl, wx.ListBox, wx.ListCtrl, wx.Choice, wx.ComboBox,
           wx.SpinCtrl)
_BOTONES = (wx.Button,)
_SOLO_TEXTO = (wx.StaticText, wx.CheckBox, wx.RadioButton)


def _sin_color(propio) -> bool:
    """Si el control no trae color propio puesto a mano."""
    try:
        return not propio()
    except Exception:
        return True


def _pintar_recuadro(control) -> None:
    """El título del grupo sale siempre en salvia con negrita."""
    tema._pintar(control, fg=_T.accent)
    control.SetFont(control.GetFont().Bold())


def _pintar_deslizador(control) -> None:
    """Deslizador o medidor con el fondo de su padre, si no trae uno propio."""
    if _sin_color(control.UseBackgroundColour):
        tema._pintar(control, bg=control.GetParent().GetBackgroundColour())


def _pintar_fondo(control) -> None:
    """Ventana, panel o zona desplazable con crema y texto gris."""
    if _sin_color(control.UseBackgroundColour):
        tema._pintar(control, bg=_T.bg)
    if _sin_color(control.UseForegroundColour):
        tema._pintar(control, fg=_T.text)


def _pintar_campo(control) -> None:
    """Campo o lista con blanco y texto gris."""
    if _sin_color(control.UseBackgroundColour):
        tema._pintar(control, bg=_T.field)
    if _sin_color(control.UseForegroundColour):
        tema._pintar(control, fg=_T.text)


def _pintar_boton(control) -> None:
    """Botón secundario con su tono y su texto."""
    if _sin_color(control.UseBackgroundColour):
        tema._pintar(control, bg=_T.btn)
    if _sin_color(control.UseForegroundColour):
        tema._pintar(control, fg=_T.btn_t)


def _pintar_texto(control) -> None:
    """Texto suelto con el gris principal."""
    if _sin_color(control.UseForegroundColour):
        tema._pintar(control, fg=_T.text)


# Cada clase de control con su pintor, en orden: primero los casos
# particulares (recuadro, deslizador) y después los generales.
_PINTORES = (
    (wx.StaticBox, _pintar_recuadro),
    ((wx.Slider, wx.Gauge), _pintar_deslizador),
    (_FONDO, _pintar_fondo),
    (_CAMPOS, _pintar_campo),
    (_BOTONES, _pintar_boton),
    (_SOLO_TEXTO, _pintar_texto),
)


def _pintar_control(control) -> None:
    """Pinta un control con el pintor de su clase, si tiene uno."""
    for clases, pintar in _PINTORES:
        if isinstance(control, clases):
            pintar(control)
            return


def _pintar_principal(ventana) -> None:
    """El botón por defecto de la ventana sale como principal."""
    try:
        principal = ventana.GetDefaultItem()
    except Exception:
        principal = None
    if principal is not None:
        tema.boton_principal(principal)


def pintar_ventana(ventana) -> None:
    """Aplica la paleta a la ventana y a todos sus hijos, en profundidad."""
    if tema.ALTO_CONTRASTE:
        return
    pendientes = [ventana]
    while pendientes:
        control = pendientes.pop()
        _pintar_control(control)
        pendientes.extend(reversed(control.GetChildren()))
    _pintar_principal(ventana)
    ventana.Refresh()
