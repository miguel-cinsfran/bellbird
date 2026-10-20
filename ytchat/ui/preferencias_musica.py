"""Página Música del diálogo de Preferencias.

Mezcla sin estado propio: `gui_preferencias` hereda de acá. Se separó
porque ese módulo no puede crecer y la página necesitaba una casilla más.
"""

from __future__ import annotations

import wx

from ytchat.core import diagnostico, musica_decir
from ytchat.core import config as cfg
from ytchat.ui import opciones_musica
from ytchat.ui.gui import ContadorAccesible, anunciar, nombre_accesible
from ytchat.ui.gui_descargas import nombrar_selector_carpeta


# Filas de música de `_OPCIONES_SIMPLES` en `gui_preferencias`: misma tabla, mismo orden.
OPCIONES_MUSICA = (
    ("chk_musica_aleatorio", "musica", "aleatorio", "musica_aleatorio", bool, False),
    ("chk_musica_repetir", "musica", "repetir", "musica_repetir", str, "no"),
    ("chk_musica_retomar", "musica", "retomar", "musica_retomar", bool, True),
    ("chk_musica_sonido_tema", "musica", "sonido_tema", "musica_sonido_tema", bool, True),
    ("cho_musica_decir", "musica", "decir", "musica_decir", str, "titulo"),
    ("chk_musica_decir_pausa", "musica", "decir_pausa", "musica_decir_pausa", bool, True),
    ("sp_musica_volumen", "musica", "volumen", "musica_volumen", int, 50),
    ("chk_musica_normalizar", "musica", "normalizar", "musica_normalizar", bool, True),
    ("chk_musica_atajos_globales", "musica", "atajos_globales", "musica_atajos_globales", bool, False),
)


class PaginaMusica:
    """Página Música: carpeta, orden, repetición, aviso, volumen, igualación y salida."""

    def _pag_musica(self, parent):
        p = self._make_panel(parent, "PagMusica")
        vs = wx.BoxSizer(wx.VERTICAL)
        self._musica_carpeta(p, vs)
        self._musica_orden(p, vs)
        self._musica_anuncios(p, vs)
        self._musica_audio(p, vs)
        self._musica_atajos(p, vs)
        p.SetSizer(vs)
        return p

    def _musica_carpeta(self, p, vs):
        vs.Add(self._fila_label(p, "Carpeta de &música:"),
               0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        carpeta = str(self._config.get("musica_carpeta", "") or "")
        self.dir_musica_carpeta = wx.DirPickerCtrl(
            p, path=carpeta, name="Carpeta de música",
            message="Elige la carpeta de música")
        nombrar_selector_carpeta(self.dir_musica_carpeta)
        # La función nombra el campo para las descargas; acá el campo es la
        # carpeta de música.
        if hasattr(self.dir_musica_carpeta, "GetTextCtrl"):
            nombre_accesible(self.dir_musica_carpeta.GetTextCtrl(),
                             "Carpeta de música")
        vs.Add(self.dir_musica_carpeta, 0,
               wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _musica_orden(self, p, vs):
        # Definidos en gui_preferencias: se importan acá para evitar un import circular.
        from ytchat.ui.gui_preferencias import _T, _tc, EleccionTexto
        self.chk_musica_aleatorio = wx.CheckBox(
            p, label="Reproducir en orden &aleatorio",
            name="MusicaAleatorio")
        self.chk_musica_aleatorio.SetForegroundColour(_T.text)
        vs.Add(self.chk_musica_aleatorio, 0, wx.ALL, 10)

        vs.Add(self._fila_label(p, "&Repetir:"), 0, wx.LEFT | wx.RIGHT, 10)
        self.chk_musica_repetir = EleccionTexto(
            p, (("no", "No"), ("todo", "Toda la cola"),
                 ("tema", "Esta canción")),
            normalizar=cfg.normalizar_repetir, name="Repetir la música")
        _tc(self.chk_musica_repetir)
        vs.Add(self.chk_musica_repetir, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_musica_retomar = wx.CheckBox(
            p, label="Recordar la ú&ltima lista al abrir",
            name="MusicaRetomar")
        self.chk_musica_retomar.SetForegroundColour(_T.text)
        vs.Add(self.chk_musica_retomar, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _musica_anuncios(self, p, vs):
        from ytchat.ui.gui_preferencias import _T, _tc, EleccionTexto
        self.chk_musica_sonido_tema = wx.CheckBox(
            p, label="&Sonido al pasar de canción",
            name="MusicaSonidoTema")
        self.chk_musica_sonido_tema.SetForegroundColour(_T.text)
        vs.Add(self.chk_musica_sonido_tema, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(self._fila_label(p, "&Decir al pasar de canción:"), 0, wx.LEFT | wx.RIGHT, 10)
        self.cho_musica_decir = EleccionTexto(
            p, (("nada", "Nada"), ("titulo", "El título"),
                ("titulo_artista", "El título y el artista"), ("artista", "Solo el artista")),
            normalizar=musica_decir.normalizar, name="Qué decir al pasar de canción")
        _tc(self.cho_musica_decir)
        vs.Add(self.cho_musica_decir, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.chk_musica_decir_pausa = wx.CheckBox(
            p, label="A&nunciar la pausa, la reanudación y la vuelta al comienzo",
            name="MusicaDecirPausa")
        self.chk_musica_decir_pausa.SetForegroundColour(_T.text)
        vs.Add(self.chk_musica_decir_pausa, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _musica_audio(self, p, vs):
        from ytchat.ui.gui_preferencias import _T
        vs.Add(self._fila_label(p, "&Volumen de la música"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_musica_volumen = ContadorAccesible(
            p, min=0, max=100,
            name="Volumen de la música")
        vs.Add(self.sp_musica_volumen, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_musica_normalizar = wx.CheckBox(
            p, label="&Igualar el volumen de las canciones",
            name="Igualar el volumen de las canciones")
        self.chk_musica_normalizar.SetForegroundColour(_T.text)
        vs.Add(self.chk_musica_normalizar, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Al abrir no se consulta VLC: la lista se arma solo con la salida
        # guardada (o la predeterminada) y se completa con el botón.
        vs.Add(self._fila_label(p, "Salida de a&udio de la música"),
               0, wx.LEFT | wx.RIGHT, 10)
        etiquetas, identificadores, seleccion = opciones_musica.opciones_salida(
            str(self._config.get("musica_salida", "") or ""),
            str(self._config.get("musica_salida_nombre", "") or ""), [])
        self._musica_salidas_ids = identificadores
        self.cho_musica_salida = wx.Choice(
            p, choices=etiquetas, name="Salida de audio de la música")
        self.cho_musica_salida.SetSelection(seleccion)
        vs.Add(self.cho_musica_salida, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.btn_buscar_salidas = wx.Button(
            p, label="&Buscar las salidas de audio",
            name="Buscar las salidas de audio")
        vs.Add(self.btn_buscar_salidas, 0, wx.ALL, 10)
        self.btn_buscar_salidas.Bind(wx.EVT_BUTTON, self._buscar_salidas)

    def _musica_atajos(self, p, vs):
        from ytchat.ui.gui_preferencias import _T
        self.chk_musica_atajos_globales = wx.CheckBox(
            p, label="Usar los atajos de música en cualquier &programa",
            name="MusicaAtajosGlobales")
        self.chk_musica_atajos_globales.SetForegroundColour(_T.text)
        vs.Add(self.chk_musica_atajos_globales, 0,
               wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _buscar_salidas(self, event):
        # Consultar libVLC puede tardar, por eso nunca corre en la interfaz.
        def consultar():
            try:
                from ytchat.music import adaptador_vlc
                salidas = adaptador_vlc.salidas_audio()
            except Exception:
                salidas = []
            wx.CallAfter(self._salidas_encontradas, salidas)

        diagnostico.crear_hilo(consultar, "SalidasAudioPrefs").start()

    def _salidas_encontradas(self, salidas):
        if not self:   # el diálogo pudo cerrarse mientras libVLC respondía
            return
        elegida = self.cho_musica_salida.GetSelection()
        if 0 <= elegida < len(self._musica_salidas_ids):
            elegida_id = self._musica_salidas_ids[elegida]
        else:
            elegida_id = ""
        elegida_nombre = ("" if not elegida_id
                          else self.cho_musica_salida.GetStringSelection())
        etiquetas, identificadores, seleccion = opciones_musica.opciones_salida(
            elegida_id, elegida_nombre, salidas or [])
        self._musica_salidas_ids = identificadores
        self.cho_musica_salida.Set(etiquetas)
        self.cho_musica_salida.SetSelection(seleccion)
        cantidad = len({ident for ident, _nombre in (salidas or []) if ident})
        if cantidad == 1:
            anunciar("Se encontró 1 salida de audio")
        elif cantidad:
            anunciar(f"Se encontraron {cantidad} salidas de audio")
        else:
            anunciar("No se encontraron salidas de audio")
