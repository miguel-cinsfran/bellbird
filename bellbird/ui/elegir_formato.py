"""Elegir el formato exacto de un vídeo del buscador.

Razón del módulo: pedir los formatos reales de un resultado, mostrarlos en
un cuadro y agregar a la cola la opción elegida. La consulta va en un hilo
y el cuadro se abre en la GUI, como la búsqueda en tandas.
"""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import N_, _
from bellbird.downloads import formatos_reales, ytdlp_bin
from bellbird.ui.accesibilidad import anunciar, nombre_accesible
from bellbird.ui import paleta
from bellbird.voice import sound_player as _snd

logger = diagnostico.obtener_logger(__name__)

TITULO = N_("Elegir formato")
TEXTO_CARGANDO = N_("Cargando formatos")
TEXTO_FALLO = N_("No se pudieron cargar los formatos.")


def _sonar(evento: str) -> None:
    try:
        _snd.reproducir(evento)
    except Exception as error:
        logger.debug("sin sonido de %s: %s", evento, error)


class DialogoFormato(wx.Dialog):
    """Las opciones exactas de un vídeo, para descargar la elegida."""

    def __init__(self, parent, opciones):
        super().__init__(parent, title=_(TITULO), name="DialogoFormato")
        self._opciones = list(opciones)
        self._crear_controles()
        paleta.pintar_ventana(self)
        self.Centre()

    def _crear_controles(self):
        panel = wx.Panel(self, name="PanelFormato")
        self.panel = panel
        vs = wx.BoxSizer(wx.VERTICAL)

        vs.Add(wx.StaticText(panel, label=_("&Formatos:")),
               0, wx.ALL, 8)
        self.lista = wx.ListBox(
            panel, choices=[o.etiqueta for o in self._opciones],
            name=_("Formatos"))
        nombre_accesible(self.lista, _("Formatos"))
        vs.Add(self.lista, 1, wx.EXPAND | wx.ALL, 8)

        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_descargar = wx.Button(
            panel, wx.ID_OK, _("&Descargar"), name=_("Descargar"))
        self.btn_descargar.SetDefault()
        fila.Add(self.btn_descargar, 0, wx.RIGHT, 8)
        self.btn_cancelar = wx.Button(
            panel, wx.ID_CANCEL, _("Cancelar"), name=_("Cancelar"))
        fila.Add(self.btn_cancelar, 0)
        vs.Add(fila, 0, wx.ALL, 8)

        panel.SetSizer(vs)
        if self._opciones:
            self.lista.SetSelection(0)
        self.lista.SetFocus()

    def elegida(self):
        """La opción elegida en la lista, o None si no hay ninguna."""
        sel = self.lista.GetSelection()
        if 0 <= sel < len(self._opciones):
            return self._opciones[sel]
        return None


class ConsultaFormatos:
    """Los formatos reales de un resultado, del hilo al cuadro.

    `agregar_urls(urls, formato, titulo)` es lo que encola, el mismo que usa
    el menú para audio y vídeo.
    """

    def __init__(self, agregar_urls):
        self._agregar_urls = agregar_urls
        self._en_curso = False
        self._padre = None

    def pedir(self, resultado) -> None:
        """Consulta los formatos de ese resultado y abre el cuadro."""
        if self._en_curso or resultado is None:
            return
        self._en_curso = True
        # El padre se guarda ahora: al volver el Administrador puede estar
        # cerrado y la ventana activa ser otra.
        self._padre = wx.GetActiveWindow()
        anunciar(_(TEXTO_CARGANDO))
        _sonar("formatos_cargando")
        hilo = diagnostico.crear_hilo(
            self._consultar_en_hilo, "FormatosVideo", args=(resultado,))
        hilo.start()

    def _consultar_en_hilo(self, resultado) -> None:
        try:
            info = ytdlp_bin.info_video(resultado.id)
        except Exception as error:
            logger.debug("no se pudo pedir los formatos: %s", error)
            info = None
        opciones = formatos_reales.opciones(info) if info else []
        wx.CallAfter(self._al_volver, resultado, opciones)

    def _al_volver(self, resultado, opciones) -> None:
        self._en_curso = False
        padre, self._padre = self._padre, None
        if not opciones:
            anunciar(_(TEXTO_FALLO))
            _sonar("formatos_fallidos")
            return
        if padre is None:
            return
        try:
            existe = bool(padre)
        except RuntimeError:
            return
        if not existe:
            return
        dialogo = DialogoFormato(padre, opciones)
        try:
            if dialogo.ShowModal() != wx.ID_OK:
                return
            elegida = dialogo.elegida()
        finally:
            dialogo.Destroy()
        if elegida is None:
            return
        self._agregar_urls(
            [resultado.url], formato=formatos_reales.transitorias(elegida),
            titulo=resultado.titulo)
