"""Página Música del diálogo de Preferencias.

Dueña de sus controles y de su guardado propio. El diálogo la construye
por composición y copia solo los controles que lee su tabla de opciones
simples.
"""

from __future__ import annotations

import wx

from bellbird.core import diagnostico, musica_decir
from bellbird.core import config as cfg
from bellbird.core.idioma import _
from bellbird.ui import opciones_musica
from bellbird.ui.accesibilidad import ContadorAccesible, anunciar, nombre_accesible
from bellbird.ui.tema import _T, _tc
from bellbird.ui.gui_descargas import nombrar_selector_carpeta
from bellbird.ui.preferencias_comun import EleccionTexto, crear_panel, fila_label


# Filas de música de `_OPCIONES_SIMPLES` en `gui_preferencias`: misma tabla, mismo orden.
OPCIONES_MUSICA = (
    ("chk_musica_aleatorio", "musica", "aleatorio", "musica_aleatorio", bool, False),
    ("chk_musica_repetir", "musica", "repetir", "musica_repetir", str, "no"),
    ("chk_musica_retomar", "musica", "retomar", "musica_retomar", bool, True),
    ("sp_musica_cruce", "musica", "cruce", "musica_cruce", int, 6),
    ("chk_musica_sonido_tema", "musica", "sonido_tema", "musica_sonido_tema", bool, False),
    ("cho_musica_decir", "musica", "decir", "musica_decir", str, "titulo"),
    ("chk_musica_decir_pausa", "musica", "decir_pausa", "musica_decir_pausa", bool, True),
    ("sp_musica_volumen", "musica", "volumen", "musica_volumen", int, 50),
    ("chk_musica_normalizar", "musica", "normalizar", "musica_normalizar", bool, True),
    ("chk_musica_preguntar_igualar", "musica", "preguntar_igualar", "musica_preguntar_igualar", bool, True),
    ("chk_musica_atajos_globales", "musica", "atajos_globales", "musica_atajos_globales", bool, False),
)


class PaginaMusica:
    """Página Música: carpeta, orden, repetición, aviso, volumen, igualación y salida."""

    def __init__(self, ventana, config):
        self._ventana = ventana
        self._config = config

    def construir(self, parent):
        p = crear_panel(parent, "PagMusica")
        vs = wx.BoxSizer(wx.VERTICAL)
        self._musica_carpeta(p, vs)
        self._musica_orden(p, vs)
        self._musica_anuncios(p, vs)
        self._musica_audio(p, vs)
        self._musica_atajos(p, vs)
        p.SetSizer(vs)
        return p

    def _musica_carpeta(self, p, vs):
        vs.Add(fila_label(p, _("Carpeta de &música:")),
               0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        carpeta = str(self._config.get("musica_carpeta", "") or "")
        self.dir_musica_carpeta = wx.DirPickerCtrl(
            p, path=carpeta, name=_("Carpeta de música"),
            message=_("Elige la carpeta de música"))
        nombrar_selector_carpeta(self.dir_musica_carpeta)
        # La función nombra el campo para las descargas; acá el campo es la
        # carpeta de música.
        if hasattr(self.dir_musica_carpeta, "GetTextCtrl"):
            nombre_accesible(self.dir_musica_carpeta.GetTextCtrl(),
                             _("Carpeta de música"))
        vs.Add(self.dir_musica_carpeta, 0,
               wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _musica_orden(self, p, vs):
        self.chk_musica_aleatorio = wx.CheckBox(
            p, label=_("Reproducir en orden &aleatorio"),
            name="MusicaAleatorio")
        self.chk_musica_aleatorio.SetForegroundColour(_T.text)
        vs.Add(self.chk_musica_aleatorio, 0, wx.ALL, 10)

        vs.Add(fila_label(p, _("&Repetir:")), 0, wx.LEFT | wx.RIGHT, 10)
        # Traductores: opción de no repetir la música.
        self.chk_musica_repetir = EleccionTexto(
            p, (("no", _("No")), ("todo", _("Toda la cola")),
                 ("tema", _("Esta canción"))),
            normalizar=cfg.normalizar_repetir, name=_("Repetir la música"))
        _tc(self.chk_musica_repetir)
        vs.Add(self.chk_musica_repetir, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_musica_retomar = wx.CheckBox(
            p, label=_("Recordar ú&ltima lista al abrir"),
            name="MusicaRetomar")
        self.chk_musica_retomar.SetForegroundColour(_T.text)
        vs.Add(self.chk_musica_retomar, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(fila_label(p, _("&Fundido entre canciones, en segundos:")),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_musica_cruce = ContadorAccesible(
            p, min=0, max=12,
            name=_("Fundido entre canciones, en segundos"))
        vs.Add(self.sp_musica_cruce, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _musica_anuncios(self, p, vs):
        self.chk_musica_sonido_tema = wx.CheckBox(
            p, label=_("&Sonido al pasar de canción"),
            name="MusicaSonidoTema")
        self.chk_musica_sonido_tema.SetForegroundColour(_T.text)
        vs.Add(self.chk_musica_sonido_tema, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(fila_label(p, _("&Decir al pasar de canción:")), 0, wx.LEFT | wx.RIGHT, 10)
        # Traductores: no decir nada al pasar de canción.
        self.cho_musica_decir = EleccionTexto(
            p, (("nada", _("Nada")), ("titulo", _("El título")),
                ("titulo_artista", _("El título y el artista")), ("artista", _("Solo el artista"))),
            normalizar=musica_decir.normalizar, name=_("Qué decir al pasar de canción"))
        _tc(self.cho_musica_decir)
        vs.Add(self.cho_musica_decir, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.chk_musica_decir_pausa = wx.CheckBox(
            p, label=_("A&nunciar pausa, reanudación y vuelta al comienzo"),
            name="MusicaDecirPausa")
        self.chk_musica_decir_pausa.SetForegroundColour(_T.text)
        vs.Add(self.chk_musica_decir_pausa, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _musica_audio(self, p, vs):
        vs.Add(fila_label(p, _("&Volumen de la música")),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_musica_volumen = ContadorAccesible(
            p, min=0, max=100,
            name=_("Volumen de la música"))
        vs.Add(self.sp_musica_volumen, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self._casilla_igualar(p, vs)

        # Al abrir no se consulta VLC: la lista se arma solo con la salida
        # guardada (o la predeterminada) y se completa con el botón.
        vs.Add(fila_label(p, _("Salida de a&udio de la música")),
               0, wx.LEFT | wx.RIGHT, 10)
        etiquetas, identificadores, seleccion = opciones_musica.opciones_salida(
            str(self._config.get("musica_salida", "") or ""),
            str(self._config.get("musica_salida_nombre", "") or ""), [])
        self._musica_salidas_ids = identificadores
        self.cho_musica_salida = wx.Choice(
            p, choices=etiquetas, name=_("Salida de audio de la música"))
        self.cho_musica_salida.SetSelection(seleccion)
        vs.Add(self.cho_musica_salida, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.btn_buscar_salidas = wx.Button(
            p, label=_("&Buscar salidas de audio"),
            name=_("Buscar salidas de audio"))
        vs.Add(self.btn_buscar_salidas, 0, wx.ALL, 10)
        self.btn_buscar_salidas.Bind(wx.EVT_BUTTON, self._buscar_salidas)

    def _casilla_igualar(self, p, vs):
        self.chk_musica_normalizar = wx.CheckBox(
            p, label=_("&Igualar volumen de las canciones"),
            name=_("Igualar volumen de las canciones"))
        self.chk_musica_normalizar.SetForegroundColour(_T.text)
        vs.Add(self.chk_musica_normalizar, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_musica_preguntar_igualar = wx.CheckBox(
            p, label=_("Pr&eguntar al abrir Música si igualar el volumen"),
            name=_("Preguntar al abrir Música si igualar el volumen"))
        self.chk_musica_preguntar_igualar.SetForegroundColour(_T.text)
        vs.Add(self.chk_musica_preguntar_igualar, 0,
               wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _musica_atajos(self, p, vs):
        self.chk_musica_atajos_globales = wx.CheckBox(
            p, label=_("Usar atajos de música en cualquier &programa"),
            name="MusicaAtajosGlobales")
        self.chk_musica_atajos_globales.SetForegroundColour(_T.text)
        vs.Add(self.chk_musica_atajos_globales, 0,
               wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _buscar_salidas(self, event):
        # Consultar libVLC puede tardar, por eso nunca corre en la interfaz.
        def consultar():
            try:
                from bellbird.music import consultas_vlc
                salidas = consultas_vlc.salidas_audio()
            except Exception:
                salidas = []
            wx.CallAfter(self._salidas_encontradas, salidas)

        diagnostico.crear_hilo(consultar, "SalidasAudioPrefs").start()

    def _salidas_encontradas(self, salidas):
        if not self._ventana:   # el diálogo pudo cerrarse mientras libVLC respondía
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
            anunciar(_("Se encontró 1 salida de audio"))
        elif cantidad:
            anunciar(_("Se encontraron {cantidad} salidas de audio").format(
                cantidad=cantidad))
        else:
            anunciar(_("No se encontraron salidas de audio"))

    def guardar(self, fijar, en_memoria):
        # La carpeta se guarda codificada igual que la lee el cargador; la
        # salida guarda su id y su nombre para no perderla.
        carpeta_musica = self.dir_musica_carpeta.GetPath()
        fijar("musica", "carpeta", cfg.codificar_texto_ini(carpeta_musica))
        en_memoria["musica_carpeta"] = carpeta_musica
        elegida_musica = self.cho_musica_salida.GetSelection()
        if 0 <= elegida_musica < len(self._musica_salidas_ids):
            salida_musica = self._musica_salidas_ids[elegida_musica]
        else:
            salida_musica = ""
        nombre_salida = ("" if not salida_musica
                         else self.cho_musica_salida.GetStringSelection())
        fijar("musica", "salida", salida_musica)
        en_memoria["musica_salida"] = salida_musica
        fijar("musica", "salida_nombre", cfg.codificar_texto_ini(nombre_salida))
        en_memoria["musica_salida_nombre"] = nombre_salida
