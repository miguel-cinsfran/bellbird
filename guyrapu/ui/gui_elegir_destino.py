"""Ventana pequeña para elegir a dónde transmitir.

Modal y chica como `DialogoDirectoYoutube`: lista «Transmitir a» con
los destinos de OBS, campo de usuario visible solo para TikTok y
botones Continuar y Cancelar. Pura salvo wx.
"""

from __future__ import annotations

import wx

from guyrapu.core import paths
from guyrapu.obs.obs_destinos import DESTINOS
from guyrapu.core.idioma import _
from guyrapu.restream import perfiles as perfiles_restream
from guyrapu.restream import transmitir
from guyrapu.ui import paleta
from guyrapu.ui.accesibilidad import anunciar, nombre_accesible


def _perfiles_guardados():
    return perfiles_restream.cargar(paths.perfiles_restream())


def destino_inicial(destino_guardado, opciones=None) -> str:
    """Destino con el que arranca la lista: el guardado o el primero."""
    opciones = tuple(opciones or DESTINOS)
    if destino_guardado in opciones:
        return destino_guardado
    return opciones[0]


def _opcion_elegida(seleccion, opciones) -> str:
    if seleccion is None or seleccion < 0 or seleccion >= len(opciones):
        return ""
    return opciones[seleccion]


def validar_eleccion(destino, usuario, opciones=None) -> tuple:
    """Valida lo elegido y devuelve (destino, usuario).

    Pura y sin ventanas: la usan el diálogo y las pruebas. Con TikTok
    y usuario vacío lanza ValueError con «Falta el usuario de TikTok.».
    Para YouTube y los perfiles de Restream el usuario no hace falta y se
    devuelve vacío.
    """
    from guyrapu.capture import tiktok_vivo
    opciones = tuple(opciones or DESTINOS)
    if destino not in opciones:
        destino = opciones[0]
    if destino == "TikTok":
        usuario = tiktok_vivo.usuario_tiktok(usuario or "")
        if not usuario:
            raise ValueError(_("Falta el usuario de TikTok."))
        return (destino, usuario)
    return (destino, "")


class DialogoElegirDestino(wx.Dialog):
    def __init__(self, padre, destino="", usuario="", perfiles=None):
        super().__init__(padre, title=_("Transmitir a"),
                         name="DialogoElegirDestino")
        perfiles = (_perfiles_guardados() if perfiles is None
                    else list(perfiles))
        self._opciones = transmitir.opciones(perfiles)
        destino = destino_inicial(destino, self._opciones)
        self._datos = None

        vs = wx.BoxSizer(wx.VERTICAL)
        self._crear_destino(vs, destino)
        self._crear_usuario(vs, usuario)
        self._crear_botones(vs)

        self.SetSizerAndFit(vs)
        self.cho_destino.Bind(wx.EVT_CHOICE, self._al_destino)
        self.btn_continuar.Bind(wx.EVT_BUTTON, self._al_continuar)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)
        self._mostrar_usuario()
        self.cho_destino.SetFocus()

    def _crear_destino(self, vs, destino):
        self.rotulo_destino = wx.StaticText(self, label=_("Transmitir a:"))
        vs.Add(self.rotulo_destino, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.cho_destino = wx.Choice(
            self, choices=[transmitir.texto(opcion)
                           for opcion in self._opciones],
            name=_("Transmitir a"))
        self.cho_destino.SetSelection(self._opciones.index(destino))
        nombre_accesible(self.cho_destino, _("Transmitir a"))
        vs.Add(self.cho_destino, 0, wx.EXPAND | wx.ALL, 10)

    def _crear_usuario(self, vs, usuario):
        self.rotulo_usuario = wx.StaticText(
            self, label=_("Usuario de TikTok:"))
        vs.Add(self.rotulo_usuario, 0, wx.LEFT | wx.RIGHT, 10)
        self.txt_usuario = wx.TextCtrl(
            self, value=usuario or "", name=_("Usuario de TikTok"))
        nombre_accesible(self.txt_usuario, _("Usuario de TikTok"))
        vs.Add(self.txt_usuario, 0, wx.EXPAND | wx.ALL, 10)

    def _crear_botones(self, vs):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        # Traductores: botón para seguir con la transmisión.
        self.btn_continuar = wx.Button(self, wx.ID_OK, _("&Continuar"))
        self.btn_continuar.SetDefault()
        # Traductores: botón para volver sin transmitir.
        self.btn_cancelar = wx.Button(self, wx.ID_CANCEL, _("C&ancelar"))
        fila.Add(self.btn_continuar, 0, wx.RIGHT, 6)
        fila.Add(self.btn_cancelar, 0)
        vs.Add(fila, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

    @property
    def datos(self):
        return self._datos

    def _opcion_elegida(self):
        return _opcion_elegida(self.cho_destino.GetSelection(),
                               self._opciones)

    def _mostrar_usuario(self):
        visible = self._opcion_elegida() == "TikTok"
        self.rotulo_usuario.Show(visible)
        self.txt_usuario.Show(visible)
        self.Layout()
        paleta.pintar_ventana(self)

    def _al_destino(self, _event):
        self._mostrar_usuario()

    def _al_continuar(self, _event) -> None:
        try:
            self._datos = validar_eleccion(
                self._opcion_elegida(),
                self.txt_usuario.GetValue(),
                self._opciones)
        except ValueError as exc:
            anunciar(str(exc))
            self.txt_usuario.Show()
            self.rotulo_usuario.Show()
            self.Layout()
            self.txt_usuario.SetFocus()
            return
        self.EndModal(wx.ID_OK)

    def _al_tecla(self, event) -> None:
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        event.Skip()


def pedir_destino(padre, destino_guardado, usuario_guardado):
    """Pide el destino y el usuario. Tupla (destino, usuario) o None."""
    dialogo = DialogoElegirDestino(padre, destino_guardado, usuario_guardado)
    try:
        if dialogo.ShowModal() == wx.ID_OK:
            return dialogo.datos
        return None
    finally:
        dialogo.Destroy()
