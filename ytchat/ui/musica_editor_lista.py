"""Editor de listas de música: el nombre y los temas con casillas.

Editar y crear comparten un solo cuadro. Las filas y el orden al guardar son
funciones puras, para poder comprobarlos sin abrir ventanas. La lista de
temas es un `wx.ListCtrl` nativo con casillas: en Windows NVDA anuncia si
cada fila está marcada o no.
"""

from __future__ import annotations

import wx

from ytchat.music import listas, vista
from ytchat.ui.gui import _T, _pintar, anunciar, nombre_accesible

MAX_NOMBRE = 60
TITULO_NUEVA = "Nueva lista"
TITULO_EDITAR = "Editar lista"
TEXTO_NOMBRE_LARGO = "El nombre no puede tener más de 60 caracteres"


def validar_nombre(nombre):
    """El nombre limpio; levanta `ErrorListas` con el motivo si no sirve."""
    limpio = listas.validar_nombre(nombre)
    if len(limpio) > MAX_NOMBRE:
        raise listas.ErrorListas(TEXTO_NOMBRE_LARGO)
    return limpio


def filas_editor(temas_carpeta=(), temas_lista=()):
    """Las filas del editor y si van marcadas.

    Primero van los temas de la lista que no están en la carpeta, porque son
    los que se perderían si el editor solo mostrara la carpeta.
    """
    carpeta = tuple(temas_carpeta or ())
    lista = tuple(temas_lista or ())
    origenes_carpeta = {tema.origen for tema in carpeta}
    marcados = {tema.origen for tema in lista}
    vistos = set()
    filas = []
    for tema in lista:
        if tema.origen in origenes_carpeta or tema.origen in vistos:
            continue
        vistos.add(tema.origen)
        filas.append((tema, True))
    for tema in carpeta:
        if tema.origen in vistos:
            continue
        vistos.add(tema.origen)
        filas.append((tema, tema.origen in marcados))
    return filas


def temas_a_guardar(temas_lista=(), temas_carpeta=(), marcados=()):
    """Los temas marcados: primero los de la lista y después los nuevos."""
    marcados = set(marcados or ())
    salida = []
    vistos = set()
    for tema in temas_lista or ():
        if tema.origen in marcados:
            salida.append(tema)
        vistos.add(tema.origen)
    for tema in temas_carpeta or ():
        if tema.origen in marcados and tema.origen not in vistos:
            salida.append(tema)
            vistos.add(tema.origen)
    return tuple(salida)


class DialogoEditorLista(wx.Dialog):
    """El nombre de una lista y todos sus temas con casillas."""

    def __init__(self, parent, nombre="", temas_carpeta=(),
                 temas_lista=()):
        super().__init__(
            parent, title=TITULO_EDITAR if nombre else TITULO_NUEVA,
            name="EditorLista")
        self._temas_carpeta = tuple(temas_carpeta or ())
        self._temas_lista = tuple(temas_lista or ())
        self._marcados = {tema.origen for tema in self._temas_lista}
        self._filas = []
        self._visibles = []
        self._nombre = None
        self._crear_controles()
        if nombre:
            self.txt_nombre.SetValue(nombre)
        self._cargar_filas()
        self.Bind(wx.EVT_CHAR_HOOK, self._tecla)
        self.Fit()
        self.Centre()
        (self.lb_temas if nombre else self.txt_nombre).SetFocus()

    def _crear_controles(self):
        self._panel = panel = wx.Panel(self, name="PanelEditorLista")
        panel.SetBackgroundColour(_T.bg)
        panel.SetForegroundColour(_T.text)
        vs = wx.BoxSizer(wx.VERTICAL)
        vs.Add(wx.StaticText(panel, label="&Nombre:"), 0, wx.ALL, 12)
        self.txt_nombre = self._campo(
            panel, "Nombre de la lista", MAX_NOMBRE)
        vs.Add(self.txt_nombre, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
               12)
        vs.Add(wx.StaticText(panel, label="&Buscar:"), 0, wx.ALL, 12)
        self.txt_buscar = self._campo(panel, "Buscar canciones")
        vs.Add(self.txt_buscar, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
               12)
        vs.Add(wx.StaticText(panel, label="C&anciones:"), 0, wx.ALL, 12)
        self.lb_temas = wx.ListCtrl(
            panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
            name="Canciones de la lista")
        _pintar(self.lb_temas, _T.field, _T.text)
        nombre_accesible(self.lb_temas, "Canciones de la lista")
        self.lb_temas.InsertColumn(0, "Canción", width=420)
        self.lb_temas.EnableCheckBoxes(True)
        self.lb_temas.SetMinSize((460, 300))
        vs.Add(self.lb_temas, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)
        vs.Add(self._crear_botones(panel), 0, wx.ALL, 12)
        panel.SetSizer(vs)
        contenedor = wx.BoxSizer(wx.VERTICAL)
        contenedor.Add(panel, 1, wx.EXPAND)
        self.SetSizer(contenedor)
        self.txt_buscar.Bind(wx.EVT_TEXT, lambda _evento: self._aplicar_filtro())

    def _campo(self, panel, nombre, largo=None):
        campo = wx.TextCtrl(panel, name=nombre)
        if largo is not None:
            campo.SetMaxLength(largo)
        _pintar(campo, _T.field, _T.text)
        nombre_accesible(campo, nombre)
        return campo

    def _crear_botones(self, panel):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_guardar = wx.Button(panel, wx.ID_OK, "&Guardar",
                                     name="Guardar")
        self.btn_cancelar = wx.Button(panel, wx.ID_CANCEL, "Cancelar",
                                      name="Cancelar")
        for boton in (self.btn_guardar, self.btn_cancelar):
            _pintar(boton, _T.btn, _T.btn_t)
            fila.Add(boton, 0, wx.RIGHT, 8)
        self.btn_guardar.SetDefault()
        self.btn_guardar.Bind(wx.EVT_BUTTON, self._guardar)
        self.btn_cancelar.Bind(
            wx.EVT_BUTTON, lambda _evento: self.EndModal(wx.ID_CANCEL))
        return fila

    def _cargar_filas(self):
        self._filas = filas_editor(self._temas_carpeta, self._temas_lista)
        self._aplicar_filtro()

    def _sincronizar_marcas(self):
        for indice, tema in enumerate(self._visibles):
            if self.lb_temas.IsItemChecked(indice):
                self._marcados.add(tema.origen)
            else:
                self._marcados.discard(tema.origen)

    def _aplicar_filtro(self):
        if not self._filas and not self._visibles:
            return
        self._sincronizar_marcas()
        todos = [tema for tema, _marcado in self._filas]
        self._visibles = list(vista.filtrar_lista(
            todos, self.txt_buscar.GetValue()))
        self.lb_temas.DeleteAllItems()
        for tema in self._visibles:
            indice = self.lb_temas.InsertItem(
                self.lb_temas.GetItemCount(), vista.fila_tema(tema))
            self.lb_temas.CheckItem(indice, tema.origen in self._marcados)

    def _temas_marcados(self):
        self._sincronizar_marcas()
        return temas_a_guardar(
            self._temas_lista, self._temas_carpeta, self._marcados)

    def _guardar(self, _evento=None):
        try:
            self._nombre = validar_nombre(self.txt_nombre.GetValue())
        except listas.ErrorListas as exc:
            anunciar(str(exc))
            self.txt_nombre.SetFocus()
            self.txt_nombre.SelectAll()
            return
        self.EndModal(wx.ID_OK)

    def datos(self):
        """El nombre limpio y los temas marcados, en el orden al guardar."""
        if self._nombre is None:
            self._nombre = validar_nombre(self.txt_nombre.GetValue())
        return self._nombre, self._temas_marcados()

    def _tecla(self, evento):
        if evento.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        evento.Skip()


def pedir_lista(parent, nombre="", temas_carpeta=(), temas_lista=()):
    """Abre el editor y devuelve (nombre, temas), o None si se cancela."""
    with DialogoEditorLista(
            parent, nombre, temas_carpeta, temas_lista) as dialogo:
        if dialogo.ShowModal() != wx.ID_OK:
            return None
        return dialogo.datos()
