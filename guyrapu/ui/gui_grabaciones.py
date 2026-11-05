"""Lista de grabaciones y clips de la app, como panel de la pestaña Grabación.

Su única razón para cambiar: la lista de grabaciones y clips. Las teclas, el
menú contextual y el foco siguen el patrón de `HistorialDialog`, y abrir un
archivo o su carpeta, el de las acciones de descargas.
"""

from __future__ import annotations

import os
import subprocess

import wx

from guyrapu.core import diagnostico
from guyrapu.core.idioma import N_, _
from guyrapu.obs import grabaciones
from guyrapu.ui.accesibilidad import anunciar, nombre_accesible
from guyrapu.ui.gui import copiar_al_portapapeles
from guyrapu.voice import sound_player

logger = diagnostico.obtener_logger(__name__)

_NO_HAY = N_("No hay grabaciones ni clips guardados.")
_ABRIR = N_("&Abrir")
_ABRIR_CARPETA = N_("Abrir ca&rpeta")
_COPIAR_RUTA = N_("&Copiar ruta")
_ELIMINAR = N_("E&liminar de la lista")


class PanelGrabaciones(wx.Panel):
    """Lista las grabaciones y los clips de la app, del más nuevo al más viejo."""

    def __init__(self, parent):
        super().__init__(parent, name="PanelGrabaciones")
        self._entradas = []
        self._crear_controles()
        self.poblar()

    def _crear_controles(self):
        vertical = wx.BoxSizer(wx.VERTICAL)
        self._lista = wx.ListBox(self, style=wx.LB_SINGLE | wx.LB_HSCROLL,
                                 name=_("Grabaciones y clips"))
        nombre_accesible(self._lista, _("Grabaciones y clips"))
        self._lista.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self._lista.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)
        vertical.Add(self._lista, 1, wx.EXPAND | wx.ALL, 6)
        self.SetSizer(vertical)

    def poblar(self, indice=0):
        """Relee las grabaciones y deja la selección en `indice`."""
        self._entradas = grabaciones.existentes()
        self._lista.Clear()
        if not self._entradas:
            self._lista.Append(_(_NO_HAY))
            indice = 0
        else:
            for entrada in self._entradas:
                self._lista.Append(grabaciones.texto_fila(entrada))
            indice = min(max(indice, 0), len(self._entradas) - 1)
        self._lista.SetSelection(indice)

    def _seleccionada(self):
        indice = self._lista.GetSelection()
        if indice == wx.NOT_FOUND or indice >= len(self._entradas):
            return None
        return self._entradas[indice]

    def _sin_grabaciones(self):
        anunciar(_(_NO_HAY))

    def _falta(self, texto):
        try:
            sound_player.reproducir("error")
        except Exception as error:
            logger.debug("sin sonido: %s", error)
        anunciar(texto)

    def _on_key(self, evento):
        tecla = evento.GetKeyCode()
        if tecla in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._abrir()
        elif tecla == wx.WXK_DELETE:
            self._eliminar()
        elif (tecla == wx.WXK_WINDOWS_MENU
              or (tecla == wx.WXK_F10 and evento.ShiftDown())):
            self._mostrar_menu()
        else:
            evento.Skip()

    def _on_context_menu(self, _evento):
        self._mostrar_menu()

    def _mostrar_menu(self):
        menu = wx.Menu()
        for etiqueta, accion in ((_ABRIR, self._abrir),
                                 (_ABRIR_CARPETA, self._abrir_carpeta),
                                 (_COPIAR_RUTA, self._copiar_ruta),
                                 (_ELIMINAR, self._eliminar)):
            identificador = wx.NewIdRef()
            menu.Append(identificador, _(etiqueta))
            menu.Bind(wx.EVT_MENU,
                      lambda _evento, funcion=accion: funcion(),
                      id=identificador)
        self._lista.PopupMenu(menu)
        menu.Destroy()

    def _abrir(self):
        entrada = self._seleccionada()
        if entrada is None:
            self._sin_grabaciones()
            return
        try:
            if not os.path.exists(entrada.get("ruta") or ""):
                raise OSError("falta")
            os.startfile(entrada["ruta"])
        except Exception as error:
            logger.debug("abrir grabación: %s", error)
            self._falta(_("El archivo ya no está disponible."))

    def _abrir_carpeta(self):
        entrada = self._seleccionada()
        if entrada is None:
            self._sin_grabaciones()
            return
        ruta = entrada.get("ruta") or ""
        try:
            if ruta and os.path.exists(ruta):
                subprocess.Popen(["explorer", "/select,", ruta])
                return
            carpeta = os.path.dirname(ruta)
            if carpeta and os.path.exists(carpeta):
                os.startfile(carpeta)
                return
        except Exception as error:
            logger.debug("abrir carpeta de la grabación: %s", error)
        self._falta(_("La carpeta ya no está disponible."))

    def _copiar_ruta(self):
        entrada = self._seleccionada()
        if entrada is None:
            self._sin_grabaciones()
            return
        copiar_al_portapapeles(entrada.get("ruta") or "")
        try:
            sound_player.reproducir("copiar")
        except Exception as error:
            logger.debug("sin sonido: %s", error)
        anunciar(_("Ruta copiada"))

    def _eliminar(self):
        entrada = self._seleccionada()
        if entrada is None:
            self._sin_grabaciones()
            return
        indice = self._lista.GetSelection()
        grabaciones.quitar(entrada.get("ruta") or "")
        anunciar(_("Eliminada de la lista"))
        self.poblar(indice)
        self._lista.SetFocus()
