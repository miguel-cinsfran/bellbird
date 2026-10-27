"""Página General del diálogo de Preferencias.

Dueña de sus casillas y de las acciones sobre el archivo de preferencias.
El diálogo la construye por composición y copia solo las casillas que lee su
tabla de opciones simples.
"""

from __future__ import annotations

import os

import wx

from ytchat.core import paths
from ytchat.core import preferencias_archivo
from ytchat.ui.gui import anunciar
from ytchat.ui.preferencias_comun import crear_panel


class PaginaGeneral:
    """Página General: casillas de inicio y acciones sobre el archivo."""

    def __init__(self, ventana):
        self._ventana = ventana

    def construir(self, parent):
        p = crear_panel(parent, "PagGeneral")
        vs = wx.BoxSizer(wx.VERTICAL)
        self._casillas(p, vs)
        self._botones(p, vs)
        p.SetSizer(vs)
        return p

    def _casillas(self, p, vs):
        self.chk_buscar_actualizaciones = wx.CheckBox(
            p, label="Buscar &actualizaciones al iniciar",
            name="Buscar actualizaciones al iniciar")
        vs.Add(self.chk_buscar_actualizaciones, 0, wx.ALL, 10)

        self.chk_confirmar_salida = wx.CheckBox(
            p, label="Preguntar antes de &salir si hay un chat conectado "
                     "o una transmisión en curso",
            name="Preguntar antes de salir si hay un chat conectado "
                 "o una transmisión en curso")
        vs.Add(self.chk_confirmar_salida, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_sonido_inicio = wx.CheckBox(
            p, label="Reproducir el sonido de &inicio",
            name="Reproducir el sonido de inicio")
        vs.Add(self.chk_sonido_inicio, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_registro_detallado = wx.CheckBox(
            p, label="Guardar un registro &detallado para diagnosticar fallos",
            name="Guardar un registro detallado para diagnosticar fallos")
        vs.Add(self.chk_registro_detallado, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _botones(self, p, vs):
        # Archivo de preferencias: la importación y el restablecimiento piden
        # reiniciar y cierran el diálogo sin guardar, para que Guardar no pise
        # el archivo nuevo con los valores viejos de los controles.
        self.btn_abrir_datos = wx.Button(
            p, label="Abrir la carpeta de da&tos",
            name="Abrir la carpeta de datos")
        vs.Add(self.btn_abrir_datos, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_exportar_prefs = wx.Button(
            p, label="E&xportar las preferencias…",
            name="Exportar las preferencias")
        vs.Add(self.btn_exportar_prefs, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_importar_prefs = wx.Button(
            p, label="I&mportar las preferencias…",
            name="Importar las preferencias")
        vs.Add(self.btn_importar_prefs, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_restablecer_prefs = wx.Button(
            p, label="Restablecer todas las &preferencias…",
            name="Restablecer todas las preferencias")
        vs.Add(self.btn_restablecer_prefs, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_abrir_datos.Bind(wx.EVT_BUTTON, self._abrir_datos)
        self.btn_exportar_prefs.Bind(wx.EVT_BUTTON, self._exportar_prefs)
        self.btn_importar_prefs.Bind(wx.EVT_BUTTON, self._importar_prefs)
        self.btn_restablecer_prefs.Bind(wx.EVT_BUTTON, self._restablecer_prefs)

    def _abrir_datos(self, event):
        try:
            os.startfile(str(paths.carpeta_datos()))  # noqa: S606
        except Exception as exc:
            wx.MessageBox(f"No se pudo abrir la carpeta de datos:\n\n{exc}",
                          "Carpeta de datos", wx.OK | wx.ICON_ERROR,
                          self._ventana)

    def _exportar_prefs(self, event):
        with wx.FileDialog(
                self._ventana, "Exportar las preferencias",
                wildcard="Preferencias (*.ini)|*.ini",
                defaultFile="YTChat TTS preferencias.ini",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as cuadro:
            if cuadro.ShowModal() != wx.ID_OK:
                return
            ruta = cuadro.GetPath()
        try:
            preferencias_archivo.exportar(ruta)
        except Exception as exc:
            wx.MessageBox(f"No se pudieron exportar las preferencias:\n\n{exc}",
                          "Exportar las preferencias",
                          wx.OK | wx.ICON_ERROR, self._ventana)
            return
        anunciar("Preferencias exportadas")

    def _importar_prefs(self, event):
        with wx.FileDialog(
                self._ventana, "Importar las preferencias",
                wildcard="Preferencias (*.ini)|*.ini",
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as cuadro:
            if cuadro.ShowModal() != wx.ID_OK:
                return
            ruta = cuadro.GetPath()
        motivo = preferencias_archivo.motivo_no_importable(ruta)
        if motivo is not None:
            wx.MessageBox(motivo, "Importar las preferencias",
                          wx.OK | wx.ICON_WARNING, self._ventana)
            return
        try:
            preferencias_archivo.importar(ruta)
        except Exception as exc:
            wx.MessageBox("No se pudieron importar las preferencias:\n\n"
                          f"{exc}", "Importar las preferencias",
                          wx.OK | wx.ICON_ERROR, self._ventana)
            return
        wx.MessageBox("Preferencias importadas. Se aplican al reiniciar "
                      "la aplicación.",
                      "Preferencias importadas",
                      wx.OK | wx.ICON_INFORMATION, self._ventana)
        # Como Cancelar: cierra sin guardar para no pisar el archivo nuevo.
        self._ventana.EndModal(wx.ID_CANCEL)

    def _restablecer_prefs(self, event):
        dialogo = wx.MessageDialog(
            self._ventana, "¿Restablecer todas las preferencias a los valores "
                           "de fábrica? Se guarda una copia de las actuales en "
                           "la carpeta de datos.",
            "Restablecer las preferencias",
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
            wx.MessageBox("No se pudieron restablecer las preferencias:\n\n"
                          f"{exc}",
                          "Restablecer las preferencias",
                          wx.OK | wx.ICON_ERROR, self._ventana)
            return
        wx.MessageBox("Preferencias restablecidas. Se aplican al reiniciar "
                      "la aplicación.",
                      "Preferencias restablecidas",
                      wx.OK | wx.ICON_INFORMATION, self._ventana)
        self._ventana.EndModal(wx.ID_CANCEL)
