"""Progreso visible de la igualación de volumen en la ventana Música.

Mezcla de `VentanaMusica`: un campo de solo lectura con el avance («Igualando
el volumen: 40 de 195») y una barra visual al lado, solo mientras el hilo
«musica-sonoridad» mide. Un temporizador propio de un segundo lee
`control._progreso_sonoridad`: con progreso muestra y refresca, sin progreso
oculta y devuelve el foco a «Temas» si lo tenía el campo. El tic nunca anuncia:
el campo se lee con Tab o con F2.
"""

from __future__ import annotations

import wx

from ytchat.core import diagnostico
from ytchat.music import sonoridad
from ytchat.ui.gui import _T, _pintar, nombre_accesible

logger = diagnostico.obtener_logger(__name__)


class IgualandoVentanaMusica:
    """Campo y barra del progreso de la igualación, con su temporizador."""

    def _crear_igualando(self, panel) -> None:
        """Crea el campo y la barra ocultos y arranca el temporizador.

        Se llama después de crear `lb_cola` y antes de los botones, así en
        el orden de Tab el campo queda entre la cola y «Abrir enlace».
        """
        self.txt_igualando = wx.TextCtrl(
            panel, value="",
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            name="Igualación del volumen")
        self.txt_igualando.SetMinSize(
            (-1, self.txt_igualando.GetCharHeight() + 12))
        _pintar(self.txt_igualando, _T.field, _T.text)
        nombre_accesible(self.txt_igualando, "Igualación del volumen")
        self.txt_igualando.Hide()
        self.gauge_igualando = wx.Gauge(
            panel, range=100, name="Progreso de la igualación")
        nombre_accesible(self.gauge_igualando, "Progreso de la igualación")
        self.gauge_igualando.Hide()
        self._temporizador_igualando = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._tic_igualando,
                  self._temporizador_igualando)
        self._temporizador_igualando.Start(1000)

    def _fila_igualando(self, panel):
        """La fila horizontal con el campo y la barra, para el sizer.

        El campo lleva proporción 1 con la barra a su derecha, debajo de
        la cola y antes de la línea separadora.
        """
        fila = wx.BoxSizer(wx.HORIZONTAL)
        fila.Add(self.txt_igualando, 1, wx.EXPAND | wx.RIGHT, 8)
        fila.Add(self.gauge_igualando, 0, wx.ALIGN_CENTER_VERTICAL)
        return fila

    def _fila_pie(self, panel):
        """La fila de botones al pie, para el sizer."""
        pie = wx.BoxSizer(wx.HORIZONTAL)
        for boton in (self.btn_enlace, self.btn_nueva, self.btn_carpeta):
            pie.Add(boton, 0, wx.RIGHT, 8)
        pie.AddStretchSpacer(1)
        pie.Add(self.btn_cerrar, 0)
        return pie

    def _tic_igualando(self, evento=None) -> None:
        """Pone al día el campo y la barra con el progreso del control.

        Con progreso los muestra si estaban ocultos, cambia el campo con
        `ChangeValue` solo si el texto cambió y pone la barra en el
        porcentaje. Sin progreso los oculta y, si el foco estaba en el
        campo, lo pasa a `lb_temas`. Solo reubica con `Layout()` cuando
        cambia la visibilidad. Nunca anuncia ni lanza.
        """
        try:
            progreso = getattr(self._control, "_progreso_sonoridad", None)
        except Exception:
            progreso = None
        if progreso is None:
            if not self.txt_igualando.IsShown():
                return
            try:
                foco_en_campo = (
                    wx.Window.FindFocus() is self.txt_igualando)
            except Exception:
                foco_en_campo = False
            if foco_en_campo:
                try:
                    self.lb_temas.SetFocus()
                except Exception as exc:
                    logger.debug(
                        "No se pudo devolver el foco a Temas: %s", exc)
            self.txt_igualando.Hide()
            self.gauge_igualando.Hide()
            self._panel.Layout()
            return
        texto = sonoridad.texto_progreso(progreso)
        if not self.txt_igualando.IsShown():
            self.txt_igualando.Show()
            self.gauge_igualando.Show()
            self._panel.Layout()
        if self.txt_igualando.GetValue() != texto:
            self.txt_igualando.ChangeValue(texto)
        try:
            hechas, total = progreso
            porcentaje = int(round(100 * hechas / total)) if total else 0
        except (TypeError, ValueError, ZeroDivisionError):
            porcentaje = 0
        porcentaje = max(0, min(100, porcentaje))
        if self.gauge_igualando.GetValue() != porcentaje:
            self.gauge_igualando.SetValue(porcentaje)

    def _parar_igualando(self) -> None:
        """Para el temporizador del progreso. Nunca lanza."""
        temporizador = getattr(self, "_temporizador_igualando", None)
        if temporizador is None:
            return
        try:
            temporizador.Stop()
        except Exception as exc:
            logger.debug("No se pudo parar el progreso de la igualación: %s",
                         exc)
        self._temporizador_igualando = None
