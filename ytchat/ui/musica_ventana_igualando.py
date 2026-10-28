"""Progreso visible de la igualación de volumen en la ventana Música.

Mezcla de `VentanaMusica`: un campo de solo lectura con el avance («Igualando
el volumen: 40 de 195») y una barra visual al lado, solo mientras el hilo
«musica-sonoridad» mide. Un temporizador propio de un segundo lee
`control._progreso_sonoridad`: con progreso muestra y refresca, sin progreso
oculta y devuelve el foco a «Temas» si lo tenía el campo. El tic nunca anuncia:
el campo se lee con Tab o con F2.

También trae el botón que pide la igualación (y la detiene mientras mide) y
la pregunta que sale una vez por apertura al recibir la biblioteca de la
carpeta: las dos arrancan la misma medición, la del control de música.
"""

from __future__ import annotations

import wx

from ytchat.core import diagnostico
from ytchat.core.idioma import _
from ytchat.music import anuncios
from ytchat.music import pregunta_igualar
from ytchat.music import sonoridad
from ytchat.ui.accesibilidad import anunciar, nombre_accesible
from ytchat.ui.tema import _T, _pintar
from ytchat.voice import sound_player as _snd

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
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_NO_VSCROLL,
            name=_("Igualación del volumen"))
        self.txt_igualando.SetMinSize(
            (-1, self.txt_igualando.GetCharHeight() + 12))
        _pintar(self.txt_igualando, _T.field, _T.text)
        nombre_accesible(self.txt_igualando, _("Igualación del volumen"))
        self.txt_igualando.Hide()
        self.gauge_igualando = wx.Gauge(
            panel, range=100, name=_("Progreso de la igualación"))
        nombre_accesible(self.gauge_igualando, _("Progreso de la igualación"))
        self.gauge_igualando.Hide()
        self._igualando_midiendo = False
        self._preguntado_igualar = False
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
        for boton in (self.btn_enlace, self.btn_nueva, self.btn_carpeta,
                      self.btn_igualar, self.btn_examinar):
            pie.Add(boton, 0, wx.RIGHT, 8)
        pie.AddStretchSpacer(1)
        pie.Add(self.btn_cerrar, 0)
        return pie

    def alternar_igualacion(self) -> None:
        """Pide la igualación del volumen, o la detiene si ya mide.

        Las pendientes se calculan en un hilo: si todavía no están, las
        pide y al llegar inicia con ellas, sin volver a calcularlas.
        """
        if self._midiendo_igualacion():
            self._control.detener_igualacion()
            anunciar(sonoridad.TEXTO_IGUALACION_DETENIDA)
            return
        biblioteca = self._control.biblioteca_actual()
        if biblioteca is None:
            # Todavía no está indexada: la pide y al llegar calcula.
            self._control.biblioteca(self._al_biblioteca_para_igualar)
            return
        self._control.pedir_pendientes(biblioteca, self._al_pendientes_boton)

    def _al_biblioteca_para_igualar(self, biblioteca) -> None:
        """Al llegar la biblioteca indexada, pide calcular las pendientes."""
        if not self:
            return
        if biblioteca is None:
            anunciar(anuncios.TEXTO_SIN_CARPETA)
            return
        self._control.pedir_pendientes(biblioteca, self._al_pendientes_boton)

    def _al_pendientes_boton(self, pendientes, total) -> None:
        """Inicia la medición con las pendientes ya calculadas."""
        if not self:
            return
        self._empezar_igualacion(pendientes)

    def _empezar_igualacion(self, pendientes) -> None:
        """Pide la igualación y anuncia lo que pasó.

        Recibe las pendientes ya calculadas, del botón o de la pregunta.
        """
        resultado = self._control.iniciar_medicion(pendientes)
        if resultado.codigo in (sonoridad.INICIO, sonoridad.YA_MIDIENDO):
            _snd.reproducir(sonoridad.SONIDO_IGUALANDO)
            anunciar(sonoridad.TEXTO_IGUALANDO.format(total=resultado.total))
        elif resultado.codigo == sonoridad.OPCION_APAGADA:
            anunciar(sonoridad.TEXTO_IGUALACION_DESACTIVADA)
        elif resultado.codigo == sonoridad.SIN_FFMPEG:
            anunciar(sonoridad.TEXTO_SIN_FFMPEG)
        else:
            anunciar(sonoridad.TEXTO_NADA_PENDIENTE)

    def preguntar_igualacion(self, biblioteca) -> None:
        """Pregunta, diferida, si hay que igualar el volumen.

        Se llama al recibir la biblioteca de la carpeta, una vez por
        apertura de la ventana. Con una lista propia elegida no se llama.
        Las pendientes se calculan en un hilo y la pregunta sale al llegar.
        """
        if self._preguntado_igualar:
            return
        self._preguntado_igualar = True
        self._control.pedir_pendientes(biblioteca, self._al_pendientes_pregunta)

    def _al_pendientes_pregunta(self, pendientes, total) -> None:
        """Muestra la pregunta si sigue habiendo pendientes.

        Sí mide con esas pendientes ya calculadas; en los dos casos, la
        casilla deja guardado que no se pregunte más.
        """
        if not self:
            return
        datos = self._control.confirmar_pregunta(pendientes, total)
        if datos is None:
            return
        cantidad, tamano = datos
        dialogo = wx.RichMessageDialog(
            self, pregunta_igualar.texto_pregunta(cantidad, tamano),
            _(pregunta_igualar.TITULO),
            wx.YES_NO | wx.ICON_QUESTION | wx.NO_DEFAULT)
        dialogo.ShowCheckBox(_(pregunta_igualar.CASILLA))
        respuesta = dialogo.ShowModal()
        marcada = dialogo.IsCheckBoxChecked()
        dialogo.Destroy()
        if marcada:
            self._control.fijar_preguntar_igualar(False)
        if respuesta == wx.ID_YES:
            self._empezar_igualacion(pendientes)

    def _rotular_boton_igualar(self, midiendo) -> None:
        """Rotula el botón según se esté midiendo o no."""
        if midiendo:
            self.btn_igualar.SetLabel(_("Detener la &igualación"))
            nombre_accesible(self.btn_igualar, _("Detener la igualación"))
        else:
            self.btn_igualar.SetLabel(_("&Igualar el volumen"))
            nombre_accesible(self.btn_igualar, _("Igualar el volumen"))

    def _midiendo_igualacion(self) -> bool:
        """Si el control tiene una medición en curso."""
        lee = getattr(self._control, "midiendo_igualacion", None)
        return bool(lee()) if callable(lee) else False

    def _rotular_si_cambio(self) -> None:
        """Rotula el botón si la medición empezó o terminó.

        Si el foco estaba en el botón, se queda en el botón.
        """
        midiendo = self._midiendo_igualacion()
        if midiendo == self._igualando_midiendo:
            return
        self._igualando_midiendo = midiendo
        try:
            foco = wx.Window.FindFocus() is self.btn_igualar
        except Exception:
            foco = False
        self._rotular_boton_igualar(midiendo)
        if foco:
            self.btn_igualar.SetFocus()

    def _tic_igualando(self, evento=None) -> None:
        """Pone al día el campo, la barra y el botón con el control.

        Con progreso los muestra si estaban ocultos, cambia el campo con
        `ChangeValue` solo si el texto cambió y pone la barra en el
        porcentaje. Sin progreso los oculta y, si el foco estaba en el
        campo, lo pasa a `lb_temas`. Además rotula el botón cuando la
        medición empieza o termina. Nunca anuncia ni lanza.
        """
        self._rotular_si_cambio()
        try:
            progreso = getattr(self._control, "_progreso_sonoridad", None)
        except Exception:
            progreso = None
        if progreso is None:
            self._ocultar_igualando()
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

    def _ocultar_igualando(self) -> None:
        """Oculta el campo y la barra, con el foco a «Temas» si lo tenía."""
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
