"""Los filtros de la ventana de música: por artista y por orden.

Una clase con su propio estado que arma el botón, los rótulos y los dos
cuadros, los muestra u oculta y sabe qué temas quedan. No lee atributos
privados de la ventana: recibe los invocables que necesita.
"""

from __future__ import annotations

import wx

from ytchat.music import anuncios, filtros
from ytchat.ui.accesibilidad import anunciar, nombre_accesible
from ytchat.ui.tema import _T, _pintar

ANCHO_MOSTRAR = 210
ANCHO_ORDENAR = 190


class FiltrosMusica:
    """El botón «Mostrar los filtros» y los dos cuadros que pliega."""

    def __init__(self, parent, visibles=False, artista="",
                 orden=filtros.CRITERIO_COLECCION, al_cambiar=None,
                 programar_aviso=None, recordar=None, avisar=None):
        self.visibles = bool(visibles)
        self.artista = str(artista or "")
        self.orden = filtros.normalizar_criterio(orden)
        self._al_cambiar = al_cambiar
        self._programar_aviso = programar_aviso
        self._recordar = recordar
        self._avisar = avisar or anunciar
        self._opciones = ((filtros.TODAS, "Todas las canciones"),)
        self._crear(parent)
        self._poner_artistas()
        self._aplicar_visibilidad(avisar=False, enfocar=False)

    def _crear(self, parent):
        self.btn = wx.Button(parent, wx.ID_ANY, "Mostrar los &filtros",
                             name="Mostrar los filtros")
        _pintar(self.btn, _T.btn, _T.btn_t)
        self.lb_mostrar = wx.StaticText(parent, label="&Mostrar:")
        self.cb_mostrar = wx.Choice(parent, name="Mostrar")
        _pintar(self.cb_mostrar, _T.field, _T.text)
        nombre_accesible(self.cb_mostrar, "Mostrar")
        self.cb_mostrar.SetMinSize((ANCHO_MOSTRAR, -1))
        self.lb_ordenar = wx.StaticText(parent, label="Or&denar por:")
        self.cb_ordenar = wx.Choice(parent, name="Ordenar por")
        _pintar(self.cb_ordenar, _T.field, _T.text)
        nombre_accesible(self.cb_ordenar, "Ordenar por")
        self.cb_ordenar.SetMinSize((ANCHO_ORDENAR, -1))
        self.cb_ordenar.Set([etiqueta for _clave, etiqueta
                             in filtros.CRITERIOS])
        self.cb_ordenar.SetSelection(self._indice_orden())
        self.sizer = self._armar_sizer()
        self.btn.Bind(wx.EVT_BUTTON, lambda evento: self.alternar())
        self.cb_mostrar.Bind(wx.EVT_CHOICE, self._al_elegir_mostrar)
        self.cb_ordenar.Bind(wx.EVT_CHOICE, self._al_elegir_orden)

    def _armar_sizer(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.btn, 0)
        cuadros = wx.BoxSizer(wx.HORIZONTAL)
        cuadros.Add(self.lb_mostrar, 0,
                    wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        cuadros.Add(self.cb_mostrar, 0,
                    wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)
        cuadros.Add(self.lb_ordenar, 0,
                    wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        cuadros.Add(self.cb_ordenar, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(cuadros, 0, wx.TOP, 8)
        return sizer

    def aplicar(self, temas):
        """Los temas filtrados si los cuadros se ven; si no, tal cual."""
        if not self.visibles:
            return tuple(temas)
        return filtros.ordenar(
            filtros.filtrar_por_artista(temas, self.artista), self.orden)

    def refrescar_artistas(self, temas):
        """Rehace «Mostrar» con los artistas de la colección elegida.

        Si el artista que estaba elegido ya no está, queda «Todas las
        canciones».
        """
        self._opciones = filtros.opciones_artistas(temas)
        claves = [clave for clave, _etiqueta in self._opciones]
        if self.artista not in claves:
            self.artista = filtros.TODAS
        self._poner_artistas()

    def alternar(self):
        """Muestra u oculta los dos cuadros, reaplica y avisa lo que hizo."""
        self.visibles = not self.visibles
        if callable(self._al_cambiar):
            self._al_cambiar()
        self._aplicar_visibilidad()

    def _poner_artistas(self):
        self.cb_mostrar.Set([etiqueta for _clave, etiqueta
                             in self._opciones])
        self.cb_mostrar.SetSelection(self._indice_artista())

    def _indice_artista(self):
        for indice, (clave, _etiqueta) in enumerate(self._opciones):
            if clave == self.artista:
                return indice
        return 0

    def _indice_orden(self):
        for indice, (clave, _etiqueta) in enumerate(filtros.CRITERIOS):
            if clave == self.orden:
                return indice
        return 0

    def _aplicar_visibilidad(self, avisar=True, enfocar=True):
        for control in (self.lb_mostrar, self.cb_mostrar,
                        self.lb_ordenar, self.cb_ordenar):
            control.Show(self.visibles)
        self._rotular()
        self.btn.GetParent().Layout()
        if not avisar:
            return
        self._recordar_estado()
        if self.visibles:
            if enfocar:
                self.cb_mostrar.SetFocus()
            self._avisar(anuncios.TEXTO_FILTROS_VISIBLES)
        else:
            if enfocar:
                self.btn.SetFocus()
            self._avisar(anuncios.TEXTO_FILTROS_OCULTOS)

    def _rotular(self):
        if self.visibles:
            self.btn.SetLabel("Ocultar los &filtros")
            nombre_accesible(self.btn, "Ocultar los filtros")
        else:
            self.btn.SetLabel("Mostrar los &filtros")
            nombre_accesible(self.btn, "Mostrar los filtros")

    def _al_elegir_mostrar(self, evento):
        indice = self.cb_mostrar.GetSelection()
        if 0 <= indice < len(self._opciones):
            self.artista = self._opciones[indice][0]
        self._avisar_cambio()
        evento.Skip()

    def _al_elegir_orden(self, evento):
        indice = self.cb_ordenar.GetSelection()
        if 0 <= indice < len(filtros.CRITERIOS):
            self.orden = filtros.CRITERIOS[indice][0]
        self._avisar_cambio()
        evento.Skip()

    def _avisar_cambio(self):
        if callable(self._al_cambiar):
            self._al_cambiar()
        if callable(self._programar_aviso):
            self._programar_aviso()
        self._recordar_estado()

    def _recordar_estado(self):
        if callable(self._recordar):
            self._recordar(self.visibles, self.artista, self.orden)
