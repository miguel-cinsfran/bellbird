"""Ventana ajena para probar los atajos globales de música.

La lanza `qa/musica_globales.py` como proceso aparte: un marco titulado
«Ventana ajena de QA» con un cuadro de texto multilínea que tiene el foco
al abrir. Escribe el texto del cuadro en `--registro` al abrir (vacío) y
en cada cambio, y se cierra sola cuando aparece el archivo `--cerrar-con`
o a los 300 segundos.

Importar este módulo no abre nada: la ventana solo se crea en `main()`.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

TITULO = "Ventana ajena de QA"
TOPE_SEGUNDOS = 300


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ventana ajena para probar que los atajos globales "
                    "no escriben fuera de la aplicación.")
    parser.add_argument("--registro", required=True,
                        help="Archivo donde se escribe el texto del cuadro.")
    parser.add_argument("--cerrar-con", required=True,
                        help="Cuando aparece este archivo, la ventana se "
                             "cierra sola.")
    args = parser.parse_args(argv)
    registro = Path(args.registro)
    cerrar_con = Path(args.cerrar_con)

    import wx
    app = wx.App(False)
    marco = wx.Frame(None, title=TITULO)
    cuadro = wx.TextCtrl(marco, style=wx.TE_MULTILINE)
    marco.SetClientSize((500, 300))
    caja = wx.BoxSizer(wx.VERTICAL)
    caja.Add(cuadro, 1, wx.EXPAND | wx.ALL, 8)
    marco.SetSizer(caja)

    def guardar() -> None:
        try:
            registro.write_text(cuadro.GetValue(), encoding="utf-8")
        except OSError:
            pass

    cuadro.Bind(wx.EVT_TEXT, lambda evento: guardar())
    marco.Show()
    cuadro.SetFocus()
    guardar()
    inicio = time.monotonic()

    def vigilar() -> None:
        try:
            cerrar = cerrar_con.exists()
        except OSError:
            cerrar = False
        if cerrar or time.monotonic() - inicio > TOPE_SEGUNDOS:
            marco.Close()
            return
        wx.CallLater(250, vigilar)

    wx.CallLater(250, vigilar)
    app.MainLoop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
