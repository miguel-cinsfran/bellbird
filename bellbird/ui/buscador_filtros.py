"""Los filtros de la pestaña de búsqueda en YouTube.

Una clase con su propio estado que arma la casilla, los rótulos y los
cuatro cuadros y sabe lo que se eligió. No lee atributos privados de la
página: la página le pasa el callback de cambio de orden y le pide lo
elegido con `actuales()` y `orden_elegido()`.
"""

from __future__ import annotations

import wx

from bellbird.core.idioma import N_, _
from bellbird.downloads.busqueda_youtube import Filtros
from bellbird.ui.tema import _T, _tc

_TIPOS = ((N_("Vídeos"), "videos"), (N_("Listas"), "listas"),
          (N_("Canales"), "canales"), (N_("En directo"), "directo"))
_DURACIONES = ((N_("Cualquiera"), ""), (N_("Menos de 4 minutos"), "corta"),
               (N_("De 4 a 20 minutos"), "media"),
               (N_("Más de 20 minutos"), "larga"))
_FECHAS = ((N_("Cualquiera"), ""), (N_("Hoy"), "hoy"),
           (N_("Esta semana"), "semana"), (N_("Este mes"), "mes"),
           (N_("Este año"), "anio"))
_ORDENES = ((N_("Relevancia"), "relevancia"), (N_("Fecha"), "fecha"),
            (N_("Vistas"), "vistas"), (N_("Duración"), "duracion"))


class FiltrosBusqueda:
    """La casilla «Mostrar filtros» y los cuatro cuadros que pliega."""

    def __init__(self, panel, al_cambiar_orden=None):
        self._panel = panel
        self.chk_filtros = wx.CheckBox(panel, label=_("Mostrar fi&ltros"),
                                       name=_("Mostrar filtros"))
        self.chk_filtros.SetForegroundColour(_T.text)
        fila = wx.BoxSizer(wx.HORIZONTAL)
        self._controles_filtros = []
        pares = (
            (_("Ti&po:"), _("Tipo"), _TIPOS),
            (_("Du&ración:"), _("Duración"), _DURACIONES),
            (_("Fec&ha:"), _("Fecha"), _FECHAS),
            (_("&Orden:"), _("Orden"), _ORDENES),
        )
        elecciones = []
        for texto, nombre, _opciones in pares:
            lbl = wx.StaticText(panel, label=texto)
            lbl.SetForegroundColour(_T.text)
            fila.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
            cho = wx.Choice(panel, name=nombre)
            _tc(cho)
            fila.Add(cho, 1, wx.EXPAND | wx.RIGHT, 6)
            self._controles_filtros.extend((lbl, cho))
            elecciones.append(cho)
        (self.cho_tipo, self.cho_duracion,
         self.cho_fecha, self.cho_orden) = elecciones
        if callable(al_cambiar_orden):
            self.cho_orden.Bind(wx.EVT_CHOICE, al_cambiar_orden)
        for control in self._controles_filtros:
            control.Show(False)
        self.sizer = fila

    def cargar_opciones(self) -> None:
        """Pone los textos traducidos en los cuatro cuadros."""
        for cho, opciones in ((self.cho_tipo, _TIPOS),
                              (self.cho_duracion, _DURACIONES),
                              (self.cho_fecha, _FECHAS),
                              (self.cho_orden, _ORDENES)):
            cho.Set([_(etiqueta) for etiqueta, _valor in opciones])
            cho.SetSelection(0)

    def actuales(self) -> Filtros:
        """Lo elegido en los cuadros; sin marcar la casilla, sin filtros."""
        if not self.chk_filtros.GetValue():
            return Filtros()

        def _elegido(cho, opciones):
            idx = cho.GetSelection()
            if 0 <= idx < len(opciones):
                return opciones[idx][1]
            return opciones[0][1]
        return Filtros(
            tipo=_elegido(self.cho_tipo, _TIPOS),
            duracion=_elegido(self.cho_duracion, _DURACIONES),
            fecha=_elegido(self.cho_fecha, _FECHAS),
            orden=_elegido(self.cho_orden, _ORDENES))

    def orden_elegido(self) -> str:
        """El orden elegido en su cuadro, o relevancia si no hay elección."""
        idx = self.cho_orden.GetSelection()
        return _ORDENES[idx][1] if 0 <= idx < len(_ORDENES) else "relevancia"

    def aplicar_visibilidad(self) -> None:
        """Muestra u oculta los cuadros según la casilla."""
        mostrar = self.chk_filtros.GetValue()
        for control in self._controles_filtros:
            control.Show(mostrar)
        self._panel.Layout()
