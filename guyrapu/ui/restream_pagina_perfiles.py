"""Pestaña Perfiles de Restream: los perfiles guardados de esta instalación.

Lista, crea, edita, cambia el nombre, duplica y elimina los perfiles. Las
acciones de la fila viven en su menú contextual, como en la pestaña Escena
del Panel de OBS. El único botón es el que no depende de la fila.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import wx

from guyrapu.core import sonidos_eventos
from guyrapu.core.idioma import _
from guyrapu.obs import nombres_escena
from guyrapu.restream import perfiles, resumen_cuenta
from guyrapu.ui import confirmar, restream_menus
from guyrapu.ui.accesibilidad import anunciar, nombre_accesible
from guyrapu.ui.busqueda_teclado import instalar_busqueda_tipo
from guyrapu.ui.preferencias_comun import fila_horizontal
from guyrapu.ui.restream_perfil import (
    DialogoNombrePerfil,
    DialogoPerfilRestream,
)
from guyrapu.voice import sound_player as _snd


class PaginaPerfiles(wx.Panel):

    def __init__(self, parent, ruta, obtener_canales, nombres_destinos=None,
                 destinos_leidos=None, esta_conectada=None):
        super().__init__(parent, name="PaginaPerfilesRestream")
        self._ruta = ruta
        self._obtener_canales = obtener_canales
        self._nombres_destinos = nombres_destinos
        self._destinos_leidos = destinos_leidos
        self._esta_conectada = esta_conectada
        self._perfiles = []
        self._crear_ui()
        self.poblar()

    def _crear_ui(self):
        vs = wx.BoxSizer(wx.VERTICAL)
        self.lista_perfiles = wx.ListBox(
            self, style=wx.LB_SINGLE | wx.LB_HSCROLL, name=_("Perfiles"))
        nombre_accesible(self.lista_perfiles, _("Perfiles"))
        instalar_busqueda_tipo(
            self.lista_perfiles,
            lambda: [self.lista_perfiles.GetString(i) for i
                     in range(self.lista_perfiles.GetCount())])
        self.lista_perfiles.Bind(wx.EVT_KEY_DOWN, self._al_tecla)
        self.lista_perfiles.Bind(wx.EVT_CONTEXT_MENU, self._menu_contextual)
        self.lista_perfiles.Bind(wx.EVT_SET_FOCUS, self._al_foco)
        vs.Add(self.lista_perfiles, 1, wx.EXPAND | wx.ALL, 8)

        self.btn_nuevo = wx.Button(
            self, label=_("&Nuevo perfil…"), name=_("Nuevo perfil"))
        nombre_accesible(self.btn_nuevo, self.btn_nuevo.GetName())
        self.btn_nuevo.Bind(wx.EVT_BUTTON, lambda evento: self.nuevo())
        vs.Add(fila_horizontal((self.btn_nuevo,)), 0, wx.ALL, 10)
        self.SetSizer(vs)

    def cantidad(self):
        return len(self._perfiles)

    def _nombres(self):
        if self._nombres_destinos is None:
            return {}
        try:
            return dict(self._nombres_destinos())
        except Exception:
            return {}

    def _leidos(self):
        if self._destinos_leidos is None:
            return False
        try:
            return bool(self._destinos_leidos())
        except Exception:
            return False

    def _conectada(self):
        if self._esta_conectada is None:
            return True
        try:
            return bool(self._esta_conectada())
        except Exception:
            return False

    def _etiqueta(self, perfil):
        return resumen_cuenta.fila_perfil(
            perfil, self._nombres(), self._leidos())

    def poblar(self, indice=None):
        self._perfiles = perfiles.cargar(self._ruta)
        self.lista_perfiles.Clear()
        for perfil in self._perfiles:
            self.lista_perfiles.Append(self._etiqueta(perfil))
        if not self._perfiles:
            return
        if indice is None:
            indice = 0
        indice = max(0, min(indice, len(self._perfiles) - 1))
        self.lista_perfiles.SetSelection(indice)

    def actualizar(self):
        indice = self.lista_perfiles.GetSelection()
        self.poblar(indice if indice >= 0 else None)

    def _indice_seleccionado(self):
        indice = self.lista_perfiles.GetSelection()
        if 0 <= indice < len(self._perfiles):
            return indice
        return None

    def nuevo(self):
        perfil = self._pedir_perfil(None, self._perfiles)
        if perfil is None:
            return
        self._perfiles.append(perfil)
        perfiles.guardar(self._ruta, self._perfiles)
        self.poblar(len(self._perfiles) - 1)
        anunciar(_("Perfil de Restream guardado. Elígelo en Transmitir a, "
                   "en la pestaña Transmisión."))

    def editar(self):
        indice = self._indice_seleccionado()
        if indice is None:
            anunciar(_("Sin selección"))
            return
        actual = self._perfiles[indice]
        existentes = [perfil for posicion, perfil
                      in enumerate(self._perfiles) if posicion != indice]
        perfil = self._pedir_perfil(actual, existentes)
        if perfil is None:
            return
        self._perfiles[indice] = perfil
        perfiles.guardar(self._ruta, self._perfiles)
        self.poblar(indice)
        anunciar(_("Perfil de Restream guardado."))

    def renombrar(self):
        indice = self._indice_seleccionado()
        if indice is None:
            anunciar(_("Sin selección"))
            return
        actual = self._perfiles[indice]
        existentes = [perfil for posicion, perfil
                      in enumerate(self._perfiles) if posicion != indice]
        nombre = self._pedir_nombre(actual, existentes)
        if nombre is None:
            return
        self._perfiles[indice] = replace(actual, nombre=nombre)
        perfiles.guardar(self._ruta, self._perfiles)
        self.poblar(indice)
        self.lista_perfiles.SetFocus()
        anunciar(_("Nombre cambiado."))

    def duplicar(self):
        indice = self._indice_seleccionado()
        if indice is None:
            anunciar(_("Sin selección"))
            return
        actual = self._perfiles[indice]
        copia = replace(actual, nombre=self._nombre_copia(actual.nombre))
        self._perfiles.append(copia)
        perfiles.guardar(self._ruta, self._perfiles)
        self.poblar(len(self._perfiles) - 1)
        anunciar(_("Perfil de Restream duplicado."))

    def eliminar(self):
        indice = self._indice_seleccionado()
        if indice is None:
            anunciar(_("Sin selección"))
            return
        if not self.confirmar(self._perfiles[indice]):
            return
        del self._perfiles[indice]
        perfiles.guardar(self._ruta, self._perfiles)
        self.poblar(indice)
        self.lista_perfiles.SetFocus()
        anunciar(_("Perfil de Restream eliminado."))

    def confirmar(self, perfil):
        return confirmar.preguntar(
            self, _("¿Eliminar el perfil {nombre}?").format(
                nombre=perfil.nombre),
            _("Eliminar perfil"), _("&Eliminar"), _("&Cancelar"),
            predeterminado_si=False)

    def _nombre_copia(self, nombre):
        return nombres_escena.nombre_de_copia(
            nombre, {perfil.nombre for perfil in self._perfiles})

    def _pedir_perfil(self, perfil, existentes):
        dialogo = DialogoPerfilRestream(
            self, perfil, list(self._obtener_canales()), existentes,
            sin_cuenta=not self._conectada())
        try:
            if dialogo.ShowModal() != wx.ID_OK:
                return None
            return dialogo.perfil()
        finally:
            dialogo.Destroy()

    def _pedir_nombre(self, actual, existentes):
        nombre = actual.nombre
        while True:
            dialogo = DialogoNombrePerfil(self, nombre)
            try:
                if dialogo.ShowModal() != wx.ID_OK:
                    return None
                nombre = dialogo.nombre()
            finally:
                dialogo.Destroy()
            mensajes = perfiles.validar(
                replace(actual, nombre=nombre), existentes)
            if not mensajes:
                return nombre
            anunciar(" ".join(mensajes))

    def _al_foco(self, evento):
        if not self.lista_perfiles.GetCount() and not self._conectada():
            self._avisar_sin_cuenta()
        evento.Skip()

    def _avisar_sin_cuenta(self):
        padre = self.GetParent()
        if getattr(padre, "_sin_cuenta_anunciado", False):
            return
        padre._sin_cuenta_anunciado = True
        anunciar(_("Sin cuenta de Restream. Conéctala en la pestaña Cuenta."))

    def _menu_contextual(self, evento):
        if self._indice_seleccionado() is None:
            anunciar(_("Sin selección"))
            return
        acciones = SimpleNamespace(
            editar=self.editar, renombrar=self.renombrar,
            duplicar=self.duplicar, eliminar=self.eliminar)
        menu = restream_menus.menu_perfil(acciones)
        self.lista_perfiles.PopupMenu(menu)
        menu.Destroy()
        evento.Skip()

    def _al_tecla(self, evento):
        lista = evento.GetEventObject()
        try:
            seleccion, total = lista.GetSelection(), lista.GetCount()
        except Exception:
            seleccion, total = -1, 0
        tecla = evento.GetKeyCode()
        if sonidos_eventos.es_orilla(tecla, seleccion, total):
            _snd.reproducir("orilla")
        if tecla in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.editar()
        elif tecla == wx.WXK_F2:
            self.renombrar()
        elif tecla in (ord("D"), ord("d")) and evento.ControlDown():
            self.duplicar()
        elif tecla == wx.WXK_DELETE:
            self.eliminar()
        elif (tecla == wx.WXK_WINDOWS_MENU
              or (tecla == wx.WXK_F10 and evento.ShiftDown())):
            self._menu_contextual(evento)
        else:
            evento.Skip()
