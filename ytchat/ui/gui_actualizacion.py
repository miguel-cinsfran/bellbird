"""Ventana genérica de actualización con estado, progreso y cierre.

No sabe nada de yt-dlp ni de ningún origen concreto: quien la abre le
pone el título, le anuncia cada fase con `estado()` y le mueve la barra
con `progreso()`. No modal, se muestra con `Show()`.
"""

from __future__ import annotations

import threading

import wx

from ytchat.core.actualizacion import notas_legibles
from ytchat.ui import paleta
from ytchat.ui.gui import anunciar, nombre_accesible


class DialogoActualizacion(wx.Dialog):
    def __init__(self, parent, titulo):
        super().__init__(parent, title=titulo,
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
                         name="DialogoActualizacion")
        self._cerrado = False
        self._cancelado = threading.Event()
        self._accion = None

        vs = wx.BoxSizer(wx.VERTICAL)
        self.txt_estado = wx.TextCtrl(
            self, value="", style=wx.TE_MULTILINE | wx.TE_READONLY,
            name="Estado")
        self.txt_estado.SetMinSize(
            (-1, 3 * self.txt_estado.GetCharHeight() + 12))
        nombre_accesible(self.txt_estado, "Estado")
        vs.Add(self.txt_estado, 0, wx.EXPAND | wx.ALL, 10)

        self.gauge = wx.Gauge(self, range=100, name="Progreso")
        nombre_accesible(self.gauge, "Progreso")
        vs.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        self.txt_notas = wx.TextCtrl(
            self, value="", style=wx.TE_MULTILINE | wx.TE_READONLY,
            name="Novedades")
        try:
            ancho60 = 60 * self.txt_notas.GetCharWidth()
        except Exception:
            ancho60 = -1
        try:
            alto_notas = 12 * self.txt_notas.GetCharHeight() + 12
        except Exception:
            alto_notas = -1
        self.txt_notas.SetMinSize((ancho60, alto_notas))
        nombre_accesible(self.txt_notas, "Novedades")
        vs.Add(self.txt_notas, 1, wx.EXPAND | wx.ALL, 10)
        self.txt_notas.Hide()

        self.btn_accion = wx.Button(self, wx.ID_ANY, "")
        self.btn_accion.Hide()

        self.btn_cerrar = wx.Button(self, wx.ID_CANCEL, "&Cerrar")
        fila_botones = wx.BoxSizer(wx.HORIZONTAL)
        fila_botones.Add(self.btn_accion, 0, wx.RIGHT, 10)
        fila_botones.Add(self.btn_cerrar, 0)
        vs.Add(fila_botones, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        self.SetSizer(vs)
        self.Fit()
        self.Centre()
        self.btn_cerrar.Bind(wx.EVT_BUTTON, self._al_cerrar)
        self.Bind(wx.EVT_CLOSE, self._al_cerrar)
        try:
            self.btn_cerrar.SetFocus()
        except Exception:
            pass

    @property
    def cerrado(self) -> bool:
        return self._cerrado

    @property
    def cancelado(self) -> threading.Event:
        return self._cancelado

    def Show(self, show=True):
        paleta.pintar_ventana(self)
        resultado = super().Show(show)
        if show:
            try:
                self.btn_cerrar.SetFocus()
            except Exception:
                pass
        return resultado

    def estado(self, texto) -> None:
        self.txt_estado.SetValue(texto)
        anunciar(texto)

    def progreso(self, porcentaje) -> None:
        if porcentaje is None:
            self.gauge.Pulse()
        else:
            self.gauge.SetValue(int(porcentaje))

    def _reajustar(self) -> None:
        # Reparte el espacio y agranda o achica la ventana a su contenido,
        # para que todo control visible tenga alto mayor que cero y quede
        # dentro del área cliente. No toca el foco ni re-centra: el foco lo
        # dejan `ofrecer_accion` y `quitar_accion` como siempre.
        try:
            self.Layout()
        except Exception:
            pass
        try:
            self.Fit()
        except Exception:
            pass
        try:
            self.Layout()
        except Exception:
            pass

    def notas(self, texto) -> None:
        limpio = notas_legibles(texto)
        self.txt_notas.SetValue(limpio)
        if limpio:
            self.txt_notas.Show()
            try:
                self.txt_notas.SetInsertionPoint(0)
                self.txt_notas.ShowPosition(0)
            except Exception:
                pass
        else:
            self.txt_notas.Hide()
        self._reajustar()

    def etiqueta_cerrar(self, etiqueta) -> None:
        self.btn_cerrar.SetLabel(etiqueta)
        self._reajustar()

    def ofrecer_accion(self, etiqueta, al_pulsar) -> None:
        self._accion = al_pulsar
        self.btn_accion.SetLabel(etiqueta)
        try:
            self.btn_accion.Unbind(wx.EVT_BUTTON)
        except Exception:
            pass
        self.btn_accion.Bind(
            wx.EVT_BUTTON, lambda _event: self._accion())
        self.btn_accion.Show()
        self._reajustar()
        try:
            self.btn_accion.SetFocus()
        except Exception:
            pass

    def quitar_accion(self) -> None:
        self._accion = None
        self.btn_accion.Hide()
        self._reajustar()
        try:
            self.btn_cerrar.SetFocus()
        except Exception:
            pass

    def en_hilo_principal(self, funcion, *args) -> None:
        def _envoltura():
            if self._cerrado:
                return
            funcion(*args)

        wx.CallAfter(_envoltura)

    def _al_cerrar(self, event) -> None:
        self._cerrado = True
        try:
            self._cancelado.set()
        except Exception:
            pass
        try:
            self.Destroy()
        except Exception:
            pass
