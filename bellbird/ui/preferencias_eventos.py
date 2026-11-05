"""Página Eventos del directo del diálogo de Preferencias.

Por composición, igual que `PaginaLectura`: recibe en el constructor lo que
necesita del diálogo (el dict de config y dos helpers como funciones) y
expone `construir(parent)`, que devuelve el panel. Los controles conservan
nombre, rótulo, `name=` y orden; el diálogo los reexporta como atributos
propios para las pruebas y la tabla.
"""

from __future__ import annotations

import wx

from bellbird.core.avisos_tiktok import EVENTOS, MODOS_EVENTO
from bellbird.core.idioma import N_, _
from bellbird.ui.accesibilidad import ContadorAccesible
from bellbird.ui.tema import _T, _tc
from bellbird.ui.preferencias_comun import EleccionTexto


_EVENTOS = {
    "superchat": N_("&Super Chats y regalos:"),
    "miembro": N_("Mem&bresías:"),
    "entrada": N_("&Entradas al directo:"),
    "me_gusta": N_("Me g&usta:"),
    "seguir": N_("Seguidores nue&vos:"),
    "compartir": N_("&Directo compartido:"),
    "cofre": N_("Co&fres:"),
    "encuesta": N_("Encues&tas:"),
    "meta": N_("&Metas:"),
    "batalla": N_("Batal&las:"),
}


OPCIONES_EVENTOS = (
    ("cho_evento_superchat", "eventos", "superchat", "evento_superchat",
     str, "principal"),
    ("cho_evento_miembro", "eventos", "miembro", "evento_miembro",
     str, "principal"),
    ("cho_evento_entrada", "eventos", "entrada", "evento_entrada",
     str, "mostrar"),
    ("chk_agrupar_entradas", "tiktok", "agrupar_entradas",
     "tiktok_agrupar_entradas", bool, True),
    ("sp_segundos_entradas", "tiktok", "segundos_entradas",
     "tiktok_segundos_entradas", int, 10),
    ("cho_evento_me_gusta", "eventos", "me_gusta", "evento_me_gusta",
     str, "mostrar"),
    ("chk_agrupar_me_gusta", "tiktok", "agrupar_me_gusta",
     "tiktok_agrupar_me_gusta", bool, True),
    ("sp_segundos_me_gusta", "tiktok", "segundos_me_gusta",
     "tiktok_segundos_me_gusta", int, 10),
    ("cho_evento_seguir", "eventos", "seguir", "evento_seguir",
     str, "principal"),
    ("cho_evento_compartir", "eventos", "compartir", "evento_compartir",
     str, "principal"),
    ("cho_evento_cofre", "eventos", "cofre", "evento_cofre",
     str, "principal"),
    ("cho_evento_encuesta", "eventos", "encuesta", "evento_encuesta",
     str, "principal"),
    ("cho_evento_meta", "eventos", "meta", "evento_meta",
     str, "principal"),
    ("cho_evento_batalla", "eventos", "batalla", "evento_batalla",
     str, "principal"),
)


class PaginaEventos:
    """Página Eventos del directo: qué se hace con cada evento."""

    def __init__(self, config, fila_label, make_panel):
        self._config = config
        self._fila_label = fila_label
        self._make_panel = make_panel

    def construir(self, parent):
        p = self._make_panel(parent, "PagEventos")
        vs = wx.BoxSizer(wx.VERTICAL)
        grilla = wx.FlexGridSizer(0, 2, 6, 10)
        grilla.AddGrowableCol(1, 1)
        for clave, _fabrica in EVENTOS:
            texto = _(_EVENTOS[clave])
            grilla.Add(self._fila_label(p, texto), 0,
                       wx.ALIGN_CENTER_VERTICAL)
            lista = EleccionTexto(
                p, [(valor, _(rotulo)) for valor, rotulo in MODOS_EVENTO],
                name=texto.replace("&", "").rstrip(":"))
            _tc(lista)
            setattr(self, "cho_evento_" + clave, lista)
            grilla.Add(lista, 0, wx.EXPAND)
            if clave == "entrada":
                self._agregar_agrupacion(
                    grilla, p, "agrupar_entradas",
                    _("Agrupar ent&radas"), _("Agrupar entradas"),
                    _("Agrupar entradas durante (segund&os):"),
                    _("Agrupar entradas durante, en segundos"),
                    "sp_segundos_entradas")
            if clave == "me_gusta":
                self._agregar_agrupacion(
                    grilla, p, "agrupar_me_gusta",
                    _("Agru&par me gusta"), _("Agrupar me gusta"),
                    _("&Agrupar me gusta durante (segundos):"),
                    _("Agrupar me gusta durante, en segundos"),
                    "sp_segundos_me_gusta")
        vs.Add(grilla, 1, wx.EXPAND | wx.ALL, 10)
        p.SetSizer(vs)
        return p

    def _agregar_agrupacion(self, grilla, padre, clave, etiqueta, nombre,
                            etiqueta_contador, nombre_contador, atributo):
        casilla = wx.CheckBox(padre, label=etiqueta, name=nombre)
        casilla.SetForegroundColour(_T.text)
        _tc(casilla)
        setattr(self, "chk_" + clave, casilla)
        grilla.Add((0, 0), 0)
        grilla.Add(casilla, 0, wx.EXPAND)
        grilla.Add(self._fila_label(padre, etiqueta_contador), 0,
                   wx.ALIGN_CENTER_VERTICAL)
        contador = ContadorAccesible(padre, min=1, max=120,
                                     name=nombre_contador)
        _tc(contador)
        setattr(self, atributo, contador)
        grilla.Add(contador, 0)
