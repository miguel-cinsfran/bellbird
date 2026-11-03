"""Ventana de Restream: la cuenta y los perfiles de transmisión (accesible).

Dos pestañas. Cuenta muestra el estado y deja conectar, volver a autorizar o
desconectar con lo que se le inyecta. Perfiles lista, crea, edita, duplica y
elimina los perfiles guardados. Todavía no entra al menú: la conexión real
llega desde afuera.
"""

from __future__ import annotations

from dataclasses import replace

import wx

from bellbird.core import sonidos_eventos
from bellbird.core.idioma import _, ngettext
from bellbird.restream import perfiles
from bellbird.ui import paleta
from bellbird.ui.accesibilidad import anunciar, nombre_accesible
from bellbird.ui.busqueda_teclado import instalar_busqueda_tipo
from bellbird.ui.preferencias_comun import (
    CampoEstado, fila_horizontal, mostrar_control)
from bellbird.ui.restream_perfil import DialogoPerfilRestream
from bellbird.voice import sound_player as _snd


class VentanaRestream(wx.Dialog):

    def __init__(self, parent, cuenta, canales, ruta_perfiles,
                 al_conectar=None, al_reautorizar=None, al_desconectar=None):
        super().__init__(parent, title=_("Restream"), size=(640, 480),
                         name="DialogoRestream")
        self._cuenta = cuenta
        self._funcion_canales = canales
        self._ruta = ruta_perfiles
        self._al_conectar = al_conectar
        self._al_reautorizar = al_reautorizar
        self._al_desconectar = al_desconectar
        self._perfiles = []
        self._crear_ui()
        paleta.pintar_ventana(self)
        self.Centre()

    def _crear_ui(self):
        panel = wx.Panel(self, name="PanelRestream")
        vs = wx.BoxSizer(wx.VERTICAL)
        self.nb = wx.Notebook(panel, name="PestanasRestream")
        self._pagina_cuenta = self._crear_cuenta()
        self._pagina_perfiles = self._crear_perfiles()
        self.nb.AddPage(self._pagina_cuenta, _("Cuenta"))
        self.nb.AddPage(self._pagina_perfiles, _("Perfiles"))
        vs.Add(self.nb, 1, wx.EXPAND | wx.ALL, 10)

        self.btn_cerrar = wx.Button(
            panel, wx.ID_CANCEL, _("Cerrar"), name=_("Cerrar"))
        nombre_accesible(self.btn_cerrar, self.btn_cerrar.GetName())
        vs.Add(self.btn_cerrar, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        panel.SetSizer(vs)

        self.btn_cerrar.Bind(
            wx.EVT_BUTTON, lambda evento: self.EndModal(wx.ID_CANCEL))
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla_ventana)
        self._actualizar_cuenta()
        self._poblar()

    def _crear_cuenta(self):
        pagina = wx.Panel(self.nb, name="PaginaCuentaRestream")
        vs = wx.BoxSizer(wx.VERTICAL)
        self.txt_estado = CampoEstado(
            pagina, _("Estado de la cuenta"), lineas=2)
        nombre_accesible(self.txt_estado, _("Estado de la cuenta"))
        vs.Add(self.txt_estado, 0, wx.EXPAND | wx.ALL, 10)

        self.btn_conectar = wx.Button(
            pagina, label=_("&Conectar"), name=_("Conectar"))
        self.btn_reautorizar = wx.Button(
            pagina, label=_("&Volver a autorizar"),
            name=_("Volver a autorizar"))
        self.btn_desconectar = wx.Button(
            pagina, label=_("&Desconectar"), name=_("Desconectar"))
        for boton in (self.btn_conectar, self.btn_reautorizar,
                      self.btn_desconectar):
            nombre_accesible(boton, boton.GetName())
        self.btn_conectar.Bind(wx.EVT_BUTTON, lambda evento: self._conectar())
        self.btn_reautorizar.Bind(
            wx.EVT_BUTTON, lambda evento: self._reautorizar())
        self.btn_desconectar.Bind(
            wx.EVT_BUTTON, lambda evento: self._desconectar())
        vs.Add(fila_horizontal((self.btn_conectar, self.btn_reautorizar,
                                self.btn_desconectar)), 0, wx.ALL, 10)
        pagina.SetSizer(vs)
        return pagina

    def _crear_perfiles(self):
        pagina = wx.Panel(self.nb, name="PaginaPerfilesRestream")
        vs = wx.BoxSizer(wx.VERTICAL)
        self.lista_perfiles = wx.ListBox(
            pagina, style=wx.LB_SINGLE | wx.LB_HSCROLL,
            name=_("Perfiles de Restream"))
        nombre_accesible(self.lista_perfiles, _("Perfiles de Restream"))
        instalar_busqueda_tipo(
            self.lista_perfiles,
            lambda: [self.lista_perfiles.GetString(i) for i
                     in range(self.lista_perfiles.GetCount())])
        self.lista_perfiles.Bind(wx.EVT_KEY_DOWN, self._al_tecla)
        vs.Add(self.lista_perfiles, 1, wx.EXPAND | wx.ALL, 8)

        self.btn_nuevo = wx.Button(
            pagina, label=_("&Nuevo…"), name=_("Nuevo"))
        self.btn_editar = wx.Button(
            pagina, label=_("&Editar…"), name=_("Editar"))
        self.btn_duplicar = wx.Button(
            pagina, label=_("D&uplicar"), name=_("Duplicar"))
        self.btn_eliminar = wx.Button(
            pagina, label=_("E&liminar"), name=_("Eliminar"))
        for boton in (self.btn_nuevo, self.btn_editar, self.btn_duplicar,
                      self.btn_eliminar):
            nombre_accesible(boton, boton.GetName())
        self.btn_nuevo.Bind(wx.EVT_BUTTON, lambda evento: self._nuevo())
        self.btn_editar.Bind(wx.EVT_BUTTON, lambda evento: self._editar())
        self.btn_duplicar.Bind(wx.EVT_BUTTON, lambda evento: self._duplicar())
        self.btn_eliminar.Bind(wx.EVT_BUTTON, lambda evento: self._eliminar())
        vs.Add(fila_horizontal((self.btn_nuevo, self.btn_editar,
                                self.btn_duplicar, self.btn_eliminar)),
               0, wx.ALL, 10)
        pagina.SetSizer(vs)
        return pagina

    def _actualizar_cuenta(self):
        conectada = bool(self._cuenta.conectada())
        self.txt_estado.SetValue(
            _("Cuenta de Restream conectada.") if conectada
            else _("Sin cuenta de Restream conectada."))
        mostrar_control(self.btn_conectar, not conectada, self._pagina_cuenta)
        mostrar_control(self.btn_reautorizar, conectada, self._pagina_cuenta)
        mostrar_control(self.btn_desconectar, conectada, self._pagina_cuenta)
        self._pagina_cuenta.Layout()

    def _conectar(self):
        self._llamar(self._al_conectar)
        self._actualizar_cuenta()
        if self._cuenta.conectada():
            anunciar(_("Cuenta de Restream conectada."))

    def _reautorizar(self):
        self._llamar(self._al_reautorizar)
        self._actualizar_cuenta()
        if self._cuenta.conectada():
            anunciar(_("Cuenta de Restream conectada."))

    def _desconectar(self):
        self._llamar(self._al_desconectar)
        self._actualizar_cuenta()
        if not self._cuenta.conectada():
            anunciar(_("Cuenta de Restream desconectada."))

    @staticmethod
    def _llamar(funcion):
        if funcion is not None:
            funcion()

    def _canales(self):
        return list(self._funcion_canales())

    def _etiqueta(self, perfil):
        cantidad = len(perfil.canales)
        cuenta = ngettext("{n} canal", "{n} canales", cantidad).format(
            n=cantidad)
        return _("{nombre}, {orientacion}, {canales}").format(
            nombre=perfil.nombre, orientacion=_(perfil.orientacion),
            canales=cuenta)

    def _poblar(self, indice=None):
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

    def _nuevo(self):
        perfil = self._pedir_perfil(None, self._perfiles)
        if perfil is None:
            return
        self._perfiles.append(perfil)
        perfiles.guardar(self._ruta, self._perfiles)
        self._poblar(len(self._perfiles) - 1)
        anunciar(_("Perfil guardado."))

    def _editar(self):
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
        self._poblar(indice)
        anunciar(_("Perfil guardado."))

    def _duplicar(self):
        indice = self._indice_seleccionado()
        if indice is None:
            anunciar(_("Sin selección"))
            return
        actual = self._perfiles[indice]
        copia = replace(actual, nombre=self._nombre_copia(actual.nombre))
        self._perfiles.append(copia)
        perfiles.guardar(self._ruta, self._perfiles)
        self._poblar(len(self._perfiles) - 1)
        anunciar(_("Perfil duplicado."))

    def _eliminar(self):
        indice = self._indice_seleccionado()
        if indice is None:
            anunciar(_("Sin selección"))
            return
        del self._perfiles[indice]
        perfiles.guardar(self._ruta, self._perfiles)
        self._poblar(indice)
        anunciar(_("Perfil eliminado."))

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
            self, perfil, self._canales(), existentes)
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
            self._editar()
        elif tecla == wx.WXK_DELETE:
            self._eliminar()
        else:
            evento.Skip()

    def _al_tecla_ventana(self, evento):
        if evento.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        evento.Skip()


def abrir_restream(padre, cuenta, canales, ruta_perfiles, al_conectar=None,
                   al_reautorizar=None, al_desconectar=None):
    dialogo = VentanaRestream(padre, cuenta, canales, ruta_perfiles,
                              al_conectar, al_reautorizar, al_desconectar)
    try:
        dialogo.ShowModal()
    finally:
        dialogo.Destroy()
