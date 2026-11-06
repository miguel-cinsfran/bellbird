"""Cuadros de propiedades de una fuente, para agregar y para Propiedades."""

from __future__ import annotations

import os

import wx

from guyrapu.core.idioma import _
from guyrapu.ui import agregar_camara, escena_captura_ventana, paleta
from guyrapu.ui.accesibilidad import anunciar, nombre_accesible
from guyrapu.ui.preferencias_comun import (
    boton, fila_campo, lista_con_nombre, nombre_de_etiqueta)

_COMODIN_IMAGEN = "*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.webp"
_COMODIN_MULTIMEDIA = (
    "*.mp4;*.mkv;*.mov;*.webm;*.avi;*.mp3;*.wav;*.ogg;*.flac;*.m4a")
_TAMANO_MINIMO = 8
_TAMANO_MAXIMO = 300
_TAMANO_INICIAL = 72


class DialogoBase(wx.Dialog):
    """Título, controles, Aceptar y Cancelar al final, Escape cancela."""

    def __init__(self, padre, titulo, nombre, aceptar="&Aceptar",
                 cancelar="&Cancelar"):
        super().__init__(padre, title=titulo, name=nombre)
        self._etiqueta_aceptar = aceptar
        self._etiqueta_cancelar = cancelar
        self._valores = None
        self.vertical = wx.BoxSizer(wx.VERTICAL)
        self._crear_controles()
        self._crear_botones()
        self.SetSizerAndFit(self.vertical)
        self._enlazar_eventos()
        paleta.pintar_ventana(self)
        self.Centre()
        self._enfocar()

    def _crear_controles(self):
        raise NotImplementedError

    def _leer(self):
        raise NotImplementedError

    def _enfocar(self):
        for hijo in self.GetChildren():
            if isinstance(hijo, (wx.Choice, wx.TextCtrl, wx.SpinCtrl)):
                hijo.SetFocus()
                return

    def _crear_botones(self):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_aceptar = boton(
            self, self._etiqueta_aceptar,
            nombre_de_etiqueta(self._etiqueta_aceptar), wx.ID_OK)
        self.btn_aceptar.SetDefault()
        self.btn_cancelar = boton(
            self, self._etiqueta_cancelar,
            nombre_de_etiqueta(self._etiqueta_cancelar), wx.ID_CANCEL)
        fila.Add(self.btn_aceptar, 0, wx.RIGHT, 8)
        fila.Add(self.btn_cancelar, 0)
        self.vertical.Add(fila, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

    def _enlazar_eventos(self):
        self.btn_aceptar.Bind(wx.EVT_BUTTON, self._al_aceptar)
        self.btn_cancelar.Bind(wx.EVT_BUTTON, self._al_cancelar)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)

    def valor(self):
        return self._valores

    def _al_aceptar(self, _event):
        valores = self._leer()
        if valores is None:
            return
        self._valores = valores
        self.EndModal(wx.ID_OK)

    def _al_cancelar(self, _event):
        self.EndModal(wx.ID_CANCEL)

    def _al_tecla(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        event.Skip()


class DialogoEleccion(DialogoBase):
    """Una lista con su rótulo y el mensaje que se muestra si está vacía."""

    def __init__(self, padre, titulo, nombre, etiqueta, opciones,
                 actual="", vacio="", aceptar="&Aceptar",
                 cancelar="&Cancelar"):
        self._etiqueta = etiqueta
        self._lista_valores = [valor for _texto, valor in opciones or ()]
        self._opciones = tuple(opciones or ())
        self._actual = actual
        self._vacio = vacio
        super().__init__(padre, titulo, nombre, aceptar, cancelar)

    def _crear_controles(self):
        self.rotulo = wx.StaticText(self, label=self._etiqueta)
        self.lista = lista_con_nombre(
            self, self._etiqueta,
            [texto for texto, _valor in self._opciones])
        if self._actual in self._lista_valores:
            self.lista.SetSelection(self._lista_valores.index(self._actual))
        elif self._lista_valores:
            self.lista.SetSelection(0)
        fila_campo(self.vertical, self.rotulo, self.lista)
        self.aviso_vacio = None
        if not self._opciones:
            self.aviso_vacio = wx.StaticText(self, label=self._vacio)
            self.vertical.Add(self.aviso_vacio, 0, wx.ALL, 6)

    def _enfocar(self):
        if self._opciones:
            self.lista.SetFocus()
        else:
            self.btn_cancelar.SetFocus()

    def _crear_botones(self):
        super()._crear_botones()
        if not self._opciones:
            self.btn_aceptar.Disable()

    def _leer(self):
        indice = self.lista.GetSelection()
        if (indice == wx.NOT_FOUND or indice < 0
                or indice >= len(self._lista_valores)):
            return None
        return self._lista_valores[indice]


class DialogoJuego(DialogoBase):
    """Modo de captura y, si es de una ventana, cuál."""

    def __init__(self, padre, ventanas, valores):
        self._ventanas = tuple(ventanas or ())
        self._valores_ventana = [valor for _texto, valor in self._ventanas]
        valores = valores or {}
        self._modo = valores.get("modo") or "any_fullscreen"
        self._ventana = valores.get("ventana") or ""
        super().__init__(padre, _("Captura de juego"), "DialogoJuego",
                         cancelar="Cancelar")

    def _crear_controles(self):
        self.rotulo_modo = wx.StaticText(self, label=_("&Capturar:"))
        self.cho_modo = lista_con_nombre(
            self, _("&Capturar:"), [_("Cualquier juego a pantalla completa"),
                                    _("Una ventana")])
        self.cho_modo.SetSelection(1 if self._modo == "window" else 0)
        fila_campo(self.vertical, self.rotulo_modo, self.cho_modo)
        self.rotulo_ventana = wx.StaticText(self, label=_("&Ventana:"))
        self.cho_ventana = lista_con_nombre(
            self, _("&Ventana:"),
            [texto for texto, _valor in self._ventanas])
        if self._ventana in self._valores_ventana:
            self.cho_ventana.SetSelection(
                self._valores_ventana.index(self._ventana))
        elif self._valores_ventana:
            self.cho_ventana.SetSelection(0)
        self.fila_ventana = fila_campo(
            self.vertical, self.rotulo_ventana, self.cho_ventana)
        self.aviso_vacio = wx.StaticText(
            self, label=_("No hay ventanas para capturar."))
        self.vertical.Add(self.aviso_vacio, 0, wx.ALL, 6)
        self._mostrar_ventana(self._modo == "window")

    def _enfocar(self):
        self.cho_modo.SetFocus()

    def _mostrar_ventana(self, mostrar):
        self.rotulo_ventana.Show(mostrar)
        self.cho_ventana.Show(mostrar)
        self.fila_ventana.ShowItems(mostrar)
        vacia = mostrar and not self._ventanas
        self.aviso_vacio.Show(bool(vacia))
        if hasattr(self, "btn_aceptar"):
            self.btn_aceptar.Enable(not vacia)
        if not mostrar and self.cho_ventana.HasFocus():
            self.cho_modo.SetFocus()
        self.Layout()

    def _crear_botones(self):
        super()._crear_botones()
        self._mostrar_ventana(self.cho_modo.GetSelection() == 1)

    def _enlazar_eventos(self):
        super()._enlazar_eventos()
        self.cho_modo.Bind(wx.EVT_CHOICE, self._al_cambiar_modo)

    def _al_cambiar_modo(self, _event):
        self._mostrar_ventana(self.cho_modo.GetSelection() == 1)

    def _leer(self):
        if self.cho_modo.GetSelection() != 1:
            return {"modo": "any_fullscreen", "ventana": ""}
        indice = self.cho_ventana.GetSelection()
        if (indice == wx.NOT_FOUND or indice < 0
                or indice >= len(self._valores_ventana)):
            anunciar(_("Elige primero una ventana en Ventana."))
            return None
        return {"modo": "window", "ventana": self._valores_ventana[indice]}


class DialogoArchivo(DialogoBase):
    """Un archivo con Examinar y, para multimedia, si se repite."""

    def __init__(self, padre, clave, valores):
        self._clave = clave
        self._archivo = (valores or {}).get("archivo", "")
        self._repetir = bool((valores or {}).get("repetir", False))
        super().__init__(padre, _("Archivo multimedia") if clave == "multimedia"
                         else _("Imagen"), "DialogoArchivo",
                         aceptar="Aceptar", cancelar="Cancelar")

    def _crear_controles(self):
        self.rotulo_archivo = wx.StaticText(self, label=_("&Archivo:"))
        self.txt_archivo = wx.TextCtrl(
            self, value=self._archivo,
            name=nombre_de_etiqueta(_("&Archivo:")))
        nombre_accesible(self.txt_archivo, self.txt_archivo.GetName())
        self.btn_examinar = boton(
            self, _("&Examinar…"), nombre_de_etiqueta(_("&Examinar…")))
        fila_campo(self.vertical, self.rotulo_archivo, self.txt_archivo,
                   boton=self.btn_examinar)
        self.chk_repetir = None
        if self._clave == "multimedia":
            self.chk_repetir = wx.CheckBox(
                self, label=_("&Repetir"),
                name=nombre_de_etiqueta(_("&Repetir")))
            self.chk_repetir.SetValue(self._repetir)
            self.vertical.Add(self.chk_repetir, 0, wx.ALL, 10)

    def _enfocar(self):
        self.txt_archivo.SetFocus()

    def _enlazar_eventos(self):
        super()._enlazar_eventos()
        self.btn_examinar.Bind(wx.EVT_BUTTON, self._al_examinar)

    def _al_examinar(self, _event):
        comodin = (_COMODIN_MULTIMEDIA if self._clave == "multimedia"
                   else _COMODIN_IMAGEN)
        with wx.FileDialog(
                self, _("Elegir archivo"),
                wildcard=_("Archivos") + "|" + comodin,
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialogo:
            if dialogo.ShowModal() == wx.ID_OK:
                self.txt_archivo.SetValue(dialogo.GetPath())

    def _leer(self):
        archivo = self.txt_archivo.GetValue().strip()
        if not archivo or not os.path.isfile(archivo):
            anunciar(_("Elige un archivo que exista."))
            return None
        if self._clave == "multimedia":
            return {"archivo": archivo,
                    "repetir": bool(self.chk_repetir.GetValue())}
        return {"archivo": archivo}


class DialogoTexto(DialogoBase):
    """El texto y el tamaño de letra."""

    def __init__(self, padre, valores):
        valores = valores or {}
        self._texto = valores.get("texto", "")
        self._tamano = int(valores.get("tamano", _TAMANO_INICIAL))
        super().__init__(padre, _("Texto"), "DialogoTexto")

    def _crear_controles(self):
        self.rotulo_texto = wx.StaticText(self, label=_("&Texto:"))
        self.txt_texto = wx.TextCtrl(
            self, value=self._texto,
            name=nombre_de_etiqueta(_("&Texto:")))
        nombre_accesible(self.txt_texto, self.txt_texto.GetName())
        fila_campo(self.vertical, self.rotulo_texto, self.txt_texto)
        self.rotulo_tamano = wx.StaticText(
            self, label=_("Tamaño de letra:"))
        self.spin_tamano = wx.SpinCtrl(
            self, min=_TAMANO_MINIMO, max=_TAMANO_MAXIMO,
            initial=self._tamano,
            name=nombre_de_etiqueta(_("Tamaño de letra:")))
        nombre_accesible(self.spin_tamano, self.spin_tamano.GetName())
        fila_campo(self.vertical, self.rotulo_tamano, self.spin_tamano)

    def _enfocar(self):
        self.txt_texto.SetFocus()

    def _leer(self):
        return {"texto": self.txt_texto.GetValue(),
                "tamano": int(self.spin_tamano.GetValue())}


def pedir(padre, clave, opciones=None, valores=None):
    """Abre el cuadro del tipo y devuelve sus valores, o None si se cancela."""
    valores = valores or {}
    if clave == "pantalla":
        return _eleccion(
            padre, "&Pantalla:", _("Captura de pantalla"), "DialogoPantalla",
            opciones, valores.get("pantalla", ""),
            _("No hay pantallas para capturar."), "pantalla")
    if clave == "juego":
        return _con_valor(DialogoJuego(padre, opciones, valores))
    if clave in ("imagen", "multimedia"):
        return _con_valor(DialogoArchivo(padre, clave, valores))
    if clave == "texto":
        return _con_valor(DialogoTexto(padre, valores))
    if clave == "camara":
        valor = agregar_camara.pedir_camara(
            padre, opciones, valores.get("dispositivo", ""))
        return None if valor is None else {"dispositivo": valor}
    if clave == "ventana":
        valor = escena_captura_ventana.pedir_valor(
            padre, opciones, valores.get("ventana", ""))
        return None if valor is None else {"ventana": valor}
    return None


def pedir_fuente(padre, opciones):
    """Elige una fuente de otra escena por su nombre."""
    dialogo = DialogoEleccion(
        padre, _("Fuente de otra escena"), "DialogoFuente",
        _("&Fuente:"), tuple((nombre, nombre) for nombre in opciones or ()),
        vacio=_("No hay fuentes de otras escenas para agregar."))
    return _con_valor(dialogo)


def _eleccion(padre, etiqueta, titulo, nombre, opciones, actual, vacio,
              clave):
    dialogo = DialogoEleccion(
        padre, titulo, nombre, etiqueta, opciones, actual, vacio)
    elegido = _con_valor(dialogo)
    return None if elegido is None else {clave: elegido}


def _con_valor(dialogo):
    try:
        aceptado = dialogo.ShowModal() == wx.ID_OK
        return dialogo.valor() if aceptado else None
    finally:
        dialogo.Destroy()
