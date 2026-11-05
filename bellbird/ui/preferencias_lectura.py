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

from bellbird.core.avisos_tiktok import EVENTOS, MODOS_EVENTO
from bellbird.core.idioma import N_, _
from bellbird.ui.accesibilidad import ContadorAccesible
from bellbird.ui.gui import caja_de_grupo
from bellbird.ui.tema import _T, _tc
from bellbird.ui.preferencias_comun import EleccionTexto


_EVENTOS_LECTURA = {
    "superchat": N_("&Super Chats y regalos:"),
    "miembro": N_("&Membresías:"),
    "entrada": N_("&Entradas al directo:"),
    "me_gusta": N_("Me g&usta:"),
    "seguir": N_("Seguidores nue&vos:"),
    "compartir": N_("&Directo compartido:"),
    "cofre": N_("Co&fres:"),
    "encuesta": N_("Encues&tas:"),
}


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
    ("cho_evento_superchat", "eventos", "superchat", "evento_superchat",
     str, "principal"),
    ("cho_evento_miembro", "eventos", "miembro", "evento_miembro",
     str, "principal"),
    ("cho_evento_entrada", "eventos", "entrada", "evento_entrada",
     str, "mostrar"),
    ("chk_agrupar_entradas", "tiktok", "agrupar_entradas",
     "tiktok_agrupar_entradas", bool, True),
    ("sp_segundos_entradas", "tiktok", "segundos_entradas",
     "tiktok_segundos_entradas", int, 10),
    ("cho_evento_me_gusta", "eventos", "me_gusta", "evento_me_gusta",
     str, "mostrar"),
    ("chk_agrupar_me_gusta", "tiktok", "agrupar_me_gusta",
     "tiktok_agrupar_me_gusta", bool, True),
    ("sp_segundos_me_gusta", "tiktok", "segundos_me_gusta",
     "tiktok_segundos_me_gusta", int, 10),
    ("cho_evento_seguir", "eventos", "seguir", "evento_seguir",
     str, "principal"),
    ("cho_evento_compartir", "eventos", "compartir", "evento_compartir",
     str, "principal"),
    ("cho_evento_cofre", "eventos", "cofre", "evento_cofre",
     str, "principal"),
    ("cho_evento_encuesta", "eventos", "encuesta", "evento_encuesta",
     str, "principal"),
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

        self.rb_formato = wx.RadioBox(
            p, label=_("Qué leer de cada mensaje"),
            choices=[_(f[0]) for f in _FORMATOS], majorDimension=1,
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

        self._construir_eventos(p, vs)

        vs.Add(self._fila_label(p, _("&Longitud máxima del mensaje (caracteres):")),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_long = ContadorAccesible(p, min=20, max=1000,
                                   name=_("Longitud máxima del mensaje"))
        _tc(self.sp_long)
        vs.Add(self.sp_long, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self._construir_recientes(p, vs)

        p.SetSizer(vs)
        return p

    def _construir_eventos(self, p, vs):
        box, padre = caja_de_grupo(p, _("Eventos del directo"))
        grilla = wx.FlexGridSizer(0, 2, 6, 10)
        grilla.AddGrowableCol(1, 1)
        for clave, _fabrica in EVENTOS:
            texto = _(_EVENTOS_LECTURA[clave])
            grilla.Add(self._fila_label(padre, texto), 0,
                       wx.ALIGN_CENTER_VERTICAL)
            lista = EleccionTexto(
                padre, [(valor, _(rotulo)) for valor, rotulo in MODOS_EVENTO],
                name=texto.replace("&", "").rstrip(":"))
            _tc(lista)
            setattr(self, "cho_evento_" + clave, lista)
            grilla.Add(lista, 0, wx.EXPAND)
            if clave == "entrada":
                self._agregar_agrupacion(
                    grilla, padre, "agrupar_entradas",
                    _("Agrupar ent&radas"), _("Agrupar entradas"),
                    _("Agrupar entradas durante (segund&os):"),
                    _("Agrupar entradas durante, en segundos"),
                    "sp_segundos_entradas")
            if clave == "me_gusta":
                self._agregar_agrupacion(
                    grilla, padre, "agrupar_me_gusta",
                    _("Agru&par me gusta"), _("Agrupar me gusta"),
                    _("&Agrupar me gusta durante (segundos):"),
                    _("Agrupar me gusta durante, en segundos"),
                    "sp_segundos_me_gusta")
        box.Add(grilla, 1, wx.EXPAND | wx.ALL, 10)
        vs.Add(box, 0, wx.EXPAND | wx.ALL, 10)

    def _agregar_agrupacion(self, grilla, padre, clave, etiqueta, nombre,
                            etiqueta_contador, nombre_contador, atributo):
        casilla = wx.CheckBox(padre, label=etiqueta, name=nombre)
        casilla.SetForegroundColour(_T.text)
        _tc(casilla)
        setattr(self, "chk_" + clave, casilla)
        grilla.Add((0, 0), 0)
        grilla.Add(casilla, 0, wx.EXPAND)
        grilla.Add(self._fila_label(padre, etiqueta_contador), 0,
                   wx.ALIGN_CENTER_VERTICAL)
        contador = ContadorAccesible(padre, min=1, max=120,
                                     name=nombre_contador)
        _tc(contador)
        setattr(self, atributo, contador)
        grilla.Add(contador, 0)

    def _construir_recientes(self, p, vs):
        vs.Add(self._fila_label(p, _("Leer los mensajes rec&ientes con:")),
               0, wx.LEFT | wx.RIGHT, 10)
        self.cho_lectura_recientes = EleccionTexto(
            p, (("lector", _("El lector de pantalla")),
                ("voz", _("La voz de la app"))),
            name=_("Leer los mensajes recientes con"))
        _tc(self.cho_lectura_recientes)
        vs.Add(self.cho_lectura_recientes, 0,
               wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_lectura_atajos_globales = wx.CheckBox(
            p, label=_("Leer mensajes recientes en cual&quier aplicación"),
            name="LecturaAtajosGlobales")
        self.chk_lectura_atajos_globales.SetForegroundColour(_T.text)
        vs.Add(self.chk_lectura_atajos_globales, 0,
               wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def cambios(self):
        """Lo que esta página guarda fuera de la tabla: (sección, clave, valor)."""
        formato = _FORMATOS[self.rb_formato.GetSelection()][1]
        return [("lectura", "formato_prefijo", formato)]
