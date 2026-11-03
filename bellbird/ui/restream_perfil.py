"""Diálogo para crear o editar un perfil de Restream (accesible).

Pide el nombre, la orientación, los canales como casillas y lo que acepta
YouTube: título, descripción, privacidad y latencia. La validación es de
`perfiles.validar`; quien lo abrió guarda con `perfiles.guardar`.
"""

from __future__ import annotations

import wx

from bellbird.core.idioma import _, ngettext
from bellbird.restream import perfiles
from bellbird.restream.perfiles import ORIENTACIONES, Perfil
from bellbird.ui import paleta
from bellbird.ui.accesibilidad import anunciar, nombre_accesible
from bellbird.ui.gui import caja_de_grupo
from bellbird.ui.preferencias_comun import nombre_de_etiqueta
from bellbird.youtube.emision import (
    ETIQUETAS_LATENCIA,
    ETIQUETAS_PRIVACIDAD,
    LATENCIA_INICIAL,
    LATENCIAS,
    PRIVACIDAD_INICIAL,
    PRIVACIDADES,
)


def _rotulo(padre, contenido, texto, control):
    """Rótulo y control en el orden de creación, para el orden de Tab."""
    rotulo = wx.StaticText(padre, label=texto)
    control.SetName(nombre_de_etiqueta(texto))
    nombre_accesible(control, control.GetName())
    contenido.Add(rotulo, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
    contenido.Add(control, 0, wx.EXPAND | wx.ALL, 10)


class DialogoPerfilRestream(wx.Dialog):

    def __init__(self, parent, perfil=None, canales=None, existentes=None):
        titulo = (_("Nuevo perfil de Restream") if perfil is None
                  else _("Editar perfil de Restream"))
        super().__init__(parent, title=titulo, size=(560, 640),
                         name="DialogoPerfilRestream")
        self._perfil = perfil
        self._existentes = list(existentes or ())
        self._canales = list(canales or ())
        self._ids_validos = {identificador for identificador, _texto
                             in self._canales}
        self._resultado = None
        self._casillas = []
        self._nota_sobrantes = None
        self._crear_ui()
        paleta.pintar_ventana(self)
        self.Centre()

    def _crear_ui(self):
        vs = wx.BoxSizer(wx.VERTICAL)
        zona = wx.ScrolledWindow(self, style=wx.TAB_TRAVERSAL | wx.VSCROLL)
        zona.SetScrollRate(0, 20)
        contenido = wx.BoxSizer(wx.VERTICAL)
        self._agregar_nombre(zona, contenido)
        self._agregar_orientacion(zona, contenido)
        self._agregar_canales(zona, contenido)
        self._agregar_youtube(zona, contenido)
        zona.SetSizer(contenido)
        vs.Add(zona, 1, wx.EXPAND)

        fila = wx.BoxSizer(wx.HORIZONTAL)
        etiqueta_guardar = _("&Guardar")
        self.btn_guardar = wx.Button(
            self, wx.ID_OK, etiqueta_guardar,
            name=nombre_de_etiqueta(etiqueta_guardar))
        self.btn_cancelar = wx.Button(
            self, wx.ID_CANCEL, _("Cancelar"), name=_("Cancelar"))
        nombre_accesible(self.btn_guardar, self.btn_guardar.GetName())
        nombre_accesible(self.btn_cancelar, self.btn_cancelar.GetName())
        fila.Add(self.btn_guardar, 0, wx.RIGHT, 6)
        fila.Add(self.btn_cancelar, 0)
        vs.Add(fila, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        self.SetSizer(vs)
        self.btn_guardar.SetDefault()
        self.btn_guardar.Bind(wx.EVT_BUTTON, self._guardar)
        self.btn_cancelar.Bind(
            wx.EVT_BUTTON, lambda evento: self.EndModal(wx.ID_CANCEL))
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)

    def _agregar_nombre(self, zona, contenido):
        valor = self._perfil.nombre if self._perfil is not None else ""
        self.txt_nombre = wx.TextCtrl(zona, value=valor)
        _rotulo(zona, contenido, _("&Nombre:"), self.txt_nombre)

    def _agregar_orientacion(self, zona, contenido):
        self.cho_orientacion = wx.Choice(
            zona, choices=[_("Horizontal"), _("Vertical")])
        _rotulo(zona, contenido, _("&Orientación:"), self.cho_orientacion)
        orientacion = (self._perfil.orientacion if self._perfil is not None
                       else ORIENTACIONES[0])
        self.cho_orientacion.SetSelection(ORIENTACIONES.index(orientacion))

    def _agregar_canales(self, zona, contenido):
        sizer, padre = caja_de_grupo(zona, _("Canales"))
        self._caja_canales = sizer
        for identificador, texto in self._canales:
            casilla = wx.CheckBox(padre, label=texto.replace("&", "&&"),
                                  name=texto)
            nombre_accesible(casilla, texto)
            if (self._perfil is not None
                    and identificador in self._perfil.canales):
                casilla.SetValue(True)
            self._casillas.append((identificador, casilla))
            sizer.Add(casilla, 0, wx.ALL, 4)
        if not self._canales:
            sizer.Add(wx.StaticText(padre, label=_(
                "No hay canales. Conecta la cuenta de Restream y agrega los "
                "canales en su página.")), 0, wx.ALL, 4)
        contenido.Add(sizer, 0, wx.EXPAND | wx.ALL, 10)
        self._nota_sobrantes = self._crear_nota_sobrantes(zona, contenido)

    def _crear_nota_sobrantes(self, zona, contenido):
        if self._perfil is None:
            return None
        sobrantes = [identificador for identificador in self._perfil.canales
                     if identificador not in self._ids_validos]
        if not sobrantes:
            return None
        texto = ngettext(
            "Hay {n} canal del perfil que ya no está en Restream. Se eliminará "
            "al guardar.",
            "Hay {n} canales del perfil que ya no están en Restream. Se "
            "eliminarán al guardar.",
            len(sobrantes)).format(n=len(sobrantes))
        nota = wx.StaticText(zona, label=texto)
        contenido.Add(nota, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        return nota

    def _agregar_youtube(self, zona, contenido):
        perfil = self._perfil
        self.txt_titulo = wx.TextCtrl(
            zona, value=perfil.titulo if perfil is not None else "")
        _rotulo(zona, contenido, _("&Título:"), self.txt_titulo)

        self.txt_descripcion = wx.TextCtrl(
            zona, value=perfil.descripcion if perfil is not None else "",
            style=wx.TE_MULTILINE)
        self.txt_descripcion.SetMinSize(
            (-1, 3 * self.txt_descripcion.GetCharHeight() + 12))
        _rotulo(zona, contenido, _("&Descripción, opcional:"),
                self.txt_descripcion)

        self.cho_privacidad = wx.Choice(
            zona, choices=[_(ETIQUETAS_PRIVACIDAD[p]) for p in PRIVACIDADES])
        _rotulo(zona, contenido, _("&Privacidad en YouTube:"),
                self.cho_privacidad)
        privacidad = (perfil.privacidad if perfil is not None
                      else PRIVACIDAD_INICIAL)
        self.cho_privacidad.SetSelection(PRIVACIDADES.index(privacidad))

        self.cho_latencia = wx.Choice(
            zona, choices=[_(ETIQUETAS_LATENCIA[l]) for l in LATENCIAS])
        _rotulo(zona, contenido, _("&Latencia en YouTube:"), self.cho_latencia)
        latencia = perfil.latencia if perfil is not None else LATENCIA_INICIAL
        self.cho_latencia.SetSelection(LATENCIAS.index(latencia))

    def perfil(self):
        return self._resultado

    def _armar_perfil(self):
        elegidos = tuple(identificador for identificador, casilla
                         in self._casillas if casilla.GetValue())
        return Perfil(
            nombre=self.txt_nombre.GetValue().strip(),
            canales=elegidos,
            orientacion=ORIENTACIONES[self.cho_orientacion.GetSelection()],
            titulo=self.txt_titulo.GetValue(),
            descripcion=self.txt_descripcion.GetValue(),
            privacidad=PRIVACIDADES[self.cho_privacidad.GetSelection()],
            latencia=LATENCIAS[self.cho_latencia.GetSelection()],
        )

    def _guardar(self, _evento):
        perfil = self._armar_perfil()
        mensajes = perfiles.validar(perfil, self._existentes)
        if mensajes:
            anunciar(" ".join(mensajes))
            self._enfocar_primer_problema(perfil)
            return
        self._resultado = perfil
        self.EndModal(wx.ID_OK)

    def _enfocar_primer_problema(self, perfil):
        nombre = (perfil.nombre or "").strip().casefold()
        repetido = any(existente.nombre.strip().casefold() == nombre
                       for existente in self._existentes)
        if not nombre or nombre == "youtube" or repetido:
            self.txt_nombre.SetFocus()
        elif self._casillas:
            self._casillas[0][1].SetFocus()
        else:
            self.txt_nombre.SetFocus()

    def _al_tecla(self, evento):
        if evento.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        evento.Skip()
