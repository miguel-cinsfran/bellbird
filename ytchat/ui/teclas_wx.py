"""Traducción de los atajos de texto («ctrl+p») a combos de teclas de wx."""

from __future__ import annotations

import re

import wx

# Traducción de los atajos de config («ctrl+p», «ctrl+left», «f5»…) a lo que
# entrega wx.EVT_CHAR_HOOK: (modificadores, keycode).

_TECLAS_WX = {
    "left": wx.WXK_LEFT, "right": wx.WXK_RIGHT, "up": wx.WXK_UP,
    "down": wx.WXK_DOWN, "enter": wx.WXK_RETURN, "space": wx.WXK_SPACE,
    "end": wx.WXK_END,
}
_RE_FKEY_WX = re.compile(r"^f(1[0-2]|[1-9])$")


def combo_wx(texto: str) -> tuple[int, int] | None:
    """«ctrl+p» → (wx.MOD_CONTROL, ord('P')). None si no se puede traducir."""
    partes = (texto or "").lower().split("+")
    if not partes or not partes[-1]:
        return None
    mods = 0
    for p in partes[:-1]:
        m = {"ctrl": wx.MOD_CONTROL, "alt": wx.MOD_ALT, "shift": wx.MOD_SHIFT}.get(p)
        if m is None:
            return None
        mods |= m
    tecla = partes[-1]
    if tecla in _TECLAS_WX:
        return (mods, _TECLAS_WX[tecla])
    if _RE_FKEY_WX.match(tecla):
        return (mods, wx.WXK_F1 + int(tecla[1:]) - 1)
    if len(tecla) == 1:
        return (mods, ord(tecla.upper()))
    return None
