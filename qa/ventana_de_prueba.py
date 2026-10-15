"""Ventana de color liso para la prueba del directo real.

La abre `qa/directo_real.py` por duplicado (verde «Cámara de prueba» y
magenta «Aplicación de prueba») para armar una escena de OBS como la de
quien usa la app, con capturas encima del panel de chat. Se queda abierta
hasta que la cierren y no tiene ningún control.
"""

from __future__ import annotations

import argparse
import sys

ANCHO = 640
ALTO = 360


def color_desde_texto(texto: str) -> tuple[int, int, int]:
    """Terna (rojo, verde, azul) desde un hexadecimal «RRGGBB», con o sin #."""
    limpio = (texto or "").strip().lstrip("#")
    if len(limpio) != 6:
        raise ValueError(f"color inválido «{texto}»: tiene que ser RRGGBB")
    try:
        return (int(limpio[0:2], 16), int(limpio[2:4], 16),
                int(limpio[4:6], 16))
    except ValueError:
        raise ValueError(
            f"color inválido «{texto}»: tiene que ser RRGGBB") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ventana de color liso para tapar el panel en la prueba "
                    "del directo real.")
    parser.add_argument("--titulo", default="Ventana de prueba")
    parser.add_argument("--color", default="00C000")
    args = parser.parse_args(argv)
    try:
        rojo, verde, azul = color_desde_texto(args.color)
    except ValueError as exc:
        print(exc)
        return 2

    import wx
    app = wx.App(False)
    marco = wx.Frame(None, title=args.titulo)
    marco.SetClientSize((ANCHO, ALTO))
    fondo = wx.Colour(rojo, verde, azul)

    def pintar(evento):
        contexto = wx.PaintDC(marco)
        contexto.SetBackground(wx.Brush(fondo))
        contexto.Clear()

    marco.Bind(wx.EVT_PAINT, pintar)
    # Sin activar: la ventana aparece detrás sin robar el foco.
    marco.ShowWithoutActivating()
    app.MainLoop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
