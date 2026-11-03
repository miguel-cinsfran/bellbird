"""Pestaña Perfiles de Restream: los perfiles guardados de esta instalación.

Lista, crea, edita, duplica y elimina los perfiles. Los destinos que ofrece
el cuadro son los que ya se leyeron de la cuenta; la ventana se los pasa al
abrir el cuadro.
"""

from __future__ import annotations

from dataclasses import replace

import wx

from bellbird.core import sonidos_eventos
from bellbird.core.idioma import _, ngettext
from bellbird.restream import perfiles
from bellbird.ui.accesibilidad import anunciar, nombre_accesible
from bellbird.ui.busqueda_teclado import instalar_busqueda_tipo
from bellbird.ui.preferencias_comun import fila_horizontal
from bellbird.ui.restream_perfil import DialogoPerfilRestream
from bellbird.voice import sound_player as _snd


class PaginaPerfiles(wx.Panel):

    def __init__(self, parent, ruta, obtener_canales):
        super().__init__(parent, name="PaginaPerfilesRestream")
        self._ruta = ruta
        self._obtener_canales = obtener_canales
        self._perfiles = []
        self._crear_ui()
        self.poblar()

    def _crear_ui(self):
        vs = wx.BoxSizer(wx.VERTICAL)
        self.lista_perfiles = wx.ListBox(
            self, style=wx.LB_SINGLE | wx.LB_HSCROLL,
            name=_("Perfiles de Restream"))
        nombre_accesible(self.lista_perfiles, _("Perfiles de Restream"))
        instalar_busqueda_tipo(
            self.lista_perfiles,
            lambda: [self.lista_perfiles.GetString(i) for i
                     in range(self.lista_perfiles.GetCount())])
        self.lista_perfiles.Bind(wx.EVT_KEY_DOWN, self._al_tecla)
        vs.Add(self.lista_perfiles, 1, wx.EXPAND | wx.ALL, 8)

        self.btn_nuevo = wx.Button(
            self, label=_("&Nuevo…"), name=_("Nuevo"))
        self.btn_editar = wx.Button(
            self, label=_("&Editar…"), name=_("Editar"))
        self.btn_duplicar = wx.Button(
            self, label=_("D&uplicar"), name=_("Duplicar"))
        self.btn_eliminar = wx.Button(
            self, label=_("E&liminar"), name=_("Eliminar"))
        for boton in (self.btn_nuevo, self.btn_editar, self.btn_duplicar,
                      self.btn_eliminar):
            nombre_accesible(boton, boton.GetName())
        self.btn_nuevo.Bind(wx.EVT_BUTTON, lambda evento: self.nuevo())
        self.btn_editar.Bind(wx.EVT_BUTTON, lambda evento: self.editar())
        self.btn_duplicar.Bind(wx.EVT_BUTTON, lambda evento: self.duplicar())
        self.btn_eliminar.Bind(wx.EVT_BUTTON, lambda evento: self.eliminar())
        vs.Add(fila_horizontal((self.btn_nuevo, self.btn_editar,
                                self.btn_duplicar, self.btn_eliminar)),
               0, wx.ALL, 10)
        self.SetSizer(vs)

    def _etiqueta(self, perfil):
        cantidad = len(perfil.canales)
        cuenta = ngettext("{n} destino", "{n} destinos", cantidad).format(
            n=cantidad)
        return _("{nombre}, {orientacion}, {destinos}").format(
            nombre=perfil.nombre, orientacion=_(perfil.orientacion),
            destinos=cuenta)

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
        anunciar(_("Perfil de Restream guardado."))

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
        del self._perfiles[indice]
        perfiles.guardar(self._ruta, self._perfiles)
        self.poblar(indice)
        anunciar(_("Perfil de Restream eliminado."))

    def _nombre_copia(self, nombre):
        base = _("Copia de {nombre}").format(nombre=nombre)
        ocupados = {perfil.nombre.strip().casefold()
                    for perfil in self._perfiles}
        if base.casefold() not in ocupados:
            return base
        numero = 2
        while f"{base} {numero}".casefold() in ocupados:
            numero += 1
        return f"{base} {numero}"

    def _pedir_perfil(self, perfil, existentes):
        dialogo = DialogoPerfilRestream(
            self, perfil, list(self._obtener_canales()), existentes)
        try:
            if dialogo.ShowModal() != wx.ID_OK:
                return None
            return dialogo.perfil()
        finally:
            dialogo.Destroy()

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
        elif tecla == wx.WXK_DELETE:
            self.eliminar()
        else:
            evento.Skip()
