"""Página General del diálogo de Preferencias.

Dueña de sus casillas y de las acciones sobre el archivo de preferencias.
El diálogo la construye por composición y copia solo las casillas que lee su
tabla de opciones simples.
"""

from __future__ import annotations

import os

import wx

from ytchat.core import config
from ytchat.core import idioma
from ytchat.core import paths
from ytchat.core import preferencias_archivo
from ytchat.core.idioma import _
from ytchat.ui.accesibilidad import anunciar
from ytchat.ui.preferencias_comun import EleccionTexto, crear_panel, fila_label


# Fila de idioma de `_OPCIONES_SIMPLES` en `gui_preferencias`: misma tabla,
# mismo orden.
OPCIONES_GENERAL = (
    ("cho_idioma", "ui", "idioma", "idioma", str, "windows"),
)


class PaginaGeneral:
    """Página General: casillas de inicio y acciones sobre el archivo."""

    def __init__(self, ventana):
        self._ventana = ventana

    def construir(self, parent):
        p = crear_panel(parent, "PagGeneral")
        vs = wx.BoxSizer(wx.VERTICAL)
        vs.Add(fila_label(p, _("Idi&oma:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.cho_idioma = EleccionTexto(p, idioma.idiomas_disponibles(),
                                        name=_("Idioma"))
        vs.Add(self.cho_idioma, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.cho_idioma.Bind(wx.EVT_CHOICE, self._al_cambiar_idioma)
        self._casillas(p, vs)
        self._botones(p, vs)
        p.SetSizer(vs)
        return p

    def _al_cambiar_idioma(self, event):
        anunciar(_("El idioma cambia al reiniciar la aplicación."))
        event.Skip()

    def _casillas(self, p, vs):
        self.chk_buscar_actualizaciones = wx.CheckBox(
            p, label=_("Buscar &actualizaciones al iniciar"),
            name=_("Buscar actualizaciones al iniciar"))
        vs.Add(self.chk_buscar_actualizaciones, 0, wx.ALL, 10)

        self.chk_confirmar_salida = wx.CheckBox(
            p, label=_("Preguntar antes de &salir si hay un chat conectado "
                       "o una transmisión en curso"),
            name=_("Preguntar antes de salir si hay un chat conectado "
                   "o una transmisión en curso"))
        vs.Add(self.chk_confirmar_salida, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_sonido_inicio = wx.CheckBox(
            p, label=_("Reproducir el sonido de &inicio"),
            name=_("Reproducir el sonido de inicio"))
        vs.Add(self.chk_sonido_inicio, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_registro_detallado = wx.CheckBox(
            p, label=_("Guardar un registro &detallado para diagnosticar fallos"),
            name=_("Guardar un registro detallado para diagnosticar fallos"))
        vs.Add(self.chk_registro_detallado, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _botones(self, p, vs):
        # Archivo de preferencias: la importación y el restablecimiento piden
        # reiniciar y cierran el diálogo sin guardar, para que Guardar no pise
        # el archivo nuevo con los valores viejos de los controles.
        self.btn_abrir_datos = wx.Button(
            p, label=_("Abrir la carpeta de da&tos"),
            name=_("Abrir la carpeta de datos"))
        vs.Add(self.btn_abrir_datos, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_exportar_prefs = wx.Button(
            p, label=_("E&xportar las preferencias…"),
            name=_("Exportar las preferencias"))
        vs.Add(self.btn_exportar_prefs, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_importar_prefs = wx.Button(
            p, label=_("I&mportar las preferencias…"),
            name=_("Importar las preferencias"))
        vs.Add(self.btn_importar_prefs, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_restablecer_prefs = wx.Button(
            p, label=_("Restablecer todas las &preferencias…"),
            name=_("Restablecer todas las preferencias"))
        vs.Add(self.btn_restablecer_prefs, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_abrir_datos.Bind(wx.EVT_BUTTON, self._abrir_datos)
        self.btn_exportar_prefs.Bind(wx.EVT_BUTTON, self._exportar_prefs)
        self.btn_importar_prefs.Bind(wx.EVT_BUTTON, self._importar_prefs)
        self.btn_restablecer_prefs.Bind(wx.EVT_BUTTON, self._restablecer_prefs)

    def _abrir_datos(self, event):
        try:
            os.startfile(str(paths.carpeta_datos()))  # noqa: S606
        except Exception as exc:
            wx.MessageBox(_("No se pudo abrir la carpeta de datos:\n\n{exc}").format(exc=exc),
                          _("Carpeta de datos"), wx.OK | wx.ICON_ERROR,
                          self._ventana)

    def _exportar_prefs(self, event):
        with wx.FileDialog(
                self._ventana, _("Exportar las preferencias"),
                # Traductores: traduce solo «Preferencias»; no cambies «(*.ini)|*.ini».
                wildcard=_("Preferencias (*.ini)|*.ini"),
                defaultFile=f"{config.APP_NAME} preferencias.ini",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as cuadro:
            if cuadro.ShowModal() != wx.ID_OK:
                return
            ruta = cuadro.GetPath()
        try:
            preferencias_archivo.exportar(ruta)
        except Exception as exc:
            wx.MessageBox(_("No se pudieron exportar las preferencias:\n\n{exc}").format(exc=exc),
                          _("Exportar las preferencias"),
                          wx.OK | wx.ICON_ERROR, self._ventana)
            return
        anunciar(_("Preferencias exportadas"))

    def _importar_prefs(self, event):
        with wx.FileDialog(
                self._ventana, _("Importar las preferencias"),
                # Traductores: traduce solo «Preferencias»; no cambies «(*.ini)|*.ini».
                wildcard=_("Preferencias (*.ini)|*.ini"),
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as cuadro:
            if cuadro.ShowModal() != wx.ID_OK:
                return
            ruta = cuadro.GetPath()
        motivo = preferencias_archivo.motivo_no_importable(ruta)
        if motivo is not None:
            wx.MessageBox(motivo, _("Importar las preferencias"),
                          wx.OK | wx.ICON_WARNING, self._ventana)
            return
        try:
            preferencias_archivo.importar(ruta)
        except Exception as exc:
            wx.MessageBox(_("No se pudieron importar las preferencias:\n\n{exc}").format(exc=exc),
                          _("Importar las preferencias"),
                          wx.OK | wx.ICON_ERROR, self._ventana)
            return
        wx.MessageBox(_("Preferencias importadas. Se aplican al reiniciar "
                        "la aplicación."),
                      _("Preferencias importadas"),
                      wx.OK | wx.ICON_INFORMATION, self._ventana)
        # Como Cancelar: cierra sin guardar para no pisar el archivo nuevo.
        self._ventana.EndModal(wx.ID_CANCEL)

    def _restablecer_prefs(self, event):
        dialogo = wx.MessageDialog(
            self._ventana, _("¿Restablecer todas las preferencias a los valores "
                             "de fábrica? Se guarda una copia de las actuales en "
                             "la carpeta de datos."),
            _("Restablecer las preferencias"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION | wx.CENTRE)
        try:
            respuesta = dialogo.ShowModal()
        finally:
            dialogo.Destroy()
        if respuesta != wx.ID_YES:
            return
        try:
            preferencias_archivo.restablecer()
        except Exception as exc:
            wx.MessageBox(_("No se pudieron restablecer las preferencias:\n\n{exc}").format(exc=exc),
                          _("Restablecer las preferencias"),
                          wx.OK | wx.ICON_ERROR, self._ventana)
            return
        wx.MessageBox(_("Preferencias restablecidas. Se aplican al reiniciar "
                        "la aplicación."),
                      _("Preferencias restablecidas"),
                      wx.OK | wx.ICON_INFORMATION, self._ventana)
        self._ventana.EndModal(wx.ID_CANCEL)
