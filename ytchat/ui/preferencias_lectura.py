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

from ytchat.core.avisos_tiktok import AVISOS, MODOS
from ytchat.core.idioma import N_, _
from ytchat.ui.accesibilidad import ContadorAccesible
from ytchat.ui.gui import caja_de_grupo
from ytchat.ui.tema import _T, _tc
from ytchat.ui.preferencias_comun import EleccionTexto


_FORMATOS = [
    (N_("Nombre y mensaje"), "nombre_mensaje"),
    (N_("Mensaje y después el nombre"), "mensaje_nombre"),
    (N_("Solo el mensaje"),  "solo_mensaje"),
    (N_("Solo el nombre"),   "solo_nombre"),
]


# Filas de lectura de `_OPCIONES_SIMPLES` en `gui_preferencias`: misma tabla,
# mismo orden.
OPCIONES_LECTURA = (
    ("chk_emojis", "texto", "limpiar_emojis", "limpiar_emojis", bool, True),
    ("chk_urls", "texto", "eliminar_urls", "eliminar_urls", bool, True),
    ("cho_aviso_entradas", "tiktok", "aviso_entradas", "tiktok_aviso_entradas", str, "mostrar"),
    ("cho_aviso_me_gusta", "tiktok", "aviso_me_gusta", "tiktok_aviso_me_gusta", str, "mostrar"),
    ("cho_aviso_seguidores", "tiktok", "aviso_seguidores", "tiktok_aviso_seguidores", str, "leer"),
    ("cho_aviso_compartidos", "tiktok", "aviso_compartidos",
     "tiktok_aviso_compartidos", str, "leer"),
    ("cho_aviso_cofres", "tiktok", "aviso_cofres", "tiktok_aviso_cofres", str, "leer"),
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

        vs.Add(self._fila_label(p, _("Qué leer de cada mensaje:")), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.rb_formato = wx.RadioBox(
            p, choices=[_(f[0]) for f in _FORMATOS], majorDimension=1,
            style=wx.RA_SPECIFY_COLS, name=_("Formato de lectura"))
        self.rb_formato.SetForegroundColour(_T.text)
        self.rb_formato.SetBackgroundColour(_T.bg)
        fa = self._config.get("formato_prefijo", "nombre_mensaje")
        for i, (_sin_uso, v) in enumerate(_FORMATOS):
            if v == fa:
                self.rb_formato.SetSelection(i)
                break
        vs.Add(self.rb_formato, 0, wx.ALL, 10)

        self.chk_emojis = wx.CheckBox(p, label=_("Omitir emo&jis en la lista y al leer"),
                                      name="LimpiarEmojis")
        self.chk_urls   = wx.CheckBox(p, label=_("Omitir e&nlaces al leer"), name="EliminarURLs")
        for c in (self.chk_emojis, self.chk_urls):
            c.SetForegroundColour(_T.text)
        vs.Add(self.chk_emojis, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        vs.Add(self.chk_urls, 0, wx.ALL, 10)

        self._construir_tiktok(p, vs)

        vs.Add(self._fila_label(p, _("&Longitud máxima del mensaje (caracteres):")),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_long = ContadorAccesible(p, min=20, max=1000,
                                   name=_("Longitud máxima del mensaje"))
        _tc(self.sp_long)
        vs.Add(self.sp_long, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self._construir_recientes(p, vs)

        p.SetSizer(vs)
        return p

    def _construir_tiktok(self, p, vs):
        box, padre = caja_de_grupo(p, _("Avisos de TikTok"))
        grilla = wx.FlexGridSizer(0, 2, 6, 10)
        grilla.AddGrowableCol(1, 1)
        for _tipo, clave, etiqueta, _fabrica in AVISOS:
            texto = _(etiqueta)
            grilla.Add(self._fila_label(padre, texto), 0,
                       wx.ALIGN_CENTER_VERTICAL)
            lista = EleccionTexto(
                padre, [(valor, _(rotulo)) for valor, rotulo in MODOS],
                name=texto.replace("&", "").rstrip(":"))
            _tc(lista)
            setattr(self, "cho_" + clave, lista)
            grilla.Add(lista, 0, wx.EXPAND)
        box.Add(grilla, 1, wx.EXPAND | wx.ALL, 10)
        vs.Add(box, 0, wx.EXPAND | wx.ALL, 10)

    def _construir_recientes(self, p, vs):
        vs.Add(self._fila_label(p, _("Leer los mensajes recientes &con:")),
               0, wx.LEFT | wx.RIGHT, 10)
        self.cho_lectura_recientes = EleccionTexto(
            p, (("lector", _("El lector de pantalla")),
                ("voz", _("La voz de la app"))),
            name=_("Leer los mensajes recientes con"))
        _tc(self.cho_lectura_recientes)
        vs.Add(self.cho_lectura_recientes, 0,
               wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_lectura_atajos_globales = wx.CheckBox(
            p, label=_("Leer los mensajes recientes en cualquier &programa"),
            name="LecturaAtajosGlobales")
        self.chk_lectura_atajos_globales.SetForegroundColour(_T.text)
        vs.Add(self.chk_lectura_atajos_globales, 0,
               wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def cambios(self):
        """Lo que esta página guarda fuera de la tabla: (sección, clave, valor)."""
        formato = _FORMATOS[self.rb_formato.GetSelection()][1]
        return [("lectura", "formato_prefijo", formato)]
