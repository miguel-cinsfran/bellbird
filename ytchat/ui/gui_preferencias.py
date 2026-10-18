"""Diálogo de Preferencias por categorías (accesible).

Reúne en un solo sitio lo que antes solo se editaba a mano en config.ini y
sounds.ini: interfaz (fuente, tema de sonido), lectura, filtros de palabras y
usuarios, y un editor de atajos. Persiste con `config.guardar_opciones`, que
escribe todo de una vez al pulsar Guardar (conservando comentarios y orden del
INI), y actualiza el dict de config en memoria.
La configuración de API/OAuth sigue en su propio diálogo (Herramientas).
"""

from __future__ import annotations

import logging
import os
import threading
import time
import webbrowser

import wx

from ytchat.core import diagnostico
from ytchat.core import config as cfg
from ytchat.core import paths
from ytchat.core import preferencias_archivo
from ytchat.ui import atajos_captura
from ytchat.capture import estado_sesion
from ytchat.obs import obs_cliente
from ytchat.obs import obs_activacion
from ytchat.capture import programados
from ytchat.voice import sound_player as _snd
from ytchat.youtube import credenciales
from ytchat.youtube import youtube_api
from ytchat.core.config import APP_NAME
from ytchat.ui.gui import ContadorAccesible, anunciar, caja_de_grupo, nombre_accesible
from ytchat.obs.obs_panel import GestorPanelObs

logger = diagnostico.obtener_logger(__name__)


# El diálogo de Preferencias usa apariencia NATIVA (sin el tema oscuro de la
# ventana principal). Motivo de accesibilidad: en Windows, poner un color
# personalizado a una casilla o radio la convierte en un control «owner-drawn»
# que NVDA anuncia como botón y sin su estado (marcada/no marcada). Sombreamos
# aquí el tema y el helper de color para que TODAS las llamadas existentes
# dejen los controles con los colores por defecto del sistema.

class _T:
    bg = surface = field = border = text = dim = accent = gold = green = red = \
        btn = btn_t = wx.NullColour


def _tc(w, bg=None, fg=None):
    pass


URL_GUIA = "https://github.com/miguel-cinsfran/ytchat-tts/blob/main/docs/CONFIGURACION_API.md"

# Ancho al que se parten las notas de cada página. Con 560 desbordaban el área
# visible (unos 490 px) y no hay desplazamiento horizontal.
ANCHO_NOTA = 450
TAMANO_DIALOGO = (720, 600)

_FORMATOS = [
    ("Nombre y mensaje", "nombre_mensaje"),
    ("Mensaje y después el nombre", "mensaje_nombre"),
    ("Solo el mensaje",  "solo_mensaje"),
    ("Solo el nombre",   "solo_nombre"),
]


# Mensaje de los combinados de voz cuando todavía no se comprobó la clave de
# ElevenLabs, distinto del de un motor sin voces instaladas.
_SIN_CLAVE_ELEVEN = "(comprueba la clave)"
_NO_HAY_VOCES = "(no hay voces disponibles)"


def _miles(numero) -> str:
    """Separa los miles con punto, como se escriben los números en español."""
    try:
        return f"{int(numero):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(numero)



# Opciones que se guardan y se cargan con el mismo molde (leer el control,
# escribir el texto en el ini y copiar el valor a la config en memoria; y al
# revés, volcar la config en el control). Lo que no sigue ese molde va a mano
# en `_on_guardar`. El último campo es el valor de fábrica de
# `config_predeterminada`, ya convertido al tipo de la fila: es el que se
# escribe en el control cuando la config no trae la clave o la trae ilegible.
# `tests/test_preferencias_tabla.py` lo compara con el de fábrica para que no
# se separen.
_OPCIONES_SIMPLES = (
    ("chk_programados", "programados", "activo", "programados_activo", bool, False),
    ("sp_fuente", "ui", "tamanio_fuente_chat", "tamanio_fuente_chat", int, 12),
    ("chk_total_sc", "ui", "mostrar_total_superchats", "mostrar_total_superchats", bool, True),
    ("chk_autoplay", "ui", "autoplay_reproductor", "autoplay_reproductor", bool, True),
    ("chk_solo_audio", "ui", "reproductor_solo_audio", "reproductor_solo_audio", bool, False),
    ("chk_metadatos", "ui", "mostrar_metadatos", "mostrar_metadatos", bool, True),
    ("chk_botones_rep", "ui", "mostrar_botones_reproductor", "mostrar_botones_reproductor", bool, True),
    ("sp_cache_video", "ui", "cache_video_mb", "cache_video_mb", int, 1024),
    ("chk_multivoz", "voz", "multivoz", "multivoz", bool, False),
    ("chk_emojis", "texto", "limpiar_emojis", "limpiar_emojis", bool, True),
    ("chk_urls", "texto", "eliminar_urls", "eliminar_urls", bool, True),
    ("chk_entradas", "tiktok", "anunciar_entradas", "tiktok_anunciar_entradas", bool, False),
    ("sp_long", "texto", "max_longitud_mensaje", "max_longitud_mensaje", int, 200),
    ("sp_cola_maxima", "cola", "tamanio_maximo", "tamanio_maximo", int, 15),
    ("sp_umbral_nombre", "cola", "umbral_solo_nombre", "umbral_solo_nombre", int, 0),
    ("chk_reconectar", "reconexion", "reconectar", "reconectar", bool, True),
    ("sp_espera_reconexion", "reconexion", "espera_entre_intentos", "espera_entre_intentos", int, 15),
    ("sp_max_intentos", "reconexion", "max_intentos", "max_intentos", int, 20),
    ("chk_buscar_actualizaciones", "actualizaciones", "buscar_al_iniciar", "buscar_actualizaciones_al_iniciar", bool, True),
    ("chk_confirmar_salida", "ui", "confirmar_salida", "confirmar_salida", bool, True),
    ("chk_recordar_direccion", "ui", "recordar_direccion", "recordar_direccion", bool, True),
    ("chk_sonido_inicio", "ui", "sonido_inicio", "sonido_inicio", bool, True),
    ("chk_registro_detallado", "diagnostico", "registro_detallado", "registro_detallado", bool, False),
    ("sp_puerto_overlay", "overlay", "puerto", "overlay_puerto", int, 8730),
    ("chk_avisar_sobrecarga", "transmision", "avisar_sobrecarga", "avisar_sobrecarga", bool, True),
)


# ── Captura de atajos (pulsar en vez de escribir) ─────────────────────────────
# Idea tomada del proyecto bellbird del dueño: en vez de teclear el atajo (con
# riesgo de escribirlo mal), se pulsa un botón, se captura la combinación real y
# se valida al vuelo (área correcta y sin conflicto). Así no hay atajos inválidos.

_TECLA_WX_A_TEXTO = {
    wx.WXK_LEFT: "left", wx.WXK_RIGHT: "right", wx.WXK_UP: "up", wx.WXK_DOWN: "down",
    wx.WXK_RETURN: "enter", wx.WXK_NUMPAD_ENTER: "enter", wx.WXK_SPACE: "space",
    wx.WXK_END: "end",
}
_AREA_AYUDA = {
    "ctrl": "Debe ser Ctrl y una tecla (por ejemplo Ctrl+P).",
    "alt":  "Debe ser Alt y una tecla (por ejemplo Alt+C).",
    "f":    "Debe ser una tecla de función, de F1 a F12, sola o con Ctrl (por ejemplo F2 o Ctrl+F2).",
}


def _tecla_texto(keycode: int) -> str | None:
    """Nombre de tecla en nuestro formato («left», «f5», «p»…) desde un keycode
    de wx. None si no es una tecla admitida como atajo."""
    if keycode in _TECLA_WX_A_TEXTO:
        return _TECLA_WX_A_TEXTO[keycode]
    if wx.WXK_F1 <= keycode <= wx.WXK_F12:
        return f"f{keycode - wx.WXK_F1 + 1}"
    if 33 <= keycode < 127:   # letras, dígitos y símbolos ASCII
        return chr(keycode).lower()
    return None


def _combo_a_texto(mods: int, keycode: int) -> str | None:
    """(modificadores, keycode) de wx → texto tipo «ctrl+p», «alt+enter», «f5».
    None si la tecla no sirve como atajo. Deja que config valide el resto."""
    tecla = _tecla_texto(keycode)
    if not tecla:
        return None
    partes = []
    if mods & wx.MOD_CONTROL: partes.append("ctrl")
    if mods & wx.MOD_ALT:     partes.append("alt")
    if mods & wx.MOD_SHIFT:   partes.append("shift")
    return "+".join(partes + [tecla]) if partes else tecla


class PreferenciasDialog(wx.Dialog):

    def __init__(self, parent, config: dict):
        # Redimensionable: quien ve poco puede agrandarlo; las páginas se
        # desplazan solas si no caben.
        super().__init__(parent, title="Preferencias", size=TAMANO_DIALOGO,
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
                         name="DialogoPreferencias")
        self._config = config
        self._ruta = paths.config_ini()
        self._capturando_atajo = None
        self._iniciar_programados()
        self._cambios = False
        self._fallo_guardado = False
        self._pendientes = []
        self.avisos = []
        self.SetBackgroundColour(_T.bg)
        self._build_ui()
        self._ajustar_minimo()
        self.Centre()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        panel = wx.Panel(self, name="PanelPreferencias")
        panel.SetBackgroundColour(_T.bg)
        panel.SetForegroundColour(_T.text)
        vs = wx.BoxSizer(wx.VERTICAL)

        # La lista se anuncia sola al recorrerla, a diferencia de las pestañas.
        self.nb = wx.Listbook(panel, name="Categorías de preferencias")
        self.lista_categorias = self.nb.GetListView()
        nombre_accesible(self.lista_categorias, "Categorías")
        _tc(self.lista_categorias, bg=_T.surface)
        self.nb.AddPage(self._pag_general(self.nb), "General")
        self.nb.AddPage(self._pag_voz(self.nb), "Voces")
        self.nb.AddPage(self._pag_lectura(self.nb), "Lectura")
        self.nb.AddPage(self._pag_cola(self.nb), "Cola de lectura")
        self.nb.AddPage(self._pag_interfaz(self.nb), "Interfaz y sonidos")
        self.nb.AddPage(self._pag_reproductor(self.nb), "Reproductor")
        self.nb.AddPage(self._pag_conexion(self.nb), "Conexión")
        self.nb.AddPage(self._pag_filtros(self.nb), "Filtros")
        self.nb.AddPage(self._pag_estado(self.nb), "Estado (F2)")
        self.nb.AddPage(self._pag_atajos(self.nb), "Atajos")
        self.nb.AddPage(self._pag_api(self.nb), "API y sesión")
        self.nb.AddPage(self._pag_programados(self.nb), "Mensajes automáticos")
        self.nb.AddPage(self._pag_transmision(self.nb), "Transmisión")
        # Mínimo explícito: si no, el libro pide el «mejor tamaño» de la página
        # más alta (Atajos, más de 1200 px) y el sizer lo desbordaría en vez
        # de dejar que la página se desplace.
        self.nb.SetMinSize((320, 240))
        vs.Add(self.nb, 1, wx.EXPAND | wx.ALL, 10)

        row = wx.BoxSizer(wx.HORIZONTAL)
        btn_guardar = wx.Button(panel, wx.ID_OK, "&Guardar", name="GuardarPreferencias")
        btn_cancelar = wx.Button(panel, wx.ID_CANCEL, "&Cancelar", name="CancelarPreferencias")
        for b in (btn_guardar, btn_cancelar):
            b.SetBackgroundColour(_T.btn)
            b.SetForegroundColour(_T.btn_t)
            row.Add(b, 0, wx.RIGHT, 6)
        vs.Add(row, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(vs)
        btn_guardar.Bind(wx.EVT_BUTTON, self._on_guardar)
        self._cargar_opciones_simples()
        self.lista_categorias.SetFocus()

    def _cargar_opciones_simples(self):
        """Vuelca la config en los 20 controles de la tabla. El valor por
        defecto de cada fila es el de fábrica, y se usa tanto si la config no
        trae la clave como si el valor no se puede convertir al tipo."""
        for atributo, _seccion, _clave, en_memoria, tipo, por_defecto in _OPCIONES_SIMPLES:
            control = getattr(self, atributo)
            try:
                valor = tipo(self._config.get(en_memoria, por_defecto))
            except (TypeError, ValueError):
                valor = por_defecto
            control.SetValue(valor)
        # El estado de los controles que depende del valor de una opción simple
        # se decidió en `_build_ui` con el valor viejo del control; se recalcula
        # aquí, ya con el valor cargado.
        self.cho_voz_eventos.Enable(bool(self._voces) and self.chk_multivoz.GetValue())

    def _make_panel(self, parent, name):
        # Página desplazable (solo vertical): la de Atajos mide más de 1200 px
        # y en un wx.Panel fijo dos tercios de sus botones quedaban fuera del
        # alcance del ratón. El foco (Tab) desplaza solo hasta el control.
        p = wx.ScrolledWindow(parent, name=name, style=wx.TAB_TRAVERSAL | wx.VSCROLL)
        p.SetScrollRate(0, 20)
        p.SetBackgroundColour(_T.bg)
        p.SetForegroundColour(_T.text)
        return p

    def _paginas(self):
        return [self.nb.GetPage(i) for i in range(self.nb.GetPageCount())]

    def _ajustar_minimo(self):
        """Ancho mínimo del diálogo: el que deja a la página más ancha entera
        (más la barra de desplazamiento). No hay desplazamiento horizontal,
        así que más angosto se cortarían controles."""
        try:
            self.Layout()
            visible = self.nb.GetPage(0).GetClientSize().width
            necesario = max(p.GetSizer().GetMinSize().width for p in self._paginas())
            barra = wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X)
            ancho = self.GetSize().width - visible + necesario + barra
            alto = 480
            self.SetMinSize((ancho, alto))
            actual = self.GetSize()
            if actual.width < ancho or actual.height < alto:
                self.SetSize((max(actual.width, ancho), max(actual.height, alto)))
        except Exception as exc:
            logger.debug("mínimo del diálogo de preferencias: %s", exc)

    def _pag_interfaz(self, parent):
        p = self._make_panel(parent, "PagInterfaz")
        vs = wx.BoxSizer(wx.VERTICAL)

        vs.Add(self._fila_label(p, "Tamaño de &fuente del chat (8 a 24):"),
               0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.sp_fuente = ContadorAccesible(p, min=8, max=24,
                                     name="Tamaño de fuente del chat")
        _tc(self.sp_fuente)
        vs.Add(self.sp_fuente, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(self._fila_label(p, "&Tema de sonido:"), 0, wx.LEFT | wx.RIGHT, 10)
        temas = cfg.listar_temas_sonido()
        self.cho_tema = wx.Choice(p, choices=temas, name="Tema de sonido")
        _tc(self.cho_tema)
        actual = cfg.tema_sonido_actual()
        self.cho_tema.SetSelection(temas.index(actual) if actual in temas else 0)
        self.cho_tema.Bind(wx.EVT_CHOICE, self._on_muestra_tema)
        vs.Add(self.cho_tema, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_total_sc = wx.CheckBox(p, label="Mostrar el total de &Super Chats en la barra de estado",
                                        name="MostrarTotalSuperChats")
        self.chk_total_sc.SetForegroundColour(_T.text)
        vs.Add(self.chk_total_sc, 0, wx.ALL, 10)

        self.chk_metadatos = wx.CheckBox(p, label="Mostrar la pestaña de &información del vídeo (canal, vistas, descripción)",
                                         name="MostrarMetadatos")
        self.chk_metadatos.SetForegroundColour(_T.text)
        vs.Add(self.chk_metadatos, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        p.SetSizer(vs)
        return p

    def _on_muestra_tema(self, event):
        """Suena la muestra del tema elegido sin cambiar el tema activo."""
        try:
            tema = self.cho_tema.GetStringSelection()
            if tema:
                _snd.reproducir_archivo(cfg.ruta_muestra_tema(tema))
        except Exception:
            pass
        event.Skip()

    def _pag_cola(self, parent):
        p = self._make_panel(parent, "PagCola")
        vs = wx.BoxSizer(wx.VERTICAL)

        self.rb_estrategia = wx.RadioBox(
            p, label="&Estrategia de la cola", majorDimension=1,
            choices=["Leer todos los mensajes",
                     "Descartar los más viejos si se acumulan"],
            style=wx.RA_SPECIFY_COLS, name="Estrategia de la cola")
        self.rb_estrategia.SetSelection(
            0 if self._config.get("estrategia", "limite") == "todas" else 1)
        vs.Add(self.rb_estrategia, 0, wx.ALL, 10)

        vs.Add(self._fila_label(p, "Tamaño &máximo de la cola"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_cola_maxima = ContadorAccesible(
            p, min=1, max=500,
            name="Tamaño máximo de la cola")
        vs.Add(self.sp_cola_maxima, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(self._fila_label(p, "Leer solo el &nombre a partir de"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_umbral_nombre = ContadorAccesible(
            p, min=0, max=500,
            name="Leer solo el nombre a partir de")
        vs.Add(self.sp_umbral_nombre, 0, wx.LEFT | wx.RIGHT, 10)
        vs.Add(wx.StaticText(p, label="Con 0, esta opción queda apagada."),
               0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        p.SetSizer(vs)
        return p

    def _pag_general(self, parent):
        p = self._make_panel(parent, "PagGeneral")
        vs = wx.BoxSizer(wx.VERTICAL)

        self.chk_buscar_actualizaciones = wx.CheckBox(
            p, label="Buscar &actualizaciones al iniciar",
            name="Buscar actualizaciones al iniciar")
        vs.Add(self.chk_buscar_actualizaciones, 0, wx.ALL, 10)

        self.chk_confirmar_salida = wx.CheckBox(
            p, label="Preguntar antes de &salir si hay un chat conectado "
                     "o una transmisión en curso",
            name="Preguntar antes de salir si hay un chat conectado "
                 "o una transmisión en curso")
        vs.Add(self.chk_confirmar_salida, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_recordar_direccion = wx.CheckBox(
            p, label="&Recordar la última dirección",
            name="Recordar la última dirección")
        vs.Add(self.chk_recordar_direccion, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_sonido_inicio = wx.CheckBox(
            p, label="Reproducir el sonido de &inicio",
            name="Reproducir el sonido de inicio")
        vs.Add(self.chk_sonido_inicio, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_registro_detallado = wx.CheckBox(
            p, label="Guardar un registro &detallado para diagnosticar fallos",
            name="Guardar un registro detallado para diagnosticar fallos")
        vs.Add(self.chk_registro_detallado, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Archivo de preferencias: la importación y el restablecimiento piden
        # reiniciar y cierran el diálogo sin guardar, para que Guardar no pise
        # el archivo nuevo con los valores viejos de los controles.
        self.btn_abrir_datos = wx.Button(
            p, label="Abrir la carpeta de da&tos",
            name="Abrir la carpeta de datos")
        vs.Add(self.btn_abrir_datos, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_exportar_prefs = wx.Button(
            p, label="E&xportar las preferencias…",
            name="Exportar las preferencias")
        vs.Add(self.btn_exportar_prefs, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_importar_prefs = wx.Button(
            p, label="I&mportar las preferencias…",
            name="Importar las preferencias")
        vs.Add(self.btn_importar_prefs, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_restablecer_prefs = wx.Button(
            p, label="Restablecer todas las &preferencias…",
            name="Restablecer todas las preferencias")
        vs.Add(self.btn_restablecer_prefs, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_abrir_datos.Bind(wx.EVT_BUTTON, self._abrir_datos)
        self.btn_exportar_prefs.Bind(wx.EVT_BUTTON, self._exportar_prefs)
        self.btn_importar_prefs.Bind(wx.EVT_BUTTON, self._importar_prefs)
        self.btn_restablecer_prefs.Bind(wx.EVT_BUTTON, self._restablecer_prefs)

        p.SetSizer(vs)
        return p

    def _abrir_datos(self, event):
        try:
            os.startfile(str(paths.carpeta_datos()))  # noqa: S606
        except Exception as exc:
            wx.MessageBox(f"No se pudo abrir la carpeta de datos:\n\n{exc}",
                          "Carpeta de datos", wx.OK | wx.ICON_ERROR, self)

    def _exportar_prefs(self, event):
        with wx.FileDialog(
                self, "Exportar las preferencias",
                wildcard="Preferencias (*.ini)|*.ini",
                defaultFile="YTChat TTS preferencias.ini",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as cuadro:
            if cuadro.ShowModal() != wx.ID_OK:
                return
            ruta = cuadro.GetPath()
        try:
            preferencias_archivo.exportar(ruta)
        except Exception as exc:
            wx.MessageBox(f"No se pudieron exportar las preferencias:\n\n{exc}",
                          "Exportar las preferencias",
                          wx.OK | wx.ICON_ERROR, self)
            return
        anunciar("Preferencias exportadas")

    def _importar_prefs(self, event):
        with wx.FileDialog(
                self, "Importar las preferencias",
                wildcard="Preferencias (*.ini)|*.ini",
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as cuadro:
            if cuadro.ShowModal() != wx.ID_OK:
                return
            ruta = cuadro.GetPath()
        motivo = preferencias_archivo.motivo_no_importable(ruta)
        if motivo is not None:
            wx.MessageBox(motivo, "Importar las preferencias",
                          wx.OK | wx.ICON_WARNING, self)
            return
        try:
            preferencias_archivo.importar(ruta)
        except Exception as exc:
            wx.MessageBox("No se pudieron importar las preferencias:\n\n"
                          f"{exc}", "Importar las preferencias",
                          wx.OK | wx.ICON_ERROR, self)
            return
        wx.MessageBox("Preferencias importadas. Se aplican al reiniciar "
                      "la aplicación.",
                      "Preferencias importadas",
                      wx.OK | wx.ICON_INFORMATION, self)
        # Como Cancelar: cierra sin guardar para no pisar el archivo nuevo.
        self.EndModal(wx.ID_CANCEL)

    def _restablecer_prefs(self, event):
        dialogo = wx.MessageDialog(
            self, "¿Restablecer todas las preferencias a los valores de "
                  "fábrica? Se guarda una copia de las actuales en la "
                  "carpeta de datos.",
            "Restablecer las preferencias",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION | wx.CENTRE)
        try:
            respuesta = dialogo.ShowModal()
        finally:
            dialogo.Destroy()
        if respuesta != wx.ID_YES:
            return
        try:
            preferencias_archivo.restablecer()
        except Exception as exc:
            wx.MessageBox("No se pudieron restablecer las preferencias:\n\n"
                          f"{exc}",
                          "Restablecer las preferencias",
                          wx.OK | wx.ICON_ERROR, self)
            return
        wx.MessageBox("Preferencias restablecidas. Se aplican al reiniciar "
                      "la aplicación.",
                      "Preferencias restablecidas",
                      wx.OK | wx.ICON_INFORMATION, self)
        self.EndModal(wx.ID_CANCEL)

    def _pag_conexion(self, parent):
        p = self._make_panel(parent, "PagConexion")
        vs = wx.BoxSizer(wx.VERTICAL)

        self.chk_reconectar = wx.CheckBox(
            p, label="&Reconectar automáticamente si se corta",
            name="Reconectar automáticamente si se corta")
        vs.Add(self.chk_reconectar, 0, wx.ALL, 10)

        vs.Add(self._fila_label(p, "&Espera entre intentos, en segundos"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_espera_reconexion = ContadorAccesible(
            p, min=1, max=300,
            name="Espera entre intentos, en segundos")
        vs.Add(self.sp_espera_reconexion, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(self._fila_label(p, "Número máximo de &intentos"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_max_intentos = ContadorAccesible(
            p, min=0, max=100,
            name="Número máximo de intentos")
        vs.Add(self.sp_max_intentos, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        p.SetSizer(vs)
        return p

    def _pag_transmision(self, parent):
        p = self._make_panel(parent, "PagTransmision")
        vs = wx.BoxSizer(wx.VERTICAL)

        self.chk_avisar_sobrecarga = wx.CheckBox(
            p, label="&Avisar cuando OBS no da abasto",
            name="AvisarSobrecargaObs")
        self.chk_avisar_sobrecarga.SetForegroundColour(_T.text)
        vs.Add(self.chk_avisar_sobrecarga, 0, wx.ALL, 10)

        vs.Add(self._fila_label(p, "&Puerto del panel de chat"),
               0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.sp_puerto_overlay = ContadorAccesible(
            p, min=1024, max=65535,
            name="Puerto del panel de chat")
        vs.Add(self.sp_puerto_overlay, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(self._fila_label(p, "&Micrófono de OBS"),
               0, wx.LEFT | wx.RIGHT, 10)
        guardado = str(self._config.get("obs_microfono", ""))
        opciones = ["Elegir automáticamente"] + ([guardado] if guardado else [])
        self.cho_microfono_obs = wx.Choice(
            p, choices=opciones, name="Micrófono de OBS")
        self.cho_microfono_obs.SetSelection(1 if guardado else 0)
        vs.Add(self.cho_microfono_obs, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.btn_buscar_microfonos = wx.Button(
            p, label="&Buscar los micrófonos en OBS",
            name="Buscar los micrófonos en OBS")
        vs.Add(self.btn_buscar_microfonos, 0, wx.ALL, 10)
        self.btn_buscar_microfonos.Bind(wx.EVT_BUTTON, self._buscar_microfonos)

        self.btn_activar_websocket_obs = wx.Button(
            p, label="&Activar el servidor websocket de OBS",
            name="Activar el servidor websocket de OBS")
        vs.Add(self.btn_activar_websocket_obs, 0, wx.ALL, 10)
        self.btn_activar_websocket_obs.Bind(
            wx.EVT_BUTTON, self._activar_servidor_websocket_obs)

        p.SetSizer(vs)
        return p

    def _buscar_microfonos(self, event):
        # Consultar OBS puede tardar o no responder, por eso nunca corre en la interfaz.
        def consultar():
            gestor = None
            try:
                gestor = GestorPanelObs(ajustes=obs_cliente.leer_ajustes())
                gestor.conectar()
                wx.CallAfter(self._microfonos_encontrados, gestor.fuentes_audio())
            except Exception as exc:
                wx.CallAfter(anunciar, obs_cliente.mensaje_de_fallo_obs(exc))
            finally:
                if gestor is not None:
                    try:
                        gestor.cerrar()
                    except Exception:
                        pass

        diagnostico.crear_hilo(consultar, "MicrofonosPrefs").start()

    def _microfonos_encontrados(self, fuentes):
        if not self:   # el diálogo pudo cerrarse mientras OBS respondía
            return
        elegido = self.cho_microfono_obs.GetStringSelection()
        opciones = ["Elegir automáticamente"]
        # La fuente guardada se conserva aunque OBS no responda o ya no la vea.
        for fuente in (elegido, *fuentes):
            if fuente and fuente not in opciones:
                opciones.append(fuente)
        self.cho_microfono_obs.Set(opciones)
        self.cho_microfono_obs.SetStringSelection(elegido or opciones[0])
        anunciar(f"Se encontraron {len(fuentes)} micrófonos en OBS")

    def _activar_servidor_websocket_obs(self, event):
        def activar():
            try:
                accion, mensaje = obs_activacion.decidir_activacion(
                    obs_activacion.obs_esta_en_ejecucion(),
                    obs_cliente.leer_ajustes())
                if accion == obs_activacion.ACTIVAR:
                    mensaje = obs_activacion.activar_servidor(
                        obs_cliente.RUTA_CONFIG_OBS)
            except Exception as exc:
                logger.warning("No se pudo activar el servidor websocket de OBS: %s", exc)
                mensaje = f"No se pudo activar el servidor websocket de OBS: {exc}"
            wx.CallAfter(anunciar, mensaje)

        diagnostico.crear_hilo(activar, "ActivarWebsocketObs").start()

    def _pag_reproductor(self, parent):
        p = self._make_panel(parent, "PagReproductor")
        vs = wx.BoxSizer(wx.VERTICAL)

        self.chk_autoplay = wx.CheckBox(p, label="&Reproducir el audio automáticamente al conectar",
                                        name="AutoplayReproductor")
        self.chk_autoplay.SetForegroundColour(_T.text)
        vs.Add(self.chk_autoplay, 0, wx.ALL, 10)

        self.chk_solo_audio = wx.CheckBox(
            p, label="Reproducir &solo el audio, sin decodificar la imagen",
            name="SoloAudioReproductor")
        self.chk_solo_audio.SetForegroundColour(_T.text)
        vs.Add(self.chk_solo_audio, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_botones_rep = wx.CheckBox(p, label="Mostrar los &botones del reproductor (también con su interruptor y el menú Reproductor)",
                                           name="MostrarBotonesReproductor")
        self.chk_botones_rep.SetForegroundColour(_T.text)
        vs.Add(self.chk_botones_rep, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        etiqueta_cache = wx.StaticText(
            p, label="&Tamaño máximo de la caché de vídeo, en megabytes:")
        self.sp_cache_video = wx.SpinCtrl(
            p, min=0, max=20000,
            name="Tamaño máximo de la caché de vídeo en megabytes")
        vs.Add(etiqueta_cache, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        vs.Add(self.sp_cache_video, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        p.SetSizer(vs)
        return p

    def _pag_voz(self, parent):
        p = self._make_panel(parent, "PagVoz")
        self._pag_voz_panel = p
        vs = wx.BoxSizer(wx.VERTICAL)

        from ytchat.voice import escala_voz
        from ytchat.voice import motores

        motor_guardado = self._config.get("motor", "sapi")
        self._motor_idx = (motores.MOTORES.index(motor_guardado)
                           if motor_guardado in motores.MOTORES else 0)
        es_eleven = motores.MOTORES[self._motor_idx] == "elevenlabs"

        # Motor de voz (SAPI 5, OneCore o ElevenLabs). Cambiarlo repuebla las
        # voces de abajo.
        vs.Add(self._fila_label(p, "&Motor de voz:"),
               0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.cho_motor = wx.Choice(
            p, choices=[motores.NOMBRES[m] for m in motores.MOTORES],
            name="Motor de voz")
        _tc(self.cho_motor)
        self.cho_motor.SetSelection(self._motor_idx)
        self.cho_motor.Bind(wx.EVT_CHOICE, self._on_motor_cambiado)
        vs.Add(self.cho_motor, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Clave de ElevenLabs y su comprobación. Solo se ven con ese motor: la
        # clave es un secreto y va a credenciales.json, nunca al ini.
        lbl_clave = self._fila_label(p, "Cl&ave de ElevenLabs:")
        self.txt_clave_eleven = wx.TextCtrl(
            p, value=credenciales.cargar().get("elevenlabs_clave", "") or "",
            style=wx.TE_PASSWORD, name="Clave de ElevenLabs")
        _tc(self.txt_clave_eleven)
        vs.Add(lbl_clave, 0, wx.LEFT | wx.RIGHT, 10)
        vs.Add(self.txt_clave_eleven, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.btn_comprobar_clave = wx.Button(
            p, label="Compro&bar clave", name="Comprobar clave")
        self.btn_comprobar_clave.SetBackgroundColour(_T.btn)
        self.btn_comprobar_clave.SetForegroundColour(_T.btn_t)
        self.btn_comprobar_clave.Bind(wx.EVT_BUTTON, self._on_comprobar_clave)
        vs.Add(self.btn_comprobar_clave, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Voz del motor elegido. También está en el menú Voz → Seleccionar voz;
        # aquí queda junto al resto de ajustes de lectura para encontrarla más
        # fácil.
        vs.Add(self._fila_label(p, "&Voz de lectura:"), 0, wx.LEFT | wx.RIGHT, 10)
        if es_eleven:
            # Nunca se va a la red en el hilo de la interfaz: la lista queda
            # vacía hasta que se compruebe la clave.
            self._voces = []
            vacio_voz = _SIN_CLAVE_ELEVEN
        else:
            self._voces = motores.listar_voces(motores.MOTORES[self._motor_idx])
            vacio_voz = _NO_HAY_VOCES
        self.cho_voz = wx.Choice(p, choices=self._voces or [vacio_voz],
                                 name="Voz de lectura")
        _tc(self.cho_voz)
        self._cargar_voces(self.cho_voz, self._config.get("voz"), vacio=vacio_voz)
        vs.Add(self.cho_voz, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Velocidad, volumen y tono como valores absolutos 0..100.
        vs.Add(self._fila_label(p, "Ve&locidad (0 a 100):"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_velocidad = ContadorAccesible(
            p, min=0, max=100,
            initial=escala_voz.ajustar_velocidad(
                int(self._config.get("velocidad_voz", escala_voz.VELOCIDAD_NORMAL)), 0),
            name="Velocidad de la voz")
        self.sp_velocidad.SetIncrement(5)
        _tc(self.sp_velocidad)
        vs.Add(self.sp_velocidad, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        try:
            vol_pct = max(0, min(100, int(round(
                float(self._config.get("volumen", 1.0)) * 100))))
        except (TypeError, ValueError):
            vol_pct = 100
        vs.Add(self._fila_label(p, "Vol&umen (0 a 100):"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_volumen = ContadorAccesible(
            p, min=0, max=100, initial=vol_pct, name="Volumen de la voz")
        self.sp_volumen.SetIncrement(5)
        _tc(self.sp_volumen)
        vs.Add(self.sp_volumen, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(self._fila_label(p, "&Tono (0 a 100):"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_tono = ContadorAccesible(
            p, min=0, max=100,
            initial=max(0, min(100, int(self._config.get("tono", 50)))),
            name="Tono de la voz")
        self.sp_tono.SetIncrement(5)
        _tc(self.sp_tono)
        vs.Add(self.sp_tono, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.btn_probar_voz = wx.Button(p, label="&Probar voz", name="Probar voz")
        self.btn_probar_voz.SetBackgroundColour(_T.btn)
        self.btn_probar_voz.SetForegroundColour(_T.btn_t)
        self.btn_probar_voz.Bind(wx.EVT_BUTTON, self._on_probar_voz)
        vs.Add(self.btn_probar_voz, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Tope de caracteres por sesión (0 sin tope), «solo lo importante» y
        # la voz de Windows de respaldo. Solo se ven con ElevenLabs.
        lbl_tope = self._fila_label(
            p, "T&ope de caracteres por sesión (0 sin tope):")
        self.sp_tope_eleven = ContadorAccesible(
            p, min=0, max=1000000,
            initial=max(0, int(self._config.get("elevenlabs_tope", 0) or 0)),
            name="Tope de caracteres de ElevenLabs")
        self.sp_tope_eleven.SetIncrement(1000)
        _tc(self.sp_tope_eleven)
        vs.Add(lbl_tope, 0, wx.LEFT | wx.RIGHT, 10)
        vs.Add(self.sp_tope_eleven, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.chk_solo_importantes = wx.CheckBox(
            p, name="Solo lo importante con ElevenLabs",
            label="U&sar ElevenLabs solo con Super Chats, miembros, cofres, "
                  "dueño y moderadores")
        self.chk_solo_importantes.SetForegroundColour(_T.text)
        self.chk_solo_importantes.SetValue(
            bool(self._config.get("elevenlabs_solo_importantes", False)))
        vs.Add(self.chk_solo_importantes, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        lbl_respaldo = self._fila_label(p, "Voz de &Windows de respaldo:")
        self._voces_respaldo = motores.listar_voces("sapi")
        self.cho_voz_respaldo = wx.Choice(
            p, choices=self._voces_respaldo or [_NO_HAY_VOCES],
            name="Voz de Windows de respaldo")
        _tc(self.cho_voz_respaldo)
        if self._voces_respaldo:
            idx_respaldo = escala_voz.resolver_voz(
                self._config.get("voz_respaldo"), self._voces_respaldo)
            self.cho_voz_respaldo.SetSelection(
                0 if idx_respaldo is None else idx_respaldo)
        else:
            self.cho_voz_respaldo.SetSelection(0)
            self.cho_voz_respaldo.Disable()
        vs.Add(lbl_respaldo, 0, wx.LEFT | wx.RIGHT, 10)
        vs.Add(self.cho_voz_respaldo, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self._eleven_ctrls = [
            lbl_clave, self.txt_clave_eleven, self.btn_comprobar_clave,
            lbl_tope, self.sp_tope_eleven, self.chk_solo_importantes,
            lbl_respaldo, self.cho_voz_respaldo,
        ]

        # Multi-voz: una voz distinta para los eventos (Super Chats, regalos,
        # miembros, entradas). Desactivada por defecto.
        self.chk_multivoz = wx.CheckBox(
            p, name="MultiVoz",
            label="Usar una voz &distinta para los eventos (Super Chats, regalos, "
                  "miembros y entradas)")
        self.chk_multivoz.SetForegroundColour(_T.text)
        vs.Add(self.chk_multivoz, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        vs.Add(self._fila_label(p, "Voz para los &eventos:"), 0, wx.LEFT | wx.RIGHT, 10)
        self.cho_voz_eventos = wx.Choice(
            p, choices=self._voces or [vacio_voz],
            name="Voz para los eventos")
        _tc(self.cho_voz_eventos)
        self._cargar_voces(self.cho_voz_eventos, self._config.get("voz_eventos"),
                           vacio=vacio_voz)
        self.cho_voz_eventos.Enable(bool(self._voces) and self.chk_multivoz.GetValue())
        self.chk_multivoz.Bind(
            wx.EVT_CHECKBOX,
            lambda e: self.cho_voz_eventos.Enable(bool(self._voces) and e.IsChecked()))
        vs.Add(self.cho_voz_eventos, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # El motor de prueba se cierra al cerrar el diálogo por cualquier camino.
        self._motor_prueba = None
        self._probando_eleven = False
        self.Bind(wx.EVT_WINDOW_DESTROY, self._al_destruir)

        p.SetSizer(vs)
        self._mostrar_controles_eleven(es_eleven)
        if es_eleven and self.txt_clave_eleven.GetValue().strip():
            # Con clave guardada, las voces se comprueban solas en segundo
            # plano y se llenan; sin clave, todo queda a la espera.
            self.btn_comprobar_clave.Disable()
            self._comprobar_clave(anunciar_ok=False)
        return p

    def _mostrar_controles_eleven(self, visible: bool) -> None:
        """Muestra u oculta los controles exclusivos de ElevenLabs. Ocultos
        salen del orden de Tab y la página se vuelve a acomodar."""
        for ctrl in getattr(self, "_eleven_ctrls", ()):
            ctrl.Show(visible)
        panel = getattr(self, "_pag_voz_panel", None)
        if panel is not None:
            panel.Layout()

    def _preparar_voces_eleven(self, anunciar_ok: bool = False) -> None:
        """Deja las voces en «(comprueba la clave)» y, si hay clave escrita, la
        comprueba en segundo plano sin bloquear la interfaz."""
        self._voces = []
        self._cargar_voces(self.cho_voz, self._config.get("voz"),
                           vacio=_SIN_CLAVE_ELEVEN)
        self._cargar_voces(self.cho_voz_eventos, self._config.get("voz_eventos"),
                           vacio=_SIN_CLAVE_ELEVEN)
        self.cho_voz_eventos.Disable()
        if self.txt_clave_eleven.GetValue().strip():
            self.btn_comprobar_clave.Disable()
            self._comprobar_clave(anunciar_ok)

    def _on_comprobar_clave(self, event) -> None:
        if not self.txt_clave_eleven.GetValue().strip():
            anunciar("Escribe la clave de ElevenLabs.")
            return
        self.btn_comprobar_clave.Disable()
        self._comprobar_clave(anunciar_ok=True)

    def _comprobar_clave(self, anunciar_ok: bool) -> None:
        """Lanza la comprobación en un hilo: voces y saldo van a la red y eso
        nunca puede correr en el hilo de la interfaz."""
        clave = self.txt_clave_eleven.GetValue().strip()
        diagnostico.crear_hilo(
            lambda: self._consultar_clave(clave, anunciar_ok),
            "ComprobarClaveEleven").start()

    def _consultar_clave(self, clave: str, anunciar_ok: bool) -> None:
        from ytchat.voice import elevenlabs
        try:
            cliente = elevenlabs.ClienteElevenLabs(clave)
            pares = cliente.voces()
            usados, limite = cliente.saldo()
        except Exception as exc:
            wx.CallAfter(self._clave_fallo, str(exc))
            return
        wx.CallAfter(self._clave_ok, pares, usados, limite, anunciar_ok)

    def _clave_ok(self, pares, usados, limite, anunciar_ok: bool) -> None:
        if not self:   # el diálogo pudo cerrarse mientras se comprobaba
            return
        self.btn_comprobar_clave.Enable()
        self._voces = [nombre for _id, nombre in pares]
        self._cargar_voces(self.cho_voz, self._config.get("voz"),
                           vacio=_SIN_CLAVE_ELEVEN)
        self._cargar_voces(self.cho_voz_eventos, self._config.get("voz_eventos"),
                           vacio=_SIN_CLAVE_ELEVEN)
        self.cho_voz_eventos.Enable(bool(self._voces) and self.chk_multivoz.GetValue())
        if anunciar_ok:
            anunciar(f"Clave válida. {len(self._voces)} voces. "
                     f"Usados {_miles(usados)} de {_miles(limite)} caracteres este mes.")

    def _clave_fallo(self, mensaje) -> None:
        if not self:
            return
        self.btn_comprobar_clave.Enable()
        self._voces = []
        self._cargar_voces(self.cho_voz, None, vacio=_SIN_CLAVE_ELEVEN)
        self._cargar_voces(self.cho_voz_eventos, None, vacio=_SIN_CLAVE_ELEVEN)
        self.cho_voz_eventos.Disable()
        anunciar(mensaje)

    def _cargar_voces(self, choice, guardada, vacio=_NO_HAY_VOCES) -> None:
        """Llena un combinado de voces y elige la guardada (o la primera). Sin
        voces deja el aviso deshabilitado, como antes."""
        from ytchat.voice import escala_voz
        if self._voces:
            choice.SetItems(self._voces)
            idx = escala_voz.resolver_voz(guardada, self._voces)
            choice.SetSelection(0 if idx is None else idx)
            choice.Enable(True)
        else:
            choice.SetItems([vacio])
            choice.SetSelection(0)
            choice.Disable()

    def _motor_elegido(self) -> str:
        from ytchat.voice import motores
        i = self.cho_motor.GetSelection()
        return motores.MOTORES[i] if 0 <= i < len(motores.MOTORES) else "sapi"

    def _on_motor_cambiado(self, event) -> None:
        # Repuebla las voces del motor nuevo sin anunciar: el lector ya lee el
        # valor del combinado al recorrerlo. Con ElevenLabs, además, se ocultan
        # o muestran sus controles y se comprueba la clave en segundo plano.
        from ytchat.voice import motores
        motor = self._motor_elegido()
        if motor == "elevenlabs":
            self._mostrar_controles_eleven(True)
            self._preparar_voces_eleven()
            return
        self._mostrar_controles_eleven(False)
        self._voces = motores.listar_voces(motor)
        self._cargar_voces(self.cho_voz, self._config.get("voz"))
        self._cargar_voces(self.cho_voz_eventos, self._config.get("voz_eventos"))
        self.cho_voz_eventos.Enable(bool(self._voces) and self.chk_multivoz.GetValue())

    def _on_probar_voz(self, event) -> None:
        from ytchat.voice import motores
        if self._motor_elegido() == "elevenlabs":
            self._probar_voz_elevenlabs()
            return
        self._cerrar_motor_prueba()
        try:
            prueba = motores.MotorPrism(self._motor_elegido())
        except motores.MotorNoDisponible:
            anunciar("No se pudo iniciar el motor de voz elegido.")
            return
        self._motor_prueba = prueba
        try:
            prueba.elegir_voz(self.cho_voz.GetSelection())
            prueba.fijar_velocidad(self.sp_velocidad.GetValue())
            prueba.fijar_volumen(self.sp_volumen.GetValue())
            prueba.fijar_tono(self.sp_tono.GetValue())
            prueba.hablar("Así suena esta voz.")
        except Exception as exc:
            logger.warning("Prueba de voz: %s", exc)

    def _probar_voz_elevenlabs(self) -> None:
        if not self._voces:
            anunciar("Primero comprueba la clave.")
            return
        if self._probando_eleven:
            return
        self._probando_eleven = True
        clave = self.txt_clave_eleven.GetValue().strip()
        voz = self.cho_voz.GetStringSelection()
        velocidad = self.sp_velocidad.GetValue()
        volumen = self.sp_volumen.GetValue()
        diagnostico.crear_hilo(
            lambda: self._sonar_prueba_elevenlabs(clave, voz, velocidad, volumen),
            "ProbarVozEleven").start()

    def _sonar_prueba_elevenlabs(self, clave, voz, velocidad, volumen) -> None:
        """Crea, usa y cierra el motor de la prueba DENTRO de su hilo: MCI y
        Prism no son seguros entre hilos."""
        from ytchat.voice import escala_voz
        from ytchat.voice import motor_elevenlabs
        prueba = None
        try:
            prueba = motor_elevenlabs.MotorElevenLabs(clave)
            idx = escala_voz.resolver_voz(voz, prueba.voces())
            prueba.elegir_voz(0 if idx is None else idx)
            prueba.fijar_velocidad(velocidad)
            prueba.fijar_volumen(volumen)
            prueba.hablar("Así suena esta voz.")
            while prueba.hablando():
                time.sleep(0.05)
        except Exception as exc:
            wx.CallAfter(anunciar, str(exc))
        finally:
            if prueba is not None:
                try:
                    prueba.cerrar()
                except Exception:
                    pass
            wx.CallAfter(self._fin_prueba_elevenlabs)

    def _fin_prueba_elevenlabs(self) -> None:
        if not self:
            return
        self._probando_eleven = False

    def _cerrar_motor_prueba(self) -> None:
        motor = getattr(self, "_motor_prueba", None)
        if motor is None:
            return
        self._motor_prueba = None
        try:
            motor.cerrar()
        except Exception as exc:
            logger.debug("Cerrar motor de prueba: %s", exc)

    def _al_destruir(self, event) -> None:
        # El evento sube desde los hijos, así que solo se atiende cuando el
        # diálogo mismo se destruye.
        if event.GetEventObject() is self:
            self._cerrar_motor_prueba()
        event.Skip()

    def _pag_lectura(self, parent):
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

        self.chk_entradas = wx.CheckBox(
            p, name="AnunciarEntradas",
            label="Leer quién &entra al directo (solo TikTok; en directos grandes "
                  "puede ser muchísimo)")
        self.chk_entradas.SetForegroundColour(_T.text)
        vs.Add(self.chk_entradas, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(self._fila_label(p, "&Longitud máxima del mensaje (caracteres):"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_long = ContadorAccesible(p, min=20, max=1000,
                                   name="Longitud máxima del mensaje")
        _tc(self.sp_long)
        vs.Add(self.sp_long, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        p.SetSizer(vs)
        return p

    def _pag_estado(self, parent):
        """Una casilla por componente del anuncio de estado (tecla F2). Sin
        colores en las casillas: en Windows eso rompe su rol accesible."""
        p = self._make_panel(parent, "PagEstado")
        vs = wx.BoxSizer(wx.VERTICAL)

        nota = wx.StaticText(p, name="NotaEstado", label=(
            "Elige qué dice la tecla F2 (estado de sesión). Marca lo que quieras "
            "oír; por defecto, los datos del vídeo y del chat. El orden en que se "
            "dice es fijo."))
        nota.SetForegroundColour(_T.dim)
        nota.Wrap(ANCHO_NOTA)
        vs.Add(nota, 0, wx.ALL, 10)

        activos = self._config.get("estado_toggles") or estado_sesion.ACTIVOS_DEFECTO
        self._chk_estado: dict = {}
        for comp in estado_sesion.COMPONENTES:
            chk = wx.CheckBox(p, label=estado_sesion.ETIQUETAS.get(comp, comp),
                              name=f"EstadoComponente_{comp}")
            chk.SetForegroundColour(_T.text)
            chk.SetValue(comp in activos)
            self._chk_estado[comp] = chk
            vs.Add(chk, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        p.SetSizer(vs)
        return p

    def _pag_filtros(self, parent):
        p = self._make_panel(parent, "PagFiltros")
        vs = wx.BoxSizer(wx.VERTICAL)

        vs.Add(self._fila_label(p, "&Palabras silenciadas (separadas por comas):"),
               0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.txt_palabras = wx.TextCtrl(
            p, value=", ".join(self._config.get("palabras_silenciadas", [])),
            name="Palabras silenciadas")
        _tc(self.txt_palabras)
        vs.Add(self.txt_palabras, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        vs.Add(self._fila_label(p, "&Usuarios silenciados (separados por comas):"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.txt_usuarios = wx.TextCtrl(
            p, value=", ".join(self._config.get("usuarios_silenciados", [])),
            name="Usuarios silenciados")
        _tc(self.txt_usuarios)
        vs.Add(self.txt_usuarios, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        nota = wx.StaticText(p, label=(
            "Estos filtros ocultan y no leen los mensajes que contengan esas "
            "palabras o de esos usuarios. Se aplican a partir del próximo mensaje."),
            name="NotaFiltros")
        nota.SetForegroundColour(_T.dim)
        nota.Wrap(ANCHO_NOTA)
        vs.Add(nota, 0, wx.ALL, 10)

        p.SetSizer(vs)
        return p

    def _pag_atajos(self, parent):
        p = self._make_panel(parent, "PagAtajos")
        vs = wx.BoxSizer(wx.VERTICAL)

        nota = wx.StaticText(p, label=(
            "Cada área tiene su modificador: Ctrl para el reproductor, Alt para "
            "conexión y chat, y teclas F para la voz. Pulsa un botón y luego la "
            "combinación que quieras: se comprueba sola que sea válida y que no "
            "choque con otra. F9 a F12, Alt+F4, F6 y Shift+F6 son fijas. "
            "Las fijas se muestran para que no se puedan pisar."),
            name="NotaAtajos")
        nota.SetForegroundColour(_T.dim)
        nota.Wrap(ANCHO_NOTA)
        vs.Add(nota, 0, wx.ALL, 10)

        # Valores normalizados en memoria (lo que se edita y se guarda).
        raw = self._config.get("atajos_raw", {})
        self._valores_atajo: dict[str, str] = {}
        self._botones_atajo: dict[str, wx.Button] = {}
        for accion, default in cfg.todos_los_atajos_default().items():
            crudo = raw.get(accion, default)
            self._valores_atajo[accion] = (
                default if accion in cfg.ATAJOS_FIJOS
                else cfg._normalizar_atajo(crudo) or "")

        for titulo, acciones in cfg.ATAJOS_GRUPOS:
            box, padre = caja_de_grupo(p, titulo)
            for accion in acciones:
                etiqueta = etiqueta_de_accion(accion)
                fija = accion in cfg.ATAJOS_FIJOS
                valor = self._valores_atajo.get(accion, "")
                sufijo = " (fija)" if fija else ""
                btn = wx.Button(
                    padre, name=f"Atajo_{accion}",
                    label=atajos_captura.etiqueta_boton(etiqueta, valor) + sufijo)
                btn.SetBackgroundColour(_T.btn); btn.SetForegroundColour(_T.btn_t)
                if fija:
                    btn.Disable()
                else:
                    btn.SetToolTip("Pulsa para capturar una nueva combinación.")
                    btn.Bind(wx.EVT_BUTTON,
                             lambda e, a=accion, et=etiqueta: self._capturar_atajo(a, et))
                    btn.Bind(wx.EVT_KILL_FOCUS, self._atajo_perdio_foco)
                self._botones_atajo[accion] = btn
                box.Add(btn, 0, wx.EXPAND | wx.ALL, 4)
            vs.Add(box, 0, wx.EXPAND | wx.ALL, 8)

        btn_restablecer = wx.Button(
            p, label="&Restablecer los atajos a los valores de fábrica",
            name="RestablecerAtajos")
        btn_restablecer.SetBackgroundColour(_T.btn)
        btn_restablecer.SetForegroundColour(_T.btn_t)
        btn_restablecer.Bind(wx.EVT_BUTTON, self._restablecer_atajos)
        vs.Add(btn_restablecer, 0, wx.ALL, 10)

        p.Bind(wx.EVT_CHAR_HOOK, self._on_tecla_captura)
        p.SetSizer(vs)
        return p

    def _capturar_atajo(self, accion, etiqueta):
        self._capturando_atajo = (accion, etiqueta)
        boton = self._botones_atajo[accion]
        boton.SetLabel(f"{etiqueta}: pulsa la combinación")
        anunciar(atajos_captura.texto_de_espera(
            etiqueta, _AREA_AYUDA.get(cfg.ATAJOS_AREA.get(accion), "")))

    def _restaurar_etiqueta_atajo(self, accion, etiqueta):
        valor = self._valores_atajo.get(accion, "")
        sufijo = " (fija)" if accion in cfg.ATAJOS_FIJOS else ""
        self._botones_atajo[accion].SetLabel(
            atajos_captura.etiqueta_boton(etiqueta, valor) + sufijo)

    def _salir_captura_atajo(self, anunciar_cambio=False):
        if self._capturando_atajo is None:
            return
        accion, etiqueta = self._capturando_atajo
        self._capturando_atajo = None
        self._restaurar_etiqueta_atajo(accion, etiqueta)
        if anunciar_cambio:
            anunciar("Sin cambios")

    def _restablecer_atajos(self, event):
        from ytchat.core import config_predeterminada as _pred
        for accion, valor in _pred.seccion("atajos").items():
            if accion in cfg.ATAJOS_FIJOS:
                continue
            self._valores_atajo[accion] = valor
            self._restaurar_etiqueta_atajo(accion, etiqueta_de_accion(accion))
        anunciar("Atajos restablecidos a los valores de fábrica. Se aplican al pulsar Guardar")

    def _atajo_perdio_foco(self, event):
        self._salir_captura_atajo()
        event.Skip()

    def _on_tecla_captura(self, event):
        if self._capturando_atajo is None:
            event.Skip()
            return
        k = event.GetKeyCode()
        mods = event.GetModifiers()
        if k == wx.WXK_ESCAPE:
            self._salir_captura_atajo(True)
            return
        if k in (wx.WXK_SHIFT, wx.WXK_CONTROL, wx.WXK_ALT, wx.WXK_RAW_CONTROL):
            return
        if k == wx.WXK_TAB and mods == wx.MOD_NONE:
            self._salir_captura_atajo()
            event.Skip()
            return
        accion, etiqueta = self._capturando_atajo
        if k in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and mods == wx.MOD_NONE:
            estado, valor, texto = atajos_captura.resolver(
                accion, None, self._valores_atajo)
        else:
            combo = _combo_a_texto(mods, k)
            estado, valor, texto = atajos_captura.resolver(
                accion, combo, self._valores_atajo)
        anunciar(texto)
        if estado == "rechazado":
            wx.MessageBox(texto, APP_NAME, wx.OK | wx.ICON_ERROR, self)
            boton = self._botones_atajo[accion]
            boton.SetFocus()
            self._capturar_atajo(accion, etiqueta)
            return
        self._valores_atajo[accion] = valor
        self._capturando_atajo = None
        self._restaurar_etiqueta_atajo(accion, etiqueta)

    def _pag_api(self, parent):
        p = self._make_panel(parent, "PagApi")
        self._login_en_curso = False
        vs = wx.BoxSizer(wx.VERTICAL)

        intro = wx.StaticText(p, name="IntroApi", label=(
            "La API key permite LEER comentarios (sin iniciar sesión). El cliente "
            "OAuth e iniciar sesión permiten MODERAR el chat, enviar mensajes al "
            "directo y publicar o responder comentarios."))
        intro.SetForegroundColour(_T.dim)
        intro.Wrap(ANCHO_NOTA)
        vs.Add(intro, 0, wx.ALL, 10)

        if not youtube_api.google_disponible():
            aviso = wx.StaticText(p, name="AvisoLibreriasApi", label=(
                "AVISO: faltan las librerías de la API. Instálalas con:\n"
                "pip install google-api-python-client google-auth-oauthlib"))
            aviso.SetForegroundColour(_T.red)
            vs.Add(aviso, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        datos = credenciales.cargar()
        grid = wx.FlexGridSizer(3, 2, 8, 8)
        grid.AddGrowableCol(1, 1)
        self.txt_api = self._fila_api(p, grid, "&API key:", "API key de YouTube",
                                      datos.get("api_key", ""))
        self.txt_cid = self._fila_api(p, grid, "ID de &cliente OAuth:",
                                      "ID de cliente OAuth", datos.get("oauth_client_id", ""))
        self.txt_secret = self._fila_api(p, grid, "&Secreto de cliente OAuth:",
                                         "Secreto de cliente OAuth",
                                         datos.get("oauth_client_secret", ""), password=True)
        vs.Add(grid, 0, wx.EXPAND | wx.ALL, 10)

        self.lbl_estado_api = wx.StaticText(p, name="EstadoSesion", label="")
        self.lbl_estado_api.SetForegroundColour(_T.accent)
        vs.Add(self.lbl_estado_api, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_api_guardar = wx.Button(p, label="&Guardar claves", name="GuardarClaves")
        self.btn_api_login   = wx.Button(p, label="&Iniciar sesión", name="IniciarSesion")
        self.btn_api_logout  = wx.Button(p, label="Cerrar s&esión", name="CerrarSesion")
        self.btn_api_guia    = wx.Button(p, label="Abrir g&uía", name="AbrirGuia")
        for b in (self.btn_api_guardar, self.btn_api_login, self.btn_api_logout, self.btn_api_guia):
            b.SetBackgroundColour(_T.btn)
            b.SetForegroundColour(_T.btn_t)
            row.Add(b, 0, wx.RIGHT, 6)
        vs.Add(row, 0, wx.ALL, 10)

        p.SetSizer(vs)
        self.btn_api_guardar.Bind(wx.EVT_BUTTON, self._api_guardar)
        self.btn_api_login.Bind(wx.EVT_BUTTON, self._api_login)
        self.btn_api_logout.Bind(wx.EVT_BUTTON, self._api_logout)
        self.btn_api_guia.Bind(wx.EVT_BUTTON, lambda e: webbrowser.open(URL_GUIA))
        self._api_refrescar_estado()
        return p

    def _iniciar_programados(self):
        self._ruta_programados = paths.mensajes_programados()
        self._mensajes_programados = programados.cargar(self._ruta_programados)

    def _pag_programados(self, parent):
        p = self._make_panel(parent, "PagProgramados")
        vs = wx.BoxSizer(wx.VERTICAL)
        intro = wx.StaticText(p, name="IntroProgramados", label=(
            "Envía mensajes al chat de tu directo cada cierto tiempo. Necesita "
            "sesión de Google iniciada y un directo de YouTube conectado. El "
            "intervalo mínimo son 5 minutos y cada mensaje admite 200 caracteres. "
            "YouTube suele bloquear los enlaces en el chat en vivo: conviene "
            "escribir el nombre de usuario en vez de la dirección completa."))
        intro.SetForegroundColour(_T.dim)
        intro.Wrap(ANCHO_NOTA)
        vs.Add(intro, 0, wx.ALL, 10)

        self.chk_programados = wx.CheckBox(
            p, label="&Activar los mensajes automáticos", name="ActivarProgramados")
        vs.Add(self.chk_programados, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.lista_programados = wx.ListBox(p, choices=[
            programados.describir_mensaje(m) for m in self._mensajes_programados
        ], name="ListaProgramados")
        nombre_accesible(self.lista_programados, "Mensajes automáticos guardados")
        vs.Add(self.lista_programados, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        vs.Add(self._fila_label(p, "&Texto del mensaje"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.txt_programado = wx.TextCtrl(p, name="TextoProgramado")
        self.txt_programado.SetMaxLength(200)
        vs.Add(self.txt_programado, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        vs.Add(self._fila_label(p, "Cada, &mínimo (minutos)"), 0, wx.LEFT | wx.RIGHT, 10)
        self.sp_min_programado = ContadorAccesible(
            p, min=5, max=240, initial=10, name="MinutosMin")
        vs.Add(self.sp_min_programado, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        vs.Add(self._fila_label(p, "y &máximo (minutos)"), 0, wx.LEFT | wx.RIGHT, 10)
        self.sp_max_programado = ContadorAccesible(
            p, min=5, max=240, initial=10, name="MinutosMax")
        vs.Add(self.sp_max_programado, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.chk_mensaje_activo = wx.CheckBox(
            p, label="&Enviar este mensaje", name="MensajeActivo")
        # Un mensaje nuevo nace activo: si no, quien lo agrega y activa los
        # automáticos no ve salir nada porque quedó «Pausado».
        self.chk_mensaje_activo.SetValue(True)
        vs.Add(self.chk_mensaje_activo, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_programado_agregar = wx.Button(p, label="&Agregar", name="AgregarProgramado")
        self.btn_programado_guardar = wx.Button(
            p, label="&Guardar cambios", name="GuardarProgramado")
        self.btn_programado_quitar = wx.Button(p, label="&Quitar", name="QuitarProgramado")
        for boton in (self.btn_programado_agregar, self.btn_programado_guardar,
                      self.btn_programado_quitar):
            boton.SetBackgroundColour(_T.btn)
            boton.SetForegroundColour(_T.btn_t)
            fila.Add(boton, 0, wx.RIGHT, 6)
        vs.Add(fila, 0, wx.ALL, 10)

        p.SetSizer(vs)
        self.lista_programados.Bind(wx.EVT_LISTBOX, self._programado_elegido)
        self.btn_programado_agregar.Bind(wx.EVT_BUTTON, self._agregar_programado)
        self.btn_programado_guardar.Bind(wx.EVT_BUTTON, self._guardar_programado)
        self.btn_programado_quitar.Bind(wx.EVT_BUTTON, self._quitar_programado)
        return p

    def _programado_elegido(self, event):
        indice = self.lista_programados.GetSelection()
        if indice != wx.NOT_FOUND:
            mensaje = self._mensajes_programados[indice]
            self.txt_programado.SetValue(mensaje.get("texto", ""))
            self.sp_min_programado.SetValue(mensaje.get("minutos_min", 10))
            self.sp_max_programado.SetValue(mensaje.get("minutos_max", 10))
            self.chk_mensaje_activo.SetValue(mensaje.get("activo", False))
            anunciar(programados.describir_mensaje(mensaje))
        event.Skip()

    def _datos_programado(self):
        return {
            "texto": self.txt_programado.GetValue(),
            "minutos_min": self.sp_min_programado.GetValue(),
            "minutos_max": self.sp_max_programado.GetValue(),
            "activo": self.chk_mensaje_activo.GetValue(),
            "proximo": 0.0,
        }

    def _validar_programado(self, mensaje):
        error, aviso = programados.validar_mensaje(
            mensaje["texto"], mensaje["minutos_min"], mensaje["minutos_max"])
        if error:
            anunciar(error)
            if not mensaje["texto"].strip() or len(mensaje["texto"]) > programados.MAX_CARACTERES:
                self.txt_programado.SetFocus()
            elif mensaje["minutos_min"] < programados.MINUTOS_MINIMOS:
                self.sp_min_programado.SetFocus()
            else:
                self.sp_max_programado.SetFocus()
            return False
        if aviso:
            anunciar(aviso)
        return True

    def _refrescar_programados(self, indice=-1):
        self.lista_programados.Set([programados.describir_mensaje(m)
                                    for m in self._mensajes_programados])
        if indice >= 0:
            self.lista_programados.SetSelection(indice)

    def _agregar_programado(self, event):
        mensaje = self._datos_programado()
        if not self._validar_programado(mensaje):
            return
        self._mensajes_programados.append(mensaje)
        programados.guardar(self._ruta_programados, self._mensajes_programados)
        self._refrescar_programados(len(self._mensajes_programados) - 1)
        anunciar("Mensaje agregado")

    def _guardar_programado(self, event):
        indice = self.lista_programados.GetSelection()
        if indice == wx.NOT_FOUND:
            anunciar("Elige primero un mensaje de la lista")
            return
        mensaje = self._datos_programado()
        if not self._validar_programado(mensaje):
            return
        mensaje["proximo"] = self._mensajes_programados[indice].get("proximo", 0.0)
        self._mensajes_programados[indice] = mensaje
        programados.guardar(self._ruta_programados, self._mensajes_programados)
        self._refrescar_programados(indice)
        anunciar("Mensaje guardado")

    def _quitar_programado(self, event):
        indice = self.lista_programados.GetSelection()
        if indice == wx.NOT_FOUND:
            anunciar("Elige primero un mensaje de la lista")
            return
        self._mensajes_programados.pop(indice)
        programados.guardar(self._ruta_programados, self._mensajes_programados)
        self._refrescar_programados(min(indice, len(self._mensajes_programados) - 1))
        anunciar("Mensaje quitado")

    def _fila_api(self, p, grid, etiqueta, nombre, valor, password=False):
        lbl = wx.StaticText(p, label=etiqueta)
        lbl.SetForegroundColour(_T.text)
        estilo = wx.TE_PASSWORD if password else 0
        txt = wx.TextCtrl(p, value=valor or "", style=estilo, name=nombre)
        _tc(txt)
        grid.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(txt, 1, wx.EXPAND)
        return txt

    def _api_refrescar_estado(self):
        if credenciales.hay_sesion():
            texto = "Estado: sesión iniciada. Moderación y comentarios activos."
            self.btn_api_logout.Enable()
        else:
            texto = "Estado: sin sesión. Solo lectura de comentarios (si hay API key)."
            self.btn_api_logout.Disable()
        if credenciales.usa_cliente_de_la_app():
            texto += " Se usa el cliente de Google de la aplicación."
        if not youtube_api.google_disponible():
            self.btn_api_login.Disable()
        self.lbl_estado_api.SetLabel(texto)

    def _api_guardar(self, event):
        credenciales.guardar_campo("api_key", self.txt_api.GetValue().strip())
        credenciales.guardar_campo("oauth_client_id", self.txt_cid.GetValue().strip())
        credenciales.guardar_campo("oauth_client_secret", self.txt_secret.GetValue().strip())
        _snd.reproducir("copiar")
        anunciar("Claves guardadas")
        self._api_refrescar_estado()

    def _api_login(self, event):
        if self._login_en_curso:
            return
        cid = self.txt_cid.GetValue().strip()
        secret = self.txt_secret.GetValue().strip()
        if not (cid and secret):
            # Sin cliente propio, vale el que trae la app: la persona solo
            # pulsa «Iniciar sesión», sin guardar nada en sus campos.
            efectivas = credenciales.efectivas()
            cid_app = (efectivas.get("oauth_client_id") or "").strip()
            secret_app = (efectivas.get("oauth_client_secret") or "").strip()
            if not (cid_app and secret_app):
                wx.MessageBox("Rellena el ID y el secreto de cliente OAuth antes de "
                              "iniciar sesión.", "Faltan datos", wx.OK | wx.ICON_WARNING, self)
                return
            cid, secret = cid_app, secret_app
        else:
            self._api_guardar(None)
        self._login_en_curso = True
        self.btn_api_login.Disable()
        anunciar("Abriendo el navegador para iniciar sesión. Autoriza y vuelve aquí.")

        def _run():
            try:
                token = youtube_api.iniciar_sesion(cid, secret)
                credenciales.guardar_campo("token", token)
                wx.CallAfter(self._api_login_ok)
            except Exception as exc:
                logger.warning("Login OAuth falló: %s", exc)
                wx.CallAfter(self._api_login_err, exc)

        diagnostico.crear_hilo(_run, "OAuthLogin").start()

    def _api_login_ok(self):
        if not self:   # el diálogo pudo cerrarse mientras se autorizaba
            return
        self._login_en_curso = False
        self.btn_api_login.Enable()
        _snd.reproducir("conectado")
        anunciar("Sesión iniciada correctamente.")
        self._api_refrescar_estado()

    def _api_login_err(self, exc):
        if not self:
            return
        self._login_en_curso = False
        self.btn_api_login.Enable()
        _snd.reproducir("error")
        anunciar("No se pudo iniciar sesión.")
        wx.MessageBox(f"No se pudo iniciar sesión:\n\n{exc}", "Error de inicio de sesión",
                      wx.OK | wx.ICON_ERROR, self)

    def _api_logout(self, event):
        credenciales.cerrar_sesion()
        _snd.reproducir("desconectado")
        anunciar("Sesión cerrada.")
        self._api_refrescar_estado()

    def _fila_label(self, p, texto):
        lbl = wx.StaticText(p, label=texto)
        lbl.SetForegroundColour(_T.accent)
        return lbl

    # ── Guardar ───────────────────────────────────────────────────────────────

    def _set(self, seccion, clave, valor):
        self._pendientes.append((seccion, clave, valor))
        self._cambios = True

    def _on_guardar(self, event):
        c = self._config
        self._pendientes = []
        self._fallo_guardado = False
        registro_detallado_inicial = bool(c.get("registro_detallado", False))
        puerto_anterior = int(c.get("overlay_puerto", 8730))
        # Los atajos ya vienen validados desde la captura (área + conflicto), así
        # que aquí solo se guardan; no hace falta revalidar por escritura.

        # Opciones simples: las de la tabla van por el bucle, el resto a mano.
        for atributo, seccion, clave, en_memoria, tipo, _por_defecto in _OPCIONES_SIMPLES:
            control = getattr(self, atributo)
            if tipo is bool:
                valor = control.GetValue()
                self._set(seccion, clave, "true" if valor else "false")
                c[en_memoria] = valor
            else:
                valor = int(control.GetValue())
                self._set(seccion, clave, str(valor))
                c[en_memoria] = valor

        tema = self.cho_tema.GetStringSelection()
        if tema and tema != cfg.tema_sonido_actual():
            if not cfg.guardar_opcion(paths.sounds_ini(), "sonidos", "tema", tema):
                self._fallo_guardado = True
            try:    _snd.cargar(cfg.cargar_sonidos())
            except Exception as exc: logger.warning("recargar sonidos: %s", exc)
            self._cambios = True

        # Voz: motor, voz de lectura, voz de eventos, velocidad, volumen y tono.
        # Si el motor elegido no tiene voces no se guardan motor ni voz (se
        # conservan los anteriores); el resto de las opciones se guarda igual.
        motor_no_disponible = False
        if self._voces:
            motor = self._motor_elegido()
            self._set("voz", "motor", motor)
            c["motor"] = motor
            # Se guarda el nombre, no el número: el índice se corre al instalar
            # una voz y la app hablaría con otra sin avisar.
            nom_voz = self.cho_voz.GetStringSelection()
            self._set("voz", "voz", nom_voz)
            c["voz"] = nom_voz
            nom_ev = self.cho_voz_eventos.GetStringSelection()
            self._set("voz", "voz_eventos", nom_ev)
            c["voz_eventos"] = nom_ev
        else:
            motor_no_disponible = True

        # Clave de ElevenLabs: es un secreto y va a credenciales.json, nunca al
        # ini. Solo se escribe si cambió.
        clave_eleven = self.txt_clave_eleven.GetValue().strip()
        if clave_eleven != (credenciales.cargar().get("elevenlabs_clave", "") or ""):
            credenciales.guardar_campo("elevenlabs_clave", clave_eleven)

        # Tope, «solo lo importante» y voz de respaldo de ElevenLabs se guardan
        # siempre, haya o no clave comprobada.
        tope_eleven = self.sp_tope_eleven.GetValue()
        self._set("voz", "elevenlabs_tope", str(tope_eleven))
        c["elevenlabs_tope"] = tope_eleven
        solo_importantes = self.chk_solo_importantes.GetValue()
        self._set("voz", "elevenlabs_solo_importantes",
                  "true" if solo_importantes else "false")
        c["elevenlabs_solo_importantes"] = solo_importantes
        voz_respaldo = (self.cho_voz_respaldo.GetStringSelection()
                        if self._voces_respaldo else "")
        self._set("voz", "voz_respaldo", voz_respaldo)
        c["voz_respaldo"] = voz_respaldo

        self._cerrar_motor_prueba()
        from ytchat.voice import escala_voz
        velocidad = escala_voz.ajustar_velocidad(self.sp_velocidad.GetValue(), 0)
        self._set("voz", "velocidad_voz", str(velocidad))
        c["velocidad_voz"] = velocidad
        volumen = self.sp_volumen.GetValue()
        self._set("voz", "volumen", f"{volumen / 100:.2f}")
        c["volumen"] = round(volumen / 100.0, 2)
        tono = self.sp_tono.GetValue()
        self._set("voz", "tono", str(tono))
        c["tono"] = tono

        formato = _FORMATOS[self.rb_formato.GetSelection()][1]
        self._set("lectura", "formato_prefijo", formato)
        c["formato_prefijo"] = formato

        # Se guarda la clave, no la etiqueta, porque config.ini solo admite estas claves.
        estrategia = ("todas", "limite")[self.rb_estrategia.GetSelection()]
        self._set("cola", "estrategia", estrategia)
        c["estrategia"] = estrategia
        registro_detallado = c["registro_detallado"]
        puerto_overlay = c["overlay_puerto"]
        microfono_obs = ("" if self.cho_microfono_obs.GetSelection() == 0
                         else self.cho_microfono_obs.GetStringSelection())
        self._set("obs", "microfono", microfono_obs)
        c["obs_microfono"] = microfono_obs

        # Estado (F2): una clave por componente + el set en memoria.
        activos = set()
        for comp, chk in self._chk_estado.items():
            on = chk.GetValue()
            self._set("estado", comp, "true" if on else "false")
            if on:
                activos.add(comp)
        c["estado_toggles"] = activos

        # Filtros
        palabras = self.txt_palabras.GetValue().strip()
        self._set("filtros", "palabras_silenciadas", palabras)
        c["palabras_silenciadas"] = _lista(palabras)
        usuarios = self.txt_usuarios.GetValue().strip()
        self._set("filtros", "usuarios_silenciados", usuarios)
        c["usuarios_silenciados"] = _lista(usuarios)

        # Atajos: los valores capturados (ya normalizados y validados).
        raw = c.setdefault("atajos_raw", {})
        for accion, valor in self._valores_atajo.items():
            if accion in cfg.ATAJOS_FIJOS:
                continue
            self._set("atajos", accion, valor)
            raw[accion] = valor

        if not cfg.guardar_opciones(self._ruta, self._pendientes):
            self._fallo_guardado = True

        if not self._fallo_guardado:
            _snd.reproducir("copiar")
        else:
            _snd.reproducir("error")

        # Los avisos se juntan acá y los dice la ventana principal una sola vez,
        # ya con el foco de vuelta en ella: anunciarlos antes de cerrar hacía que
        # el cambio de foco los cortara entre sí.
        self.avisos = []
        if not self._fallo_guardado:
            self.avisos.append("Preferencias guardadas.")
        else:
            self.avisos.append("Las preferencias se aplicaron, pero no se pudieron "
                               "guardar en el disco. Se perderán al cerrar la "
                               "aplicación.")
        if motor_no_disponible:
            self.avisos.append("El motor elegido no está disponible, se conserva el anterior.")
        if registro_detallado != registro_detallado_inicial:
            self.avisos.append("El cambio del registro detallado se aplica al reiniciar "
                               "la aplicación.")
        # El servidor del panel ya escucha en el puerto viejo; no se reinicia
        # solo, así que se avisa dónde se aplica.
        if puerto_overlay != puerto_anterior and c.get("overlay_activo", False):
            self.avisos.append("El puerto nuevo del panel de chat se aplica al apagarlo y "
                               "volver a encenderlo desde el panel de transmisión.")
        self.EndModal(wx.ID_OK)

    def hubo_cambios(self) -> bool:
        return self._cambios


_ETIQUETAS_ATAJO = {
    # Reproductor
    "rep_play":          "Reproducir o pausa",
    "rep_retro":         "Retroceder 1 minuto",
    "rep_avanz":         "Avanzar 1 minuto",
    "rep_directo":       "Ir al directo",
    "rep_detener":       "Detener vídeo",
    "rep_mute":          "Silenciar o activar audio",
    "rep_vol_menos":     "Bajar volumen del reproductor",
    "rep_vol_mas":       "Subir volumen del reproductor",
    "descargas_abrir":   "Abrir el gestor de descargas",
    "pantalla_completa": "Pantalla completa",
    "abrir_preferencias": "Abrir Preferencias",
    "abrir_historial":    "Abrir el historial de directos",
    "marcar_incidencia":  "Marcar incidencia",
    "abrir_transmision":  "Abrir Transmisión",
    "copiar_enlace":      "Copiar enlace del directo",
    "obs_micro":          "Silenciar el micrófono de OBS",
    "avisos_sobrecarga":  "Activar o desactivar los avisos de sobrecarga",
    # Conexión y chat
    "conectar":          "Conectar",
    "desconectar":       "Desconectar",
    "enviar_chat":       "Enviar mensaje al chat",
    "ir_lista":          "Ir a la lista del panel actual",
    "salir":             "Salir de la aplicación",
    # Voz / lectura
    "pausa":             "Pausar o reanudar lectura",
    "detener_tts":       "Detener voz actual",
    "velocidad_menos":   "Bajar velocidad (fija)",
    "velocidad_mas":     "Subir velocidad (fija)",
    "volumen_menos":     "Bajar volumen del TTS (fijo)",
    "volumen_mas":       "Subir volumen del TTS (fijo)",
    "silenciar_lectura": "Silenciar lectura TTS",
    "silenciar_sonidos": "Silenciar sonidos",
    "anunciar_estado":   "Anunciar estado",
    "anunciar_autor":    "Anunciar autor del último mensaje",
    "describir_escena":  "Describir la escena de OBS",
    "region_siguiente":  "Región siguiente",
    "region_anterior":   "Región anterior",
}
_mostrar_atajo = atajos_captura.mostrar_atajo


def etiqueta_de_accion(accion: str) -> str:
    try:
        etiqueta = _ETIQUETAS_ATAJO.get(accion)
        if etiqueta is not None:
            return etiqueta
        return str(accion).replace("_", " ").capitalize()
    except Exception:
        return ""


def _lista(v: str) -> list:
    return [x.strip().lower() for x in v.split(",") if x.strip()]


def abrir_preferencias(parent, config: dict, pagina=None, avisos=None) -> bool:
    """Devuelve True si se guardaron cambios (para aplicarlos en caliente).

    Si `pagina` coincide con el texto de una pestaña (p. ej. "API y sesión"),
    esa queda seleccionada al abrir. Sin `pagina`, igual que siempre.
    Si se pasa una lista en `avisos`, al cerrar con Guardar se le agregan los
    avisos que armó el diálogo, para que la ventana principal los diga cuando
    recupera el foco.
    """
    dlg = PreferenciasDialog(parent, config)
    try:
        if pagina:
            try:
                for i in range(dlg.nb.GetPageCount()):
                    if dlg.nb.GetPageText(i) == pagina:
                        dlg.nb.SetSelection(i)
                        break
            except Exception as exc:
                logger.debug("abrir_preferencias: no se pudo elegir página: %s", exc)
        res = dlg.ShowModal()
        if res == wx.ID_OK and avisos is not None:
            avisos.extend(dlg.avisos)
        return res == wx.ID_OK and dlg.hubo_cambios()
    finally:
        dlg.Destroy()


def ofrecer_iniciar_sesion(parent, config) -> bool:
    """Ofrece abrir Preferencias en la pestaña de sesión tras caducar el token.

    Devuelve lo que devuelva `abrir_preferencias` si el usuario acepta, o
    False si no quiere.
    """
    if wx.MessageBox("Tu sesión de YouTube caducó. ¿Abrir Preferencias para "
                     "volver a iniciar sesión?",
                     "Sesión caducada", wx.YES_NO | wx.ICON_QUESTION,
                     parent) != wx.YES:
        return False
    return abrir_preferencias(parent, config, pagina="API y sesión")
