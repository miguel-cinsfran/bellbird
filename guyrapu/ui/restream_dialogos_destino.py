"""Cuadros de la pestaña Destinos: cambiar el título y agregar uno manual.

El primero pide el título y la descripción con que el destino sale en su
plataforma. El segundo pide plataforma, nombre, servidor y clave para los
destinos que se conectan con servidor y clave. Los dos se arman con el mismo
rótulo y los mismos botones del cuadro de perfil de Restream.
"""

from __future__ import annotations

import wx

from guyrapu.core.idioma import _
from guyrapu.ui import paleta
from guyrapu.ui.accesibilidad import anunciar, nombre_accesible
from guyrapu.ui.preferencias_comun import nombre_de_etiqueta
from guyrapu.ui.restream_perfil import _rotulo


class DialogoMetaDestino(wx.Dialog):
    """Título y descripción de un destino de la cuenta."""

    def __init__(self, parent, meta):
        super().__init__(parent, title=_("Cambiar título"), size=(520, 360),
                         name="DialogoMetaDestino")
        self._resultado = None
        self._crear_ui(meta)
        paleta.pintar_ventana(self)
        self.Centre()

    def _crear_ui(self, meta):
        vs = wx.BoxSizer(wx.VERTICAL)
        contenido = wx.BoxSizer(wx.VERTICAL)
        self.lbl_titulo, self.txt_titulo = _rotulo(
            self, contenido, _("&Título:"),
            lambda: wx.TextCtrl(
                self, value=meta.titulo, style=wx.TE_PROCESS_ENTER))
        self.lbl_descripcion, self.txt_descripcion = _rotulo(
            self, contenido, _("&Descripción:"),
            lambda: wx.TextCtrl(
                self, value=meta.descripcion, style=wx.TE_MULTILINE))
        self.txt_descripcion.SetMinSize(
            (-1, 3 * self.txt_descripcion.GetCharHeight() + 12))
        vs.Add(contenido, 1, wx.EXPAND)
        self._agregar_botones(vs)

        self.SetSizer(vs)
        self.btn_aceptar.SetDefault()
        self.btn_aceptar.Bind(wx.EVT_BUTTON, self._aceptar)
        self.btn_cancelar.Bind(
            wx.EVT_BUTTON, lambda evento: self.EndModal(wx.ID_CANCEL))
        self.txt_titulo.Bind(wx.EVT_TEXT_ENTER, self._aceptar)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)
        self.txt_titulo.SetFocus()

    def _agregar_botones(self, vs):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        etiqueta = _("&Aceptar")
        self.btn_aceptar = wx.Button(
            self, wx.ID_OK, etiqueta, name=nombre_de_etiqueta(etiqueta))
        self.btn_cancelar = wx.Button(
            self, wx.ID_CANCEL, _("Cancelar"), name=_("Cancelar"))
        for boton in (self.btn_aceptar, self.btn_cancelar):
            nombre_accesible(boton, boton.GetName())
        fila.Add(self.btn_aceptar, 0, wx.RIGHT, 6)
        fila.Add(self.btn_cancelar, 0)
        vs.Add(fila, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

    def datos(self):
        """El título y la descripción aceptados, o None si no se aceptó."""
        return self._resultado

    def _aceptar(self, _evento=None):
        self._resultado = (self.txt_titulo.GetValue(),
                           self.txt_descripcion.GetValue())
        self.EndModal(wx.ID_OK)

    def _al_tecla(self, evento):
        if evento.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        evento.Skip()


class DialogoDestinoManual(wx.Dialog):
    """Plataforma, nombre, servidor y clave de un destino manual."""

    def __init__(self, parent, plataformas):
        super().__init__(parent, title=_("Agregar destino manual"),
                         size=(560, 470), name="DialogoDestinoManual")
        self._plataformas = sorted(
            plataformas.items(),
            key=lambda par: (par[1].casefold(), par[0]))
        self._resultado = None
        self._crear_ui()
        paleta.pintar_ventana(self)
        self.Centre()

    def _crear_ui(self):
        vs = wx.BoxSizer(wx.VERTICAL)
        contenido = wx.BoxSizer(wx.VERTICAL)
        self.lbl_plataforma, self.cho_plataforma = _rotulo(
            self, contenido, _("&Plataforma:"),
            lambda: wx.Choice(
                self, choices=[nombre for _id, nombre in self._plataformas]))
        self.lbl_nombre, self.txt_nombre = _rotulo(
            self, contenido, _("&Nombre:"),
            lambda: wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER))
        self.lbl_servidor, self.txt_servidor = _rotulo(
            self, contenido, _("&Servidor:"),
            lambda: wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER))
        self.lbl_clave, self.txt_clave = _rotulo(
            self, contenido, _("&Clave de transmisión:"),
            lambda: wx.TextCtrl(
                self, style=wx.TE_PASSWORD | wx.TE_PROCESS_ENTER))
        vs.Add(contenido, 1, wx.EXPAND)
        self._agregar_botones(vs)

        self.SetSizer(vs)
        self.btn_aceptar.SetDefault()
        self.btn_aceptar.Bind(wx.EVT_BUTTON, self._aceptar)
        self.btn_cancelar.Bind(
            wx.EVT_BUTTON, lambda evento: self.EndModal(wx.ID_CANCEL))
        for campo in (self.txt_nombre, self.txt_servidor, self.txt_clave):
            campo.Bind(wx.EVT_TEXT_ENTER, self._aceptar)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)
        self.cho_plataforma.SetFocus()

    def _agregar_botones(self, vs):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        etiqueta = _("&Aceptar")
        self.btn_aceptar = wx.Button(
            self, wx.ID_OK, etiqueta, name=nombre_de_etiqueta(etiqueta))
        self.btn_cancelar = wx.Button(
            self, wx.ID_CANCEL, _("Cancelar"), name=_("Cancelar"))
        for boton in (self.btn_aceptar, self.btn_cancelar):
            nombre_accesible(boton, boton.GetName())
        fila.Add(self.btn_aceptar, 0, wx.RIGHT, 6)
        fila.Add(self.btn_cancelar, 0)
        vs.Add(fila, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

    def datos(self):
        """(plataforma, nombre, servidor, clave) aceptados, o None."""
        return self._resultado

    def _aceptar(self, _evento=None):
        indice = self.cho_plataforma.GetSelection()
        if indice < 0:
            anunciar(_("Falta la plataforma."))
            self.cho_plataforma.SetFocus()
            return
        servidor = self.txt_servidor.GetValue().strip()
        if not servidor:
            anunciar(_("Falta el servidor."))
            self.txt_servidor.SetFocus()
            return
        clave = self.txt_clave.GetValue().strip()
        if not clave:
            anunciar(_("Falta la clave de transmisión."))
            self.txt_clave.SetFocus()
            return
        self._resultado = (
            self._plataformas[indice][0],
            self.txt_nombre.GetValue().strip(),
            servidor,
            clave,
        )
        self.EndModal(wx.ID_OK)

    def _al_tecla(self, evento):
        if evento.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        evento.Skip()
