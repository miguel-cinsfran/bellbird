"""Tandas de resultados pedidas en un hilo, para la búsqueda y su vista.

Razón del módulo: pedir tandas con una función traer y entregar lo que
llegó, descartando lo viejo. La página lo usa con buscar y la vista de
contenido con contenido.
"""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.ui.accesibilidad import anunciar


def anunciar_tanda(cuantos: int, mas: bool) -> None:
    """Avisa cuántos resultados trajo la tanda."""
    if cuantos == 1:
        anunciar(_("1 resultado más") if mas else _("1 resultado"))
    elif mas:
        anunciar(_("{cantidad} resultados más").format(cantidad=cuantos))
    else:
        anunciar(_("{cantidad} resultados").format(cantidad=cuantos))


class Tandas:
    """Tandas pedidas en un hilo, con lo acumulado sin repetir id."""

    def __init__(self, lista, btn_mas):
        self._lista = lista
        self._btn_mas = btn_mas
        self._generacion = 0
        self._inicio = 1
        self._hay_mas = False
        self._acumulado = []

    @property
    def generacion(self) -> int:
        return self._generacion

    @property
    def inicio(self) -> int:
        return self._inicio

    @property
    def acumulado(self) -> list:
        return list(self._acumulado)

    def pedir(self, traer, cantidad, al_tanda, mas=False, nombre="Tandas") -> None:
        """Pide una tanda con traer(inicio, cantidad) en un hilo.

        al_tanda(nuevos, mas, respuesta, foco_en_mas) corre en la GUI
        con lo nuevo ya acumulado; una llegada vieja se descarta.
        """
        inicio = self._inicio if mas else 1
        if not mas:
            self._inicio = 1
            self._acumulado = []
            self._lista.DeleteAllItems()
            self._btn_mas.Disable()
        self._generacion += 1
        hilo = diagnostico.crear_hilo(
            self._pedir_en_hilo, nombre,
            args=(self._generacion, traer, inicio, cantidad, mas, al_tanda))
        hilo.start()

    def _pedir_en_hilo(self, generacion, traer, inicio, cantidad, mas, al_tanda):
        respuesta = traer(inicio, cantidad)
        wx.CallAfter(self.llegada, generacion, respuesta, inicio,
                     cantidad, mas, al_tanda)

    def llegada(self, generacion, respuesta, inicio, cantidad, mas,
               al_tanda) -> None:
        if generacion != self._generacion:
            return
        foco_en_mas = wx.Window.FindFocus() is self._btn_mas
        if respuesta.error:
            self._hay_mas = self._hay_mas and mas
            self._btn_mas.Enable(self._hay_mas)
            al_tanda([], mas, respuesta, foco_en_mas)
            return
        vistos = {r.id for r in self._acumulado}
        nuevos = [r for r in respuesta.resultados if r.id not in vistos]
        self._acumulado.extend(nuevos)
        self._inicio = inicio + cantidad
        self._hay_mas = bool(respuesta.hay_mas)
        self._btn_mas.Enable(self._hay_mas)
        al_tanda(nuevos, mas, respuesta, foco_en_mas)
