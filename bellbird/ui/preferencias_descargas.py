"""Página Descargas del diálogo de Preferencias.

Dueña de sus controles y de su guardado propio. El diálogo la construye
por composición, como la de Música.
"""

from __future__ import annotations

import wx

from bellbird.core import config as cfg
from bellbird.core.idioma import _
from bellbird.downloads.opciones_formato import (
    LIMITE_MAX, PLANTILLAS, SIMULTANEAS_MAX, SIMULTANEAS_MIN)
from bellbird.ui.accesibilidad import ContadorAccesible, nombre_accesible
from bellbird.ui.gui_descargas import nombrar_selector_carpeta
from bellbird.ui.preferencias_comun import crear_panel, fila_label
from bellbird.ui.tema import _T, _tc


class PaginaDescargasPreferencias:
    """Página Descargas: carpeta, numeración, subcarpeta, nombre y topes."""

    def __init__(self):
        self.dir_descargas = None
        self.chk_descargas_numerar = None
        self.chk_descargas_carpeta_lista = None
        self.cho_descargas_plantilla = None
        self.sp_descargas_simultaneas = None
        self.sp_descargas_limite = None
        self._plantillas_claves = [clave for _etiqueta, clave, _plantilla in PLANTILLAS]

    def construir(self, parent):
        p = crear_panel(parent, "PagDescargas")
        vs = wx.BoxSizer(wx.VERTICAL)
        self._descargas_carpeta(p, vs)
        self._descargas_listas(p, vs)
        self._descargas_topes(p, vs)
        self._cargar()
        p.SetSizer(vs)
        return p

    def _descargas_carpeta(self, p, vs):
        vs.Add(fila_label(p, _("Carpeta de &descargas:")),
               0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.dir_descargas = wx.DirPickerCtrl(
            p, path=cfg.obtener_opciones_descarga().get("carpeta") or "",
            name=_("Carpeta de descargas"),
            message=_("Elige la carpeta de descargas"))
        nombrar_selector_carpeta(self.dir_descargas)
        if hasattr(self.dir_descargas, "GetTextCtrl"):
            nombre_accesible(self.dir_descargas.GetTextCtrl(),
                              _("Carpeta de descargas"))
        vs.Add(self.dir_descargas, 0,
               wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _descargas_listas(self, p, vs):
        self.chk_descargas_numerar = wx.CheckBox(
            p, label=_("&Numerar archivos de listas"),
            name="DescargasNumerar")
        self.chk_descargas_numerar.SetForegroundColour(_T.text)
        vs.Add(self.chk_descargas_numerar, 0, wx.ALL, 10)
        self.chk_descargas_carpeta_lista = wx.CheckBox(
            p, label=_("Carpeta propia para cada &lista"),
            name="DescargasCarpetaLista")
        self.chk_descargas_carpeta_lista.SetForegroundColour(_T.text)
        vs.Add(self.chk_descargas_carpeta_lista, 0,
               wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        vs.Add(fila_label(p, _("Nombre de los &archivos:")),
               0, wx.LEFT | wx.RIGHT, 10)
        etiquetas = [_(etiqueta) for etiqueta, _clave, _plantilla in PLANTILLAS]
        self.cho_descargas_plantilla = wx.Choice(
            p, choices=etiquetas, name=_("Nombre de los archivos"))
        _tc(self.cho_descargas_plantilla)
        vs.Add(self.cho_descargas_plantilla, 0,
               wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _descargas_topes(self, p, vs):
        vs.Add(fila_label(p, _("Descargas &simultáneas:")),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_descargas_simultaneas = ContadorAccesible(
            p, min=SIMULTANEAS_MIN, max=SIMULTANEAS_MAX,
            name=_("Descargas simultáneas"))
        vs.Add(self.sp_descargas_simultaneas, 0,
               wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        vs.Add(fila_label(p, _("Límite de &velocidad en MB/s, 0 sin límite:")),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_descargas_limite = ContadorAccesible(
            p, min=0, max=LIMITE_MAX,
            name=_("Límite de velocidad en MB/s"))
        vs.Add(self.sp_descargas_limite, 0,
               wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _cargar(self):
        """Vuelca las opciones guardadas en los seis controles."""
        opciones = cfg.obtener_opciones_descarga()
        self.dir_descargas.SetPath(str(opciones.get("carpeta") or ""))
        self.chk_descargas_numerar.SetValue(bool(opciones.get("enumerar", False)))
        self.chk_descargas_carpeta_lista.SetValue(bool(opciones.get("carpeta_lista", False)))
        try:
            indice = self._plantillas_claves.index(opciones.get("plantilla"))
        except ValueError:
            indice = 0
        self.cho_descargas_plantilla.SetSelection(indice)
        self.sp_descargas_simultaneas.SetValue(int(opciones.get("simultaneas", 2)))
        self.sp_descargas_limite.SetValue(int(opciones.get("limite", 0)))

    def guardar(self):
        """Guarda la página sin tocar formato, bitrate ni resolución."""
        opciones = cfg.obtener_opciones_descarga()
        opciones["carpeta"] = self.dir_descargas.GetPath()
        opciones["enumerar"] = bool(self.chk_descargas_numerar.GetValue())
        opciones["carpeta_lista"] = bool(self.chk_descargas_carpeta_lista.GetValue())
        indice = self.cho_descargas_plantilla.GetSelection()
        if 0 <= indice < len(self._plantillas_claves):
            opciones["plantilla"] = self._plantillas_claves[indice]
        else:
            opciones["plantilla"] = "titulo_id"
        opciones["simultaneas"] = int(self.sp_descargas_simultaneas.GetValue())
        opciones["limite"] = int(self.sp_descargas_limite.GetValue())
        cfg.guardar_opciones_descarga(opciones)
