"""Página Lectura del diálogo de Preferencias.

Por composición, no como mezcla: recibe en el constructor lo que necesita
del diálogo (el dict de config y dos helpers como funciones) y expone
`construir(parent)`, que devuelve el panel, y `cambios()`, que devuelve lo
que esta página guarda fuera de la tabla para que el diálogo lo aplique
con su `_set` de hoy. Los controles conservan nombre, rótulo, `name=` y
orden; el diálogo los reexporta como atributos propios para las pruebas.
"""

from __future__ import annotations

import wx

from ytchat.ui.gui import ContadorAccesible, _T, _tc


_FORMATOS = [
    ("Nombre y mensaje", "nombre_mensaje"),
    ("Mensaje y después el nombre", "mensaje_nombre"),
    ("Solo el mensaje",  "solo_mensaje"),
    ("Solo el nombre",   "solo_nombre"),
]


# Filas de lectura de `_OPCIONES_SIMPLES` en `gui_preferencias`: misma tabla,
# mismo orden.
OPCIONES_LECTURA = (
    ("chk_emojis", "texto", "limpiar_emojis", "limpiar_emojis", bool, True),
    ("chk_urls", "texto", "eliminar_urls", "eliminar_urls", bool, True),
    ("chk_entradas", "tiktok", "anunciar_entradas", "tiktok_anunciar_entradas", bool, False),
    ("chk_me_gusta", "tiktok", "leer_me_gusta", "tiktok_leer_me_gusta", bool, False),
    ("sp_long", "texto", "max_longitud_mensaje", "max_longitud_mensaje", int, 200),
    ("cho_lectura_recientes", "lectura", "recientes", "lectura_recientes", str, "lector"),
    ("chk_lectura_atajos_globales", "lectura", "atajos_globales", "lectura_atajos_globales", bool, False),
)


class PaginaLectura:
    """Página Lectura: qué leer de cada mensaje y hasta cuántos caracteres."""

    def __init__(self, config, fila_label, make_panel):
        self._config = config
        self._fila_label = fila_label
        self._make_panel = make_panel

    def construir(self, parent):
        p = self._make_panel(parent, "PagLectura")
        vs = wx.BoxSizer(wx.VERTICAL)

        vs.Add(self._fila_label(p, "Qué leer de cada mensaje:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.rb_formato = wx.RadioBox(
            p, choices=[f[0] for f in _FORMATOS], majorDimension=1,
            style=wx.RA_SPECIFY_COLS, name="Formato de lectura")
        self.rb_formato.SetForegroundColour(_T.text)
        self.rb_formato.SetBackgroundColour(_T.bg)
        fa = self._config.get("formato_prefijo", "nombre_mensaje")
        for i, (_, v) in enumerate(_FORMATOS):
            if v == fa:
                self.rb_formato.SetSelection(i)
                break
        vs.Add(self.rb_formato, 0, wx.ALL, 10)

        self.chk_emojis = wx.CheckBox(p, label="&Quitar emojis (no mostrarlos en la lista ni leerlos)",
                                      name="LimpiarEmojis")
        self.chk_urls   = wx.CheckBox(p, label="Quitar &URLs al leer", name="EliminarURLs")
        for c in (self.chk_emojis, self.chk_urls):
            c.SetForegroundColour(_T.text)
        vs.Add(self.chk_emojis, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        vs.Add(self.chk_urls, 0, wx.ALL, 10)

        self._construir_tiktok(p, vs)

        vs.Add(self._fila_label(p, "&Longitud máxima del mensaje (caracteres):"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_long = ContadorAccesible(p, min=20, max=1000,
                                   name="Longitud máxima del mensaje")
        _tc(self.sp_long)
        vs.Add(self.sp_long, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self._construir_recientes(p, vs)

        p.SetSizer(vs)
        return p

    def _construir_tiktok(self, p, vs):
        self.chk_entradas = wx.CheckBox(
            p, name="AnunciarEntradas",
            label="Leer quién &entra al directo (solo TikTok; en directos grandes "
                  "puede ser muchísimo)")
        self.chk_entradas.SetForegroundColour(_T.text)
        vs.Add(self.chk_entradas, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.chk_me_gusta = wx.CheckBox(
            p, name="LeerMeGusta",
            label="Leer quién da &me gusta (solo TikTok; en directos grandes "
                  "puede ser muchísimo)")
        self.chk_me_gusta.SetForegroundColour(_T.text)
        vs.Add(self.chk_me_gusta, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _construir_recientes(self, p, vs):
        from ytchat.ui.gui_preferencias import EleccionTexto

        vs.Add(self._fila_label(p, "Leer los mensajes recientes &con:"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.cho_lectura_recientes = EleccionTexto(
            p, (("lector", "El lector de pantalla"),
                ("voz", "La voz de la app")),
            name="Leer los mensajes recientes con")
        _tc(self.cho_lectura_recientes)
        vs.Add(self.cho_lectura_recientes, 0,
               wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_lectura_atajos_globales = wx.CheckBox(
            p, label="Leer los mensajes recientes en cualquier &programa",
            name="LecturaAtajosGlobales")
        self.chk_lectura_atajos_globales.SetForegroundColour(_T.text)
        vs.Add(self.chk_lectura_atajos_globales, 0,
               wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def cambios(self):
        """Lo que esta página guarda fuera de la tabla: (sección, clave, valor)."""
        formato = _FORMATOS[self.rb_formato.GetSelection()][1]
        return [("lectura", "formato_prefijo", formato)]
