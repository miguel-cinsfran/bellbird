"""Ventana pequeña para elegir a dónde transmitir.

Modal y chica como `DialogoDirectoYoutube`: lista «Transmitir a» con
los destinos de OBS, campo de usuario visible solo para TikTok y
botones Continuar y Cancelar. Pura salvo wx.
"""

from __future__ import annotations

import wx

from ytchat.obs.obs_destinos import DESTINOS
from ytchat.ui.gui import anunciar, nombre_accesible


def destino_inicial(destino_guardado) -> str:
    """Destino con el que arranca la lista: el guardado o el primero."""
    if destino_guardado in DESTINOS:
        return destino_guardado
    return DESTINOS[0]


def validar_eleccion(destino, usuario) -> tuple:
    """Valida lo elegido y devuelve (destino, usuario).

    Pura y sin ventanas: la usan el diálogo y las pruebas. Con TikTok
    y usuario vacío lanza ValueError con «Falta el usuario de TikTok.».
    Para YouTube el usuario no hace falta y se devuelve vacío.
    """
    from ytchat.capture import tiktok_vivo
    if destino not in DESTINOS:
        destino = DESTINOS[0]
    if destino == "TikTok":
        usuario = tiktok_vivo.usuario_tiktok(usuario or "")
        if not usuario:
            raise ValueError("Falta el usuario de TikTok.")
        return (destino, usuario)
    return (destino, "")


class DialogoElegirDestino(wx.Dialog):
    def __init__(self, padre, destino="", usuario=""):
        super().__init__(padre, title="Transmitir a",
                         name="DialogoElegirDestino")
        destino = destino_inicial(destino)
        self._datos = None

        vs = wx.BoxSizer(wx.VERTICAL)
        self.rotulo_destino = wx.StaticText(self, label="Transmitir a:")
        vs.Add(self.rotulo_destino, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.cho_destino = wx.Choice(
            self, choices=list(DESTINOS), name="Transmitir a")
        self.cho_destino.SetStringSelection(destino)
        nombre_accesible(self.cho_destino, "Transmitir a")
        vs.Add(self.cho_destino, 0, wx.EXPAND | wx.ALL, 10)

        self.rotulo_usuario = wx.StaticText(
            self, label="Usuario de TikTok:")
        vs.Add(self.rotulo_usuario, 0, wx.LEFT | wx.RIGHT, 10)
        self.txt_usuario = wx.TextCtrl(
            self, value=usuario or "", name="Usuario de TikTok")
        nombre_accesible(self.txt_usuario, "Usuario de TikTok")
        vs.Add(self.txt_usuario, 0, wx.EXPAND | wx.ALL, 10)

        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_continuar = wx.Button(self, wx.ID_OK, "&Continuar")
        self.btn_continuar.SetDefault()
        self.btn_cancelar = wx.Button(self, wx.ID_CANCEL, "C&ancelar")
        fila.Add(self.btn_continuar, 0, wx.RIGHT, 6)
        fila.Add(self.btn_cancelar, 0)
        vs.Add(fila, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        self.SetSizerAndFit(vs)
        self.cho_destino.Bind(wx.EVT_CHOICE, self._al_destino)
        self.btn_continuar.Bind(wx.EVT_BUTTON, self._al_continuar)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)
        self._mostrar_usuario()
        self.cho_destino.SetFocus()

    @property
    def datos(self):
        return self._datos

    def _mostrar_usuario(self):
        visible = self.cho_destino.GetStringSelection() == "TikTok"
        self.rotulo_usuario.Show(visible)
        self.txt_usuario.Show(visible)
        self.Layout()

    def _al_destino(self, _event):
        self._mostrar_usuario()

    def _al_continuar(self, _event) -> None:
        try:
            self._datos = validar_eleccion(
                self.cho_destino.GetStringSelection(),
                self.txt_usuario.GetValue())
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
