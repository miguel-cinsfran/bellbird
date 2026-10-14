"""Ventana para pedir los datos del directo de YouTube antes de transmitir.

Modal pequeña como `DialogoRedactar`: título, descripción opcional y
privacidad, que se recuerdan para la próxima vez. Pura salvo wx.
"""

from __future__ import annotations

from datetime import datetime

import wx

from ytchat.ui.gui import anunciar, nombre_accesible
from ytchat.youtube.emision import (
    ETIQUETAS_PRIVACIDAD,
    PRIVACIDAD_INICIAL,
    PRIVACIDADES,
    EmisionError,
    titulo_por_defecto,
)


def resultado_directo(titulo, descripcion, privacidad) -> dict:
    """Valida los valores de la ventana y arma el dict del directo.

    Pura y sin ventanas: la usan el diálogo y las pruebas. El título
    vacío anuncia «Falta el título del directo.» vía excepción, igual
    que `cuerpo_emision`.
    """
    titulo = (titulo or "").strip()
    if not titulo:
        raise EmisionError("Falta el título del directo.")
    if privacidad not in PRIVACIDADES:
        privacidad = PRIVACIDAD_INICIAL
    return {"titulo": titulo[:100], "descripcion": descripcion or "",
            "privacidad": privacidad}


class DialogoDirectoYoutube(wx.Dialog):
    def __init__(self, padre, titulo="", descripcion="",
                 privacidad=PRIVACIDAD_INICIAL):
        super().__init__(padre, title="Directo de YouTube",
                         name="DialogoDirectoYoutube")
        if privacidad not in PRIVACIDADES:
            privacidad = PRIVACIDAD_INICIAL
        if not (titulo or "").strip():
            titulo = titulo_por_defecto(datetime.now())
        self._datos = None

        vs = wx.BoxSizer(wx.VERTICAL)
        rotulo_titulo = wx.StaticText(self, label="Título:")
        vs.Add(rotulo_titulo, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.txt_titulo = wx.TextCtrl(
            self, value=titulo, name="Título del directo")
        self.txt_titulo.SetMaxLength(100)
        self.txt_titulo.SelectAll()
        nombre_accesible(self.txt_titulo, "Título del directo")
        vs.Add(self.txt_titulo, 0, wx.EXPAND | wx.ALL, 10)

        rotulo_descripcion = wx.StaticText(
            self, label="Descripción, opcional:")
        vs.Add(rotulo_descripcion, 0, wx.LEFT | wx.RIGHT, 10)
        self.txt_descripcion = wx.TextCtrl(
            self, value=descripcion or "", style=wx.TE_MULTILINE,
            name="Descripción del directo")
        self.txt_descripcion.SetMinSize(
            (-1, 3 * self.txt_descripcion.GetCharHeight() + 12))
        nombre_accesible(self.txt_descripcion, "Descripción del directo")
        vs.Add(self.txt_descripcion, 1, wx.EXPAND | wx.ALL, 10)

        rotulo_privacidad = wx.StaticText(self, label="Privacidad:")
        vs.Add(rotulo_privacidad, 0, wx.LEFT | wx.RIGHT, 10)
        self.cho_privacidad = wx.Choice(
            self, choices=[ETIQUETAS_PRIVACIDAD[p] for p in PRIVACIDADES],
            name="Privacidad")
        self.cho_privacidad.SetSelection(PRIVACIDADES.index(privacidad))
        nombre_accesible(self.cho_privacidad, "Privacidad")
        vs.Add(self.cho_privacidad, 0, wx.EXPAND | wx.ALL, 10)

        fila = wx.BoxSizer(wx.HORIZONTAL)
        # Cancelar lleva la letra en la «a» para no repetir la C de Crear.
        self.btn_crear = wx.Button(self, wx.ID_OK, "&Crear directo")
        self.btn_crear.SetDefault()
        self.btn_cancelar = wx.Button(self, wx.ID_CANCEL, "C&ancelar")
        fila.Add(self.btn_crear, 0, wx.RIGHT, 6)
        fila.Add(self.btn_cancelar, 0)
        vs.Add(fila, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        self.SetSizerAndFit(vs)
        self.btn_crear.Bind(wx.EVT_BUTTON, self._al_crear)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)
        self.txt_titulo.SetFocus()

    @property
    def datos(self):
        return self._datos

    def _privacidad_elegida(self) -> str:
        return PRIVACIDADES[self.cho_privacidad.GetSelection()]

    def _al_crear(self, _event) -> None:
        try:
            self._datos = resultado_directo(
                self.txt_titulo.GetValue(),
                self.txt_descripcion.GetValue(),
                self._privacidad_elegida())
        except EmisionError as exc:
            anunciar(str(exc))
            self.txt_titulo.SetFocus()
            return
        self.EndModal(wx.ID_OK)

    def _al_tecla(self, event) -> None:
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        event.Skip()


def pedir_datos_directo(padre, titulo="", descripcion="",
                        privacidad=PRIVACIDAD_INICIAL):
    """Pide título, descripción y privacidad. Dict o None si se cancela."""
    dialogo = DialogoDirectoYoutube(padre, titulo, descripcion, privacidad)
    try:
        if dialogo.ShowModal() == wx.ID_OK:
            return dialogo.datos
        return None
    finally:
        dialogo.Destroy()
