"""Bloque de la voz secundaria de la página Voces.

Dueño de sus controles, de cómo se cargan las voces y de cómo se guardan. La
página Voces le pasa las voces del motor y las de Windows y le pide recargar,
guardar y mostrar u ocultar el respaldo. La prueba de voz la dispara hacia la
página, que es dueña del `PruebaVoz` y de la voz principal.
"""

from __future__ import annotations

import wx

from bellbird.core.idioma import N_, _
from bellbird.ui.accesibilidad import ContadorAccesible
from bellbird.ui.gui import caja_de_grupo
from bellbird.ui.preferencias_comun import fila_label
from bellbird.ui.tema import _T, _tc
from bellbird.voice import escala_voz

_IGUAL_PRINCIPAL = N_("Igual que la voz principal")
_IGUAL_RESPALDO = N_("Igual que el respaldo de la voz principal")


def _porcentaje_de_volumen(config) -> int:
    try:
        return max(0, min(100, int(round(
            float(config.get("volumen_secundaria", 1.0)) * 100))))
    except (TypeError, ValueError):
        return 100


class BloqueVozSecundaria:
    """Voz, velocidad, volumen, prueba y respaldo de la voz secundaria."""

    def __init__(self, config, al_probar):
        self._config = config
        self._al_probar = al_probar
        self._voces = []
        self._voces_respaldo = []

    def construir(self, parent, voces, voces_respaldo):
        box, padre = caja_de_grupo(parent, _("Voz secundaria"))
        self._voces = list(voces or ())
        self._voces_respaldo = list(voces_respaldo or ())

        box.Add(self._crear_voz(padre), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        box.Add(self._crear_ajustes(padre), 0, wx.LEFT | wx.RIGHT, 10)
        box.Add(self._crear_probar(padre), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        box.Add(self._crear_respaldo(padre), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        return box

    def _crear_voz(self, padre):
        fila = wx.BoxSizer(wx.VERTICAL)
        fila.Add(fila_label(padre, _("Vo&z:")), 0, wx.BOTTOM, 6)
        self.cho_voz = wx.Choice(padre, name=_("Voz secundaria"))
        _tc(self.cho_voz)
        self.recargar_voces(self._voces)
        fila.Add(self.cho_voz, 0, wx.EXPAND | wx.BOTTOM, 6)
        return fila

    def _crear_ajustes(self, padre):
        fila = wx.BoxSizer(wx.VERTICAL)
        fila.Add(fila_label(padre, _("Veloci&dad (0 a 100):")), 0, wx.BOTTOM, 6)
        self.sp_velocidad = ContadorAccesible(
            padre, min=0, max=100,
            name=_("Velocidad de la voz secundaria"),
            initial=escala_voz.ajustar_velocidad(
                int(self._config.get("velocidad_secundaria",
                                     escala_voz.VELOCIDAD_NORMAL)), 0))
        self.sp_velocidad.SetIncrement(5)
        _tc(self.sp_velocidad)
        fila.Add(self.sp_velocidad, 0, wx.BOTTOM, 6)

        fila.Add(fila_label(padre, _("Volum&en (0 a 100):")), 0, wx.BOTTOM, 6)
        self.sp_volumen = ContadorAccesible(
            padre, min=0, max=100, initial=_porcentaje_de_volumen(self._config),
            name=_("Volumen de la voz secundaria"))
        self.sp_volumen.SetIncrement(5)
        _tc(self.sp_volumen)
        fila.Add(self.sp_volumen, 0, wx.BOTTOM, 6)
        return fila

    def _crear_probar(self, padre):
        self.btn_probar = wx.Button(
            padre, label=_("Proba&r voz secundaria"),
            name=_("Probar voz secundaria"))
        self.btn_probar.SetBackgroundColour(_T.btn)
        self.btn_probar.SetForegroundColour(_T.btn_t)
        self.btn_probar.Bind(wx.EVT_BUTTON, lambda _evento: self._al_probar())
        return self.btn_probar

    def _crear_respaldo(self, padre):
        fila = wx.BoxSizer(wx.VERTICAL)
        self.lbl_respaldo = fila_label(
            padre, _("Voz de W&indows de respaldo:"))
        self.cho_respaldo = wx.Choice(
            padre, name=_("Voz de Windows de respaldo de la voz secundaria"))
        _tc(self.cho_respaldo)
        self._cargar_respaldo()
        fila.Add(self.lbl_respaldo, 0, wx.BOTTOM, 6)
        fila.Add(self.cho_respaldo, 0, wx.EXPAND)
        return fila

    def _cargar_respaldo(self):
        guardada = self._config.get("voz_respaldo_secundaria") or ""
        items = [_(_IGUAL_RESPALDO)] + self._voces_respaldo
        self.cho_respaldo.SetItems(items)
        indice = escala_voz.resolver_voz(guardada, self._voces_respaldo)
        self.cho_respaldo.SetSelection(
            0 if indice is None else indice + 1)

    def recargar_voces(self, voces) -> None:
        """Rellena la lista con la voz guardada si sigue existiendo."""
        self._voces = list(voces or ())
        guardada = self._config.get("voz_secundaria") or ""
        self.cho_voz.SetItems([_(_IGUAL_PRINCIPAL)] + self._voces)
        indice = escala_voz.resolver_voz(guardada, self._voces)
        self.cho_voz.SetSelection(0 if indice is None else indice + 1)

    def mostrar_respaldo(self, visible: bool) -> None:
        self.lbl_respaldo.Show(visible)
        self.cho_respaldo.Show(visible)

    def datos_de_prueba(self):
        """La voz elegida (vacía es la principal), la velocidad y el volumen."""
        return (self._voz_elegida(), self.sp_velocidad.GetValue(),
                self.sp_volumen.GetValue())

    def _voz_elegida(self) -> str:
        indice = self.cho_voz.GetSelection()
        if 1 <= indice <= len(self._voces):
            return self._voces[indice - 1]
        return ""

    def guardar(self, fijar, en_memoria, hay_voces: bool) -> None:
        if hay_voces:
            voz = self._voz_elegida()
            fijar("voz", "voz_secundaria", voz)
            en_memoria["voz_secundaria"] = voz
        velocidad = escala_voz.ajustar_velocidad(
            self.sp_velocidad.GetValue(), 0)
        fijar("voz", "velocidad_secundaria", str(velocidad))
        en_memoria["velocidad_secundaria"] = velocidad
        volumen = self.sp_volumen.GetValue()
        fijar("voz", "volumen_secundaria", f"{volumen / 100:.2f}")
        en_memoria["volumen_secundaria"] = round(volumen / 100.0, 2)
        respaldo = self._respaldo_elegido()
        fijar("voz", "voz_respaldo_secundaria", respaldo)
        en_memoria["voz_respaldo_secundaria"] = respaldo

    def _respaldo_elegido(self) -> str:
        indice = self.cho_respaldo.GetSelection()
        if 1 <= indice <= len(self._voces_respaldo):
            return self._voces_respaldo[indice - 1]
        return ""
