"""Interfaz wxPython accesible: barra de menú nativa + paneles en notebook.

Rediseño: una sola ventana con barra de menú (que NVDA lee de forma nativa y
que muestra los atajos), barra superior con URL+Conectar, y un notebook con los
paneles Chat en vivo, Comentarios y Reproductor. Al conectar se detecta si la
URL es un directo o un vídeo subido y se ajustan los paneles.
"""

from __future__ import annotations

import logging
import random
import re
import threading
import time
import webbrowser
from datetime import datetime

import wx

from ytchat.core.config import (
    APP_NAME, APP_VERSION,
    TIPO_TEXTO, TIPO_SUPERCHAT, TIPO_STICKER, TIPO_MIEMBRO, TIPO_ENTRADA,
    TIPO_SEGUIR, TIPO_COMPARTIR, TIPO_COFRE,
    TIPO_ME_GUSTA,
    FILTROS,
)
from ytchat.core.config import (parsear_atajos, detectar_conflictos_atajos,
                    guardar_opcion)
from ytchat.core import paths
from ytchat.core import anuncio_ajuste
from ytchat.core import sonidos_eventos
from ytchat.capture import deteccion
from ytchat.capture import metadatos
from ytchat.capture import estado_sesion
from ytchat.core import historial
from ytchat.ui.lista_chat import ListaChat, MensajeChat
from ytchat.ui.busqueda_lista import buscar_prefijo, coincide
from ytchat.ui import atajos_captura
from ytchat.voice import escala_voz
from ytchat.voice import sound_player as _snd
from ytchat.youtube import credenciales
from ytchat.youtube import youtube_api
from ytchat.core import diagnostico
from ytchat.downloads import ytdlp_bin
from ytchat.core import apagado
from ytchat.obs import overlay_servidor
from ytchat.capture import programados
from ytchat.capture import descartes
from ytchat.capture import redaccion
from ytchat.capture import alias
from ytchat.obs import obs_audio
from ytchat.obs import obs_estado
from ytchat.obs import obs_vigilante
from ytchat.obs import obs_activacion
from ytchat.obs import obs_cliente
from ytchat.obs.obs_panel import GestorPanelObs
from ytchat.ui.gui_redactar import PanelRedactar

# Mapeo entre índice de FILTROS y clave persistida en config.ini.
_NOMBRES_FILTRO = ("todos", "texto", "superchat", "miembro")
_IDX_FILTRO     = {"todos": 0, "texto": 1, "superchat": 2, "miembro": 3}


MAX_ITEMS_CHAT  = 500
TIMER_STATUS_MS = 1000
TIMER_DIAGNOSTICO_MS = 100
# Ráfagas de mensajes del chat: en vez de un Append/Delete por mensaje (mucho
# repintado en el hilo de GUI mientras NVDA navega la lista), se agrupan y se
# vuelcan juntos cada tanto. Ver agregar_mensaje_chat / _volcar_pendientes.
MS_VOLCADO_CHAT = 120
ANCHO_DEFECTO   = 860
ALTO_DEFECTO    = 700

# Mensaje bajo la barra de URL cuando no hay conexión. Breve pero completo:
# qué se puede pegar y cómo conectar.
MENSAJE_INICIAL = ("Sin conectar. Pega un enlace de YouTube (directo o vídeo) o "
                   "de un directo de TikTok y pulsa Conectar (Alt+C). En YouTube "
                   "podrás leer el chat y los comentarios; en TikTok, el chat del "
                   "directo.")
RUTA_CONFIG = None  # se asigna en iniciar_gui() con paths.config_ini()
_URL_RE         = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)

# Índices de las páginas del notebook (solo chat y comentarios; el reproductor
# es una región fija, no una pestaña).
PAG_CHAT = 0
PAG_COMENTARIOS = 1

# Regiones que recorre F6 / Shift+F6.
REG_CONEXION = 0
REG_CONTENIDO = 1
REG_REPRODUCTOR = 2
_NOMBRE_REGION = ("Conexión", "Contenido", "Reproductor")

logger = diagnostico.obtener_logger(__name__)
_OBS_COMPONENTES = frozenset(("obs_transmision", "obs_grabacion", "obs_escena"))


# ── Lector de pantalla (Prism, opcional) ────────────────────────────────────
# Si Prism no está instalado o no hay un lector de pantalla activo, los
# `anunciar()` son no-ops silenciosos; la app funciona igual.

_lector = None


def _lector_init():
    global _lector
    try:
        from ytchat.voice.lector import Lector
        _lector = Lector()
        logger.info("Lector de pantalla: %s", _lector.nombre() or "ninguno")
    except Exception as exc:
        logger.warning("La aplicación se quedó sin salida para lector de pantalla: %s", exc)


def anunciar(texto: str, urgente: bool = True) -> None:
    if _lector is None:
        logger.info("ANUNCIO sin lector %s", texto)
        return
    if not wx.IsMainThread():
        # Prism habla por COM (JAWS) y no es seguro desde otros hilos; el
        # vigilante de OBS y las descargas anuncian desde los suyos, así que se
        # reenvía al hilo de la interfaz, que es donde se crea y se usa el
        # lector porque JAWS crea su COM ahí.
        try:    wx.CallAfter(anunciar, texto, urgente)
        except Exception: pass
        return
    logger.info("ANUNCIO %s", texto)
    try:
        # Casi todos responden a una tecla y deben llegar antes del próximo foco.
        _lector.speak(texto, interrupt=urgente)
    except Exception as exc:
        logger.warning("No se pudo anunciar con voz: %s", exc)
    # También a la línea braille, como hace TWBlue (output.speak): quien usa
    # pantalla braille sin voz recibe igualmente los anuncios de la app.
    try:
        _lector.braille(texto)
    except Exception:
        pass


def anunciar_conflictos_atajos(raw: dict | None) -> None:
    for perdedora, conservada, combinacion in detectar_conflictos_atajos(raw):
        anunciar(
            f"Conflicto de atajos: {perdedora} se quedó sin atajo porque "
            f"{conservada} usa {combinacion}.")


# ── Nombre accesible reforzado (MSAA) ─────────────────────────────────────────
# Patrón tomado de eleven-tts-studio: en Windows, `SetName` por sí solo no
# siempre lo anuncian NVDA/JAWS de forma fiable (sobre todo en deslizadores y en
# ventanas genéricas como la superficie de vídeo). Reforzamos con un
# `wx.Accessible` explícito que expone el nombre por MSAA. Solo se usa en los
# controles donde el nombre flojea; los estándar (botones, casillas) ya se leen
# bien con `name=` y no hace falta.

class _NombreAccesible(wx.Accessible):
    """Expone el nombre del control por MSAA. Solo nombra el control en sí
    (childId 0); las filas/hijos (p. ej. cada línea de una lista) las deja al
    proveedor por defecto, o todas se anunciarían con el nombre de la lista."""

    def __init__(self, nombre: str):
        super().__init__()
        self._nombre = nombre

    def GetName(self, childId):
        if childId == 0:
            return (wx.ACC_OK, self._nombre)
        return (wx.ACC_NOT_IMPLEMENTED, "")


def nombre_accesible(ctrl, nombre: str, msaa: bool = True) -> None:
    """Refuerza el nombre accesible de un control. Mantiene los tooltips ricos
    que ya tengamos (solo pone uno si falta) y no altera el rol ni el valor: el
    `wx.Accessible` solo sobrescribe el nombre y delega el resto.

    `msaa=False` se salta el `wx.Accessible` (deja SetName/tooltip/HelpText
    igual). Úsalo en listas de CONTENIDO DINÁMICO (chat, comentarios): al
    instalar un `wx.Accessible` en Python, TODAS las consultas MSAA de NVDA
    sobre ese control (también las de cada fila al navegar con flechas) pasan
    por el proxy de wx y el hilo de GUI. Con la lista recibiendo Append/Delete
    constantes por los mensajes que llegan, esas consultas se quedan esperando
    y la navegación se traba a trompicones. Las listas estáticas (voces,
    historial…) no sufren esto y siguen con el refuerzo."""
    ctrl.SetName(nombre)
    if not ctrl.GetToolTip():
        ctrl.SetToolTip(nombre)
    try:    ctrl.SetHelpText(nombre)   # JAWS lee el help text en algunos controles
    except Exception: pass
    if not msaa:
        return
    try:
        acc = _NombreAccesible(nombre)
        ctrl.SetAccessible(acc)
        ctrl._nombre_accesible = acc   # evita que el GC se lo lleve
    except Exception:
        pass  # fuera de Windows o sin MSAA: el name/tooltip siguen aplicando


def caja_de_grupo(panel, titulo):
    """Crea una caja y devuelve el sizer junto al padre de sus controles."""
    caja = wx.StaticBox(panel, label=titulo)
    return wx.StaticBoxSizer(caja, wx.VERTICAL), caja


# ── Búsqueda por prefijo (type-ahead) en listas de texto ────────────────────
# Estando en el chat o en comentarios, escribir letras seguidas salta al
# primer mensaje cuyo texto MOSTRADO («autor: mensaje…») empiece por eso, con
# buffer multiletra («mig» → «Miguel», no una letra a la vez) que se resetea
# solo tras un rato sin teclear. La lógica de búsqueda vive en
# `busqueda_lista.py` (pura, sin wx); esto solo engancha el evento y lleva el
# buffer/temporizador.

_MS_RESET_BUSQUEDA = 900


class _EstadoBusqueda:
    """Buffer de teclas y temporizador de reseteo de una lista. Uno por
    control (instalar_busqueda_tipo lo crea y lo cierra en un closure)."""

    def __init__(self):
        self.buffer = ""
        self.timer = None


def instalar_busqueda_tipo(listbox: wx.ListBox, obtener_textos) -> None:
    """Engancha en `listbox` el type-ahead sobre EVT_CHAR (aparte de
    EVT_KEY_DOWN, que ya usan estas listas para Enter/Ctrl+C/menú, para no
    pelearse con esos keycodes). `obtener_textos` es una función sin
    argumentos que devuelve, en orden de fila, el texto mostrado de cada
    ítem (normalmente `[listbox.GetString(i) for i in range(GetCount())]`).
    """
    estado = _EstadoBusqueda()

    def _resetear_buffer():
        estado.buffer = ""
        estado.timer = None

    def _on_char(event):
        # Combinaciones con Ctrl/Alt son atajos, no texto de búsqueda.
        if event.ControlDown() or event.AltDown():
            event.Skip()
            return
        code = event.GetUnicodeKey()
        if code == wx.WXK_NONE:
            event.Skip()
            return
        ch = chr(code)
        if not ch.isprintable():
            event.Skip()
            return
        if ch == " " and not estado.buffer:
            # Espacio con el buffer vacío: no es inicio de búsqueda, que se
            # comporte como en cualquier lista (no lo consumimos).
            event.Skip()
            return

        estado.buffer += ch
        if estado.timer is not None:
            try:    estado.timer.Stop()
            except Exception: pass
        estado.timer = wx.CallLater(_MS_RESET_BUSQUEDA, _resetear_buffer)

        textos = obtener_textos()
        if not textos:
            return
        actual = listbox.GetSelection()
        if (len(estado.buffer) > 1 and actual != wx.NOT_FOUND
                and 0 <= actual < len(textos)
                and coincide(textos[actual], estado.buffer)):
            return   # el seleccionado ya cumple: no mover nada
        desde = (actual + 1) if actual != wx.NOT_FOUND else 0
        idx = buscar_prefijo(textos, desde, estado.buffer)
        if idx is not None:
            listbox.SetSelection(idx)
            # NVDA no siempre anuncia una selección puesta por programa.
            anunciar(textos[idx])
        else:
            # Que quien busca sepa que se buscó (en toda la lista, dando la
            # vuelta) y no hubo nada; se descarta la última letra para poder
            # seguir completando la búsqueda anterior.
            anunciar(f"No hay coincidencias con {estado.buffer}")
            estado.buffer = estado.buffer[:-1]

    listbox.Bind(wx.EVT_CHAR, _on_char)


# ── Paleta «crema + salvia» (ver docs/PALETA-COLORES.md) ─────────────────────
# Fondo crema, salvia como color de marca y muy pocos tonos con papel fijo.
# `accent` y `red` son colores de TEXTO (secciones, estados, errores), no
# fondos: son la salvia y el rojo oscurecidos lo justo para dar 4.5:1 sobre
# el fondo. Contraste comprobado con la fórmula WCAG en cada par texto/fondo
# real de la app; todos dan 4.5:1 o más. Con el contraste alto de Windows
# activado (ALTO_CONTRASTE) la paleta no se aplica y manda el tema del sistema.

class _T:
    bg      = wx.Colour(247, 244, 238)  # #F7F4EE  crema (fondo de marca)
    surface = wx.Colour(255, 255, 255)  # #FFFFFF  paneles, grupos, pestañas
    field   = wx.Colour(233, 225, 211)  # #E9E1D3  campos (secundario/beige)
    text    = wx.Colour(51,  51,  51)   # #333333  texto principal
    dim     = wx.Colour(107, 107, 107)  # #6B6B6B  texto secundario
    accent  = wx.Colour(63,  91,  58)   # #3F5B3A  salvia oscurecida (primario, texto)
    red     = wx.Colour(179, 38,  30)   # #B3261E  error
    btn     = wx.Colour(233, 225, 211)  # botones secundarios (= field)
    btn_t   = wx.Colour(51,  51,  51)
    # Botón primario (Conectar): salvia tal cual del md, texto oscuro encima.
    primary   = wx.Colour(202, 215, 197)  # #CAD7C5  salvia (marca, sin oscurecer)
    primary_t = wx.Colour(51,  51,  51)


def _detectar_alto_contraste() -> bool:
    """¿Windows tiene activado un tema de alto contraste? (SPI_GETHIGHCONTRAST)"""
    try:
        import ctypes

        class _HighContrast(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwFlags", ctypes.c_uint),
                        ("lpszDefaultScheme", ctypes.c_wchar_p)]

        datos = _HighContrast()
        datos.cbSize = ctypes.sizeof(_HighContrast)
        if ctypes.windll.user32.SystemParametersInfoW(
                0x42, datos.cbSize, ctypes.byref(datos), 0):   # SPI_GETHIGHCONTRAST
            return bool(datos.dwFlags & 1)                      # HCF_HIGHCONTRASTON
    except Exception:
        pass
    return False


# Con alto contraste la paleta propia pisaría los colores que el usuario eligió
# precisamente para ver: en ese caso no se pinta nada y mandan los del sistema.
ALTO_CONTRASTE = _detectar_alto_contraste()


def _pintar(w, bg=None, fg=None):
    """Aplica colores de la paleta a un control, salvo en alto contraste."""
    if ALTO_CONTRASTE:
        return
    if bg is not None:
        w.SetBackgroundColour(bg)
    if fg is not None:
        w.SetForegroundColour(fg)


def _tc(w, bg=None, fg=None):
    _pintar(w, bg or _T.field, fg or _T.text)


class ContadorAccesible(wx.SpinCtrl):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.Bind(wx.EVT_SET_FOCUS, self._on_focus)

    def _on_focus(self, event):
        # Selecciona el valor para reemplazarlo sin borrarlo antes.
        self.SetSelection(0, len(self.GetTextValue()))
        event.Skip()


def _titulo(w, color=None):
    """Etiqueta de sección: color de acento y seminegrita, para jerarquía."""
    _pintar(w, fg=color or _T.accent)
    w.SetFont(w.GetFont().Bold())


_ACCEL_NOMBRES = {
    "ctrl": "Ctrl", "alt": "Alt", "shift": "Shift",
    "enter": "Enter", "left": "Left", "right": "Right",
    "up": "Up", "down": "Down", "space": "Space", "end": "End",
}


def _fmt_accel(texto: str) -> str:
    """'f5'->'F5', 'ctrl+left'->'Ctrl+Left', 'alt+enter'->'Alt+Enter'.

    Formato que entiende wx para los aceleradores de menú.
    """
    if not texto:
        return ""
    partes = []
    for p in texto.split("+"):
        partes.append(_ACCEL_NOMBRES.get(p, p.upper()))
    return "+".join(partes)


class WxAnnouncingHandler(logging.Handler):
    """Reenvía los mensajes del logger al lector de pantalla."""

    def __init__(self):
        super().__init__()
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record):
        if not registro_es_anunciable(record.name):
            return
        try:    anunciar(self.format(record))
        except Exception: pass


# Lista blanca: solo estos loggers llegan al lector. Lo no listado se registra
# pero no se habla, para que un logger.info nuevo no se convierta en voz por descuido.
_LOGGERS_ANUNCIABLES = frozenset({
    "ytchat.obs_vigilante",  # avisa cuando OBS vuelve a responder
})


def registro_es_anunciable(nombre_logger: str | None) -> bool:
    """Decide si un registro del log debe llegar al lector de pantalla."""
    # Lista blanca: solo lo explicitamente permitido se habla; lo desconocido se calla.
    return bool(nombre_logger) and nombre_logger in _LOGGERS_ANUNCIABLES


class _LogWx(wx.Log):
    """Reenvia el log de wx al logger del modulo sin recortar el texto."""

    def DoLogRecord(self, level, msg, info):
        try:
            # Mensaje entero, sin recortar: es lo unico para diagnosticar
            if level in (wx.LOG_FatalError, wx.LOG_Error, wx.LOG_Warning):
                logger.warning("wx: %s", msg)
            else:
                logger.debug("wx: %s", msg)
        except Exception:
            pass


# ── Frame principal ──────────────────────────────────────────────────────────

def mensaje_confirmar_salida(confirmar_salida: bool, chat_conectado: bool,
                             supervisor_activo: bool,
                             obs_transmitiendo: bool) -> str | None:
    """Mensaje para preguntar antes de salir, o None si no hay que preguntar.

    Pura y sin wx: recibe la opción y los tres estados y decide. Lo
    importante va primero, en tono de herramienta.
    """
    if not confirmar_salida:
        return None
    transmision = bool(supervisor_activo or obs_transmitiendo)
    if chat_conectado and transmision:
        return ("¿Salir de la aplicación? Hay un chat conectado y una "
                "transmisión en curso.")
    if chat_conectado:
        return "¿Salir de la aplicación? Hay un chat conectado."
    if transmision:
        return "¿Salir de la aplicación? Hay una transmisión en curso."
    return None


class YTChatFrame(wx.Frame):

    def __init__(self, parent, config, cola, stats, worker, parada):
        super().__init__(
            parent,
            title=f"{APP_NAME} v{APP_VERSION}",
            size=(ANCHO_DEFECTO, ALTO_DEFECTO),
            name="VentanaPrincipal",
        )
        # Piso de la ventana: sin esto, se podía achicar hasta el punto de
        # aplastar el chat, el reproductor y los textos, cortándolos.
        try:
            self.SetMinSize((640, 480))
        except Exception:
            pass
        self._config    = config
        self._cola      = cola
        self._stats     = stats
        self._worker    = worker
        self._parada    = parada
        self._alive     = True
        self._apagando  = False
        self._conectado = False
        self._conectando = False   # entre pulsar Conectar y la respuesta
        self._texto_tipo = MENSAJE_INICIAL   # texto de lbl_tipo sin saltos de Wrap
        self._titulo_stream = ""
        self._tipo_video = deteccion.DESCONOCIDO
        self._es_tiktok = False   # para que F2 distinga TikTok de YouTube (ambos LIVE)
        self._usuario_tiktok_sesion = ""   # usuario del directo conectado
        self._conexion_propia = False   # la pidió la transmisión
        self._chat_propio = False   # el directo conectado es del canal propio
        self._obs_transmitiendo = False   # OBS emite sin supervisor a la vista
        self._descartes_avisado = False

        self._chat = ListaChat(MAX_ITEMS_CHAT)
        self._filtro = None
        # Cola de mensajes entrantes aún no volcados a lb_chat/self._chat, y el
        # temporizador que programa el volcado agrupado (ver MS_VOLCADO_CHAT).
        self._pendientes: list[MensajeChat] = []
        self._pendientes_timer = None

        self._sc_totales: dict[str, float] = {}
        self._live_chat_id = ""
        self._video_id_sesion = ""   # vídeo de YouTube de la conexión vigente
        self._enlace_directo = ""   # URL del directo conectado, solo si es live
        self._causa_sin_chat = ""
        self._mensajes_programados = programados.cargar(
            paths.mensajes_programados())
        self._programados_reloj_iniciado = False
        self._programados_ultimo_envio = None
        self._programado_en_curso = False

        # Voz activa (antes era un wx.Choice; ahora es un submenú de radio).
        self._voz_idx = 0
        self._voz_nombre = "—"

        self.on_conectar_cb    = None
        self.on_desconectar_cb = None

        self._atajos = parsear_atajos(config.get("atajos_raw", {}))
        anunciar_conflictos_atajos(config.get("atajos_raw", {}))
        self._diagnostico_marca = time.monotonic()
        self._diagnostico_censo = self._diagnostico_marca
        self._diagnostico_parada = threading.Event()
        self._obs_vigilante = None
        self._supervisor = None
        self._descripcion_escena_en_curso = False

        _pintar(self, bg=_T.bg)
        self._build_menubar()
        if self._config.get("overlay_activo", False):
            self._cambiar_overlay(True)
        self._build_ui()
        self._bind_events()
        self._init_timer()
        self._actualizar_vigilante_obs()
        diagnostico.crear_hilo(
            lambda: diagnostico.vigilar_hilo_interfaz(
                lambda: self._diagnostico_marca, self._diagnostico_parada),
            "VigilanteInterfaz").start()
        self.Centre()

    # ── Barra de menú ────────────────────────────────────────────────────────

    def _accel(self, accion: str) -> str:
        at = self._atajos.get(accion)
        return ("\t" + _fmt_accel(at.texto)) if at else ""

    def _bind_menu(self, item, fn, *args):
        """Difiere el anuncio hasta que el menú se cerró y volvió el foco."""
        if isinstance(item, tuple):
            menu, identificador = item
            menu.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(fn, *args), id=identificador)
        else:
            self.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(fn, *args), item)

    def _build_menubar(self):
        from ytchat.ui import gui_menu
        gui_menu.construir_menu(self)

    def _sincronizar_pausa(self) -> None:
        try:    pausado = bool(self._worker.esta_pausado())
        except Exception: return
        self.mi_pausa.SetItemLabel(
            ("&Reanudar lectura" if pausado else "&Pausar lectura") + self._accel("pausa"))

    def _cambiar_overlay(self, encender):
        from ytchat.ui import gui_transmitir
        return gui_transmitir.cambiar_overlay(self, encender)

    def _guardar_usuario_tiktok(self, usuario):
        from ytchat.ui import gui_transmitir
        return gui_transmitir.guardar_usuario_tiktok(self, usuario)

    def _guardar_destino_transmision(self, destino):
        from ytchat.ui import gui_transmitir
        return gui_transmitir.guardar_destino_transmision(self, destino)

    def _alternar_aviso_sobrecarga(self):
        from ytchat.ui import gui_transmitir
        gui_transmitir.alternar_aviso_sobrecarga(self)

    def _guardar_datos_directo_youtube(self, titulo, descripcion, privacidad,
                                        latencia=None, ninos=False, dvr=True,
                                        categoria="", etiquetas=None,
                                        miniatura="", lista="",
                                        lista_titulo=""):
        from ytchat.ui import gui_transmitir
        return gui_transmitir.guardar_datos_directo_youtube(
            self, titulo, descripcion, privacidad, latencia, ninos, dvr,
            categoria, etiquetas, miniatura, lista, lista_titulo)

    def _actualizar_boton_directo(self) -> None:
        from ytchat.ui import gui_transmitir
        gui_transmitir.actualizar_boton_directo(self)

    def _al_terminar_supervisor(self) -> None:
        from ytchat.ui import gui_transmitir
        gui_transmitir.al_terminar_supervisor(self)

    def _supervisar_transmision(self, accion, destino="", usuario="",
                                  revision=None):
        from ytchat.ui import gui_transmitir
        return gui_transmitir.supervisar_transmision(
            self, accion, destino, usuario, revision)

    def _on_actualizar_ytdlp(self, event):
        from ytchat.ui import gui_actualizar_ytdlp
        gui_actualizar_ytdlp.abrir_ventana_actualizacion(self)

    def _on_actualizar_app(self, event):
        from ytchat.ui import gui_actualizar_app
        gui_actualizar_app.abrir_ventana_actualizacion(self)

    # ── Construcción de la UI ────────────────────────────────────────────────

    def _build_ui(self):
        # Importes diferidos para evitar el ciclo (esos módulos importan de gui).
        from ytchat.ui.gui_comentarios import ComentariosPanel
        from ytchat.player.reproductor import ReproductorPanel

        panel = wx.Panel(self, name="PanelPrincipal")
        _pintar(panel, _T.bg, _T.text)
        vs = wx.BoxSizer(wx.VERTICAL)

        # ── Barra superior: URL + tipo + Conectar ──
        row = wx.BoxSizer(wx.HORIZONTAL)
        lbl = wx.StaticText(panel, label="&URL/ID:", name="EtiquetaURL")
        _titulo(lbl)
        row.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.txt_url = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER, name="URL del directo o vídeo")
        _tc(self.txt_url)
        self.txt_url.SetToolTip(
            "Enlace de YouTube (directo o vídeo) o de un directo de TikTok "
            "(tiktok.com/@usuario/live). También vale el ID de 11 caracteres de "
            "YouTube. Pulsa Enter para conectar.")
        row.Add(self.txt_url, 1, wx.EXPAND | wx.RIGHT, 8)
        self.btn_conectar = wx.Button(panel, label="&Conectar", name="Conectar")
        _pintar(self.btn_conectar, _T.primary, _T.primary_t)
        self.btn_conectar.SetFont(self.btn_conectar.GetFont().Bold())
        row.Add(self.btn_conectar, 0, wx.ALIGN_CENTER_VERTICAL)
        from ytchat.ui.boton_directo import BotonDirecto
        self._boton_directo = BotonDirecto(panel, self.btn_conectar, self)
        row.Add(self._boton_directo.boton, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
        vs.Add(row, 0, wx.EXPAND | wx.ALL, 12)

        self.lbl_tipo = wx.StaticText(panel, label=self._texto_tipo, name="TipoVideo")
        _pintar(self.lbl_tipo, fg=_T.dim)
        # Ancho mínimo fijo: si no, el mínimo del sizer (y el piso de la
        # ventana) seguiría al texto sin partir, es decir, al ancho actual.
        self.lbl_tipo.SetMinSize((200, -1))
        self.lbl_tipo.Wrap(ANCHO_DEFECTO - 40)
        vs.Add(self.lbl_tipo, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # ── Zona de contenido: notebook + reproductor. Se oculta hasta que hay
        # conexión y se vuelve a ocultar al desconectar (queda solo la barra
        # superior), para que no aparezca todo a medio cargar. ──
        self._zona = wx.Panel(panel, name="ZonaContenido")
        _pintar(self._zona, bg=_T.bg)
        zvs = wx.BoxSizer(wx.VERTICAL)

        self.nb = wx.Notebook(self._zona, name="Paneles")
        _tc(self.nb, bg=_T.surface)
        self._pag_chat = self._build_pagina_chat(self.nb)
        self._com_panel = ComentariosPanel(self.nb, self._cola, self._config)
        self.nb.AddPage(self._pag_chat, "Chat en vivo")
        self.nb.AddPage(self._com_panel, "Comentarios")
        # Pestaña de información del vídeo (solo lectura). Se añade SIEMPRE al
        # final, para no alterar los índices de Chat/Comentarios, y se puede
        # ocultar por preferencia. La rellena set_metadatos con lo de yt-dlp.
        self._pag_info = self._build_pagina_info(self.nb)
        self._metadatos = {}
        if bool(self._config.get("mostrar_metadatos", True)):
            self.nb.AddPage(self._pag_info, "Información")
        else:
            self._pag_info.Hide()
        # Piso para que la lista del chat, los comentarios y la información no
        # queden aplastados por el reproductor en ventanas bajas: 170 dejaba
        # ver 2-3 mensajes; con esto se ven varios más sin tocar el reproductor.
        self.nb.SetMinSize((-1, 260))
        zvs.Add(self.nb, 3, wx.EXPAND | wx.BOTTOM, 10)

        # Proporción 3/2 (antes el reproductor iba fijo en 0): chat y reproductor
        # comparten el alto sobrante con algo más de peso para el chat —que tiene
        # menos mínimo— para que queden equilibrados; el vídeo crece al agrandar la
        # ventana en vez de quedar fijo y comerse el espacio del chat.
        self._rep_panel = ReproductorPanel(self._zona, self._config)
        # Al alternar los botones del reproductor (desde su interruptor o el menú),
        # sincronizamos la casilla del menú y persistimos la preferencia.
        self._rep_panel.on_botones_toggle = self._on_botones_rep_cambio
        zvs.Add(self._rep_panel, 2, wx.EXPAND)

        self._zona.SetSizer(zvs)
        vs.Add(self._zona, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self._zona.Hide()

        panel.SetSizer(vs)
        self._panel_principal = panel

        # Control de la música: nace sin tocar VLC ni el disco.
        from ytchat.ui import gui_musica
        self._musica = gui_musica.ControlMusica(self)

        # Regiones que recorre F6 / Shift+F6.
        self._region_idx = REG_CONTENIDO
        self._regiones = [
            lambda: self.txt_url.SetFocus(),
            self._foco_contenido,
            self._rep_panel.anclar_foco,
        ]

        # 7 campos: estado, velocidad, voz, cola, leídos, volumen, total SC.
        self.sb = self.CreateStatusBar(7, name="BarraEstado")
        # (Sin fondo: la barra de estado nativa lo ignora.)
        _pintar(self.sb, fg=_T.dim)
        self.sb.SetStatusWidths([-3, -1, -3, -1, -1, -1, -2])
        self._actualizar_sb()
        self._set_conectado_ui(False)   # estado inicial: desconectado

    def _build_pagina_chat(self, parent) -> wx.Panel:
        pag = wx.Panel(parent, name="PaginaChat")
        _pintar(pag, _T.bg, _T.text)
        vs = wx.BoxSizer(wx.VERTICAL)

        lbl = wx.StaticText(pag, label="Mensajes del chat:", name="EtiquetaChat")
        _titulo(lbl)
        vs.Add(lbl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)

        self.lb_chat = wx.ListBox(
            pag, style=wx.LB_SINGLE | wx.LB_HSCROLL, name="Chat en vivo")
        _tc(self.lb_chat)
        pt = int(self._config.get("tamanio_fuente_chat", 12))
        self.lb_chat.SetFont(wx.Font(
            pt, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        self.lb_chat.SetToolTip(
            "Mensajes del chat. Enter copia el mensaje. "
            "Tecla aplicaciones abre el menú contextual.")
        # msaa=False: ver el porqué en nombre_accesible() (lista dinámica).
        nombre_accesible(self.lb_chat, "Chat en vivo", msaa=False)
        vs.Add(self.lb_chat, 1, wx.EXPAND | wx.ALL, 8)

        self._panel_redactar = PanelRedactar(
            pag, "&Mensaje:", redaccion.MAXIMO_CHAT, self._enviar_live_redactado)
        vs.Add(self._panel_redactar, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        pag.SetSizer(vs)
        self._actualizar_motivo_redaccion()
        return pag

    def _build_pagina_info(self, parent) -> wx.Panel:
        pag = wx.Panel(parent, name="PaginaInfo")
        _pintar(pag, _T.bg, _T.text)
        vs = wx.BoxSizer(wx.VERTICAL)

        lbl = wx.StaticText(pag, label="Información del vídeo:", name="EtiquetaInfo")
        _titulo(lbl)
        vs.Add(lbl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)

        # Solo lectura y multilínea. TE_AUTO_URL (con TE_RICH2, necesario en
        # Windows) hace clicables los enlaces de la descripción SIN romper la
        # lectura con NVDA, que recorre el cuadro como texto normal (flechas,
        # selección, copiar). Es la opción accesible frente a un wx.html.
        self.txt_info = wx.TextCtrl(
            pag, value="", name="Información del vídeo",
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_AUTO_URL | wx.TE_RICH2)
        _tc(self.txt_info)
        self.txt_info.SetToolTip(
            "Datos del vídeo: canal, vistas, descripción. Solo lectura. Los "
            "enlaces se abren con clic o se copian y pegan en el navegador.")
        vs.Add(self.txt_info, 1, wx.EXPAND | wx.ALL, 8)

        pag.SetSizer(vs)
        self.txt_info.Bind(wx.EVT_TEXT_URL, self._on_info_url)
        return pag

    def _on_info_url(self, event):
        # TE_AUTO_URL dispara este evento para CADA movimiento del ratón sobre el
        # enlace; abrir solo al soltar el botón izquierdo (si no, abriría a cada
        # paso del cursor).
        mouse = event.GetMouseEvent()
        if mouse.LeftUp():
            url = self.txt_info.GetRange(event.GetURLStart(), event.GetURLEnd())
            if url:
                webbrowser.open(url)
        else:
            event.Skip()

    # ── Enlaces de eventos ───────────────────────────────────────────────────

    def _bind_events(self):
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_ACTIVATE, self._on_activate)
        # En el panel, no en el frame: cuando el frame recibe EVT_SIZE el panel
        # aún tiene el tamaño viejo y cada Wrap iba un evento tarde.
        self._panel_principal.Bind(wx.EVT_SIZE, self._on_resize)
        self.btn_conectar.Bind(wx.EVT_BUTTON, self._on_conectar)
        self.txt_url.Bind(wx.EVT_TEXT_ENTER,  self._on_conectar)
        self.nb.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_nb_page)
        self.lb_chat.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._copiar_mensaje())
        self._enlazar_eventos_chat()
        instalar_busqueda_tipo(
            self.lb_chat,
            lambda: [self.lb_chat.GetString(i) for i in range(self.lb_chat.GetCount())])

    def _enlazar_eventos_chat(self):
        self.lb_chat.Bind(wx.EVT_KEY_DOWN, self._on_chat_key)
        self.lb_chat.Bind(wx.EVT_CHAR_HOOK, self._on_chat_char_hook)
        self.lb_chat.Bind(wx.EVT_CONTEXT_MENU, self._on_chat_menu)

    def _on_nb_page(self, event):
        # No hay anuncio nativo del cambio de pestaña: lo decimos a mano.
        idx = event.GetSelection()
        if 0 <= idx < self.nb.GetPageCount():
            anunciar(self.nb.GetPageText(idx))
        event.Skip()

    def _on_resize(self, event):
        # Primero el Wrap y luego Skip: así el Layout por defecto del panel ya
        # cuenta con la altura nueva de la etiqueta.
        self._ajustar_ancho_tipo()
        event.Skip()

    def _ajustar_ancho_tipo(self) -> None:
        """Reajusta el salto de línea de lbl_tipo al ancho disponible: con
        Wrap() fijo, ensanchar o angostar la ventana dejaba el texto cortado
        o con un hueco de sobra en vez de acomodarse."""
        if not hasattr(self, "lbl_tipo"):
            return
        try:
            ancho = max(200, self.lbl_tipo.GetParent().GetClientSize().Width - 20)
            # Wrap() solo parte: mete saltos de línea literales que GetLabel
            # conserva, así que al ensanchar el texto se quedaba troceado. Se
            # parte siempre desde el texto original.
            self.lbl_tipo.SetLabel(self._texto_tipo)
            self.lbl_tipo.Wrap(ancho)
        except Exception:
            pass

    def _fijar_tipo(self, texto: str) -> None:
        self._texto_tipo = texto
        self._ajustar_ancho_tipo()
        try:    self._panel_principal.Layout()
        except Exception: pass

    def _ajustar_minimo_ventana(self) -> None:
        """Piso real de la ventana: lo que pide el sizer (con el reproductor a
        la vista ronda los 850 px de alto, muy por encima de 640×480, y el
        vídeo quedaba cortado por abajo). Se limita a la pantalla y, si la
        ventana era más chica, se agranda para que quepa todo."""
        try:
            minimo = self._panel_principal.GetSizer().GetMinSize()
            area = wx.Display(self).GetClientArea()
            # Descontar título, menú, barra de estado y bordes.
            ancho = max(640, min(minimo.width, area.width - 40))
            alto = max(480, min(minimo.height, area.height - 110))
            self.SetMinClientSize((ancho, alto))
            actual = self.GetClientSize()
            if self.IsMaximized() or (actual.width >= ancho and actual.height >= alto):
                return
            self.SetClientSize((max(actual.width, ancho), max(actual.height, alto)))
            rect = self.GetRect()
            x = max(area.x, min(rect.x, area.right - rect.width))
            y = max(area.y, min(rect.y, area.bottom - rect.height))
            if (x, y) != (rect.x, rect.y):
                self.Move((x, y))
        except Exception as exc:
            logger.debug("ajustar mínimo de la ventana: %s", exc)

    def _on_activate(self, event):
        if event.GetActive() and self._alive:
            # Diferido: wx repone el foco en el último control tras este evento.
            wx.CallAfter(self._foco_al_activar)
        event.Skip()

    def _foco_al_activar(self) -> None:
        """Al volver a la app, llevar el foco al contenido (o a la URL si no hay
        conexión) SOLO si no quedó ya en un control de la ventana: al cerrarse
        un diálogo o un aviso, el usuario vuelve a donde estaba (reproductor,
        redacción…) y no hay que arrastrarlo al chat."""
        if not self._alive:
            return
        foco = wx.Window.FindFocus()
        if foco is not None and self._es_descendiente(foco):
            return
        if self._conectado:
            self._foco_contenido()
        else:
            self.txt_url.SetFocus()

    def _es_descendiente(self, ventana) -> bool:
        while ventana is not None:
            if ventana is self:
                return True
            try:    ventana = ventana.GetParent()
            except Exception: return False
        return False

    def _init_timer(self):
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_timer, self._timer)
        self._timer.Start(TIMER_STATUS_MS)
        self._diagnostico_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_diagnostico_timer, self._diagnostico_timer)
        self._diagnostico_timer.Start(TIMER_DIAGNOSTICO_MS)

    def _arrancar_precalentamiento(self) -> None:
        if self._alive:
            self._rep_panel._precalentar()

    # ── Navegación de paneles ────────────────────────────────────────────────

    def _navegar_region(self, delta: int):
        if not self._conectado:
            self.txt_url.SetFocus()
            anunciar("Conéctate primero para usar los paneles")
            return
        self._region_idx = (self._region_idx + delta) % len(self._regiones)
        self._ir_region(self._region_idx)

    def _ir_region(self, idx: int):
        if not (0 <= idx < len(self._regiones)):
            return
        if idx != REG_CONEXION and not self._conectado:
            anunciar("Conéctate primero para usar los paneles")
            return
        self._region_idx = idx
        try:    self._regiones[idx]()
        except Exception as exc: logger.debug("ir_region %d: %s", idx, exc)
        nombre = _NOMBRE_REGION[idx]
        if idx == REG_CONTENIDO:
            nombre += f": {self.nb.GetPageText(self.nb.GetSelection())}"
        anunciar(nombre)

    def _ir_lista(self):
        """Alt+L: foco directo a la lista de la pestaña actual (chat o comentarios)."""
        if not self._conectado:
            anunciar("Conéctate primero")
            return
        self._region_idx = REG_CONTENIDO
        self._foco_contenido()

    def _foco_contenido(self):
        pag = self.nb.GetCurrentPage()
        if pag is self._pag_chat:
            self.lb_chat.SetFocus()
        elif pag is self._com_panel:
            self._com_panel.anclar_foco()
        elif pag is self._pag_info:
            self.txt_info.SetFocus()
        else:
            self.nb.SetFocus()

    def _ir_pestana(self, idx: int):
        """Selecciona una pestaña del notebook y deja el foco en su contenido."""
        if 0 <= idx < self.nb.GetPageCount():
            # ChangeSelection no dispara EVT_NOTEBOOK_PAGE_CHANGED (SetSelection
            # sí): si no, _on_nb_page anunciaba la pestaña y aquí otra vez.
            self.nb.ChangeSelection(idx)
            self._region_idx = REG_CONTENIDO
            self._foco_contenido()
            anunciar(self.nb.GetPageText(idx))

    def _rep_accion(self, metodo: str, *args):
        if getattr(self, "_rep_panel", None) is None:
            anunciar("El reproductor no está disponible")
            return
        try:
            getattr(self._rep_panel, metodo)(*args)
        except Exception as exc:
            logger.debug("acción reproductor %s: %s", metodo, exc)

    def _toggle_botones_rep(self):
        """Desde el menú: alterna los botones del reproductor. El panel avisa de
        vuelta (on_botones_toggle → _on_botones_rep_cambio) para sincronizar."""
        try:    self._rep_panel.alternar_botones()
        except Exception as exc:
            logger.debug("alternar botones reproductor: %s", exc)

    def _on_botones_rep_cambio(self, visibles: bool):
        """El panel cambió la visibilidad de los botones (por su interruptor o por
        el menú): sincronizar la casilla del menú y guardar la preferencia."""
        try:    self.mi_rep_botones.Check(bool(visibles))
        except Exception: pass
        self._config["mostrar_botones_reproductor"] = bool(visibles)
        guardar_opcion(RUTA_CONFIG, "ui", "mostrar_botones_reproductor",
                       "true" if visibles else "false")

    # ── Historial de directos ────────────────────────────────────────────────

    def _ruta_historial(self):
        return paths.historial_lives()

    def registrar_historial(self, plataforma: str, clave: str, url: str,
                            titulo: str, canal: str, directo: bool = False) -> None:
        """Guarda (o actualiza) una entrada del historial al conectar con éxito.
        Lo llama main vía wx.CallAfter cuando ya tiene título y canal."""
        if not self._alive or not clave:
            return
        try:
            ruta = self._ruta_historial()
            lista = historial.upsert(historial.cargar(ruta), plataforma, clave,
                                     url, titulo, canal, directo=directo)
            historial.guardar(ruta, lista)
            # Solo un directo deja enlace copiable; un vídeo grabado lo vacía.
            if directo:
                self._enlace_directo = url
            else:
                self._enlace_directo = ""
        except Exception as exc:
            logger.debug("registrar historial: %s", exc)

    def _on_historial(self):
        from ytchat.ui.gui_historial import abrir_historial
        abrir_historial(self, self._ruta_historial(),
                        self._reconectar_desde_historial)

    def _reconectar_desde_historial(self, url: str) -> None:
        """Desde el historial: si hay una sesión, desconecta; luego pone la URL
        elegida y conecta."""
        if not url:
            return
        if self._conectado:
            if self.on_desconectar_cb:
                try:    self.on_desconectar_cb()
                except Exception: pass
            self.set_conectado(False)
        self.txt_url.SetValue(url)
        wx.CallAfter(self._on_conectar, None)

    # ── Handlers de conexión ─────────────────────────────────────────────────

    def _conectar_si_procede(self):
        if not self._conectado:
            self._on_conectar(None)

    def _desconectar_si_procede(self):
        if self._conectado or self._conectando:
            self._on_conectar(None)

    def _on_conectar(self, event):
        if self._conectado or self._conectando:
            # Desconectar o, si aún estaba «Conectando…», cancelar: el callback
            # cierra la sesión y lo que devuelva ese hilo se descarta.
            cancelando = not self._conectado
            if self.on_desconectar_cb:
                self.on_desconectar_cb()
            self.set_conectado(False)
            if cancelando:
                anunciar("Conexión cancelada")
                self.txt_url.SetFocus()
        else:
            url = self.txt_url.GetValue().strip()
            if not url:
                wx.MessageBox("Introduce una URL o ID de YouTube.",
                              "Falta URL", wx.OK | wx.ICON_WARNING, self)
                self.txt_url.SetFocus()
                return
            self._conectando = True
            # El botón y «Desconectar» siguen activos para poder cancelar una
            # conexión que no responde.
            self.btn_conectar.SetLabel("&Cancelar conexión")
            self.btn_conectar.Enable()
            self.mi_conectar.Enable(False)
            self.mi_desconectar.Enable(True)
            self.txt_url.Disable()
            _snd.reproducir("conectando")
            anunciar("Conectando")
            if self.on_conectar_cb:
                self.on_conectar_cb(url)
            self._actualizar_boton_directo()

    def url_invalida(self):
        """La URL/ID no es válida: restaurar la UI y avisar (sin esperas)."""
        if not self._alive:
            return
        _snd.reproducir("error")
        self._set_conectado_ui(False)
        anunciar("La URL o el ID de YouTube no es válido")
        self.txt_url.SetFocus()
        wx.MessageBox("La URL o el ID de YouTube no es válido. Revisa lo que pegaste.",
                      "URL no válida", wx.OK | wx.ICON_WARNING, self)

    def _on_preferencias(self, event):
        try:
            from ytchat.ui.gui_preferencias import abrir_preferencias
            avisos = []
            acepto = abrir_preferencias(self, self._config, avisos=avisos)
            # La lista ya se guardó en disco al tocar sus botones: se relee
            # haya aceptado o no, y el reloj se arma de nuevo con la lista nueva.
            self._mensajes_programados = programados.cargar(
                paths.mensajes_programados())
            self._programados_reloj_iniciado = False
            if acepto:
                # El anuncio se difiere para que NVDA termine de decir el foco
                # de la ventana principal antes de hablar, y sin interrumpir lo
                # que diga _aplicar_preferencias_en_caliente.
                def _aplicar_y_avisar():
                    if not self._alive:
                        return
                    self._aplicar_preferencias_en_caliente()
                    if avisos:
                        anunciar(" ".join(avisos), urgente=False)
                wx.CallLater(300, _aplicar_y_avisar)
        except Exception as exc:
            logger.warning("No se pudo abrir preferencias: %s", exc)
            wx.MessageBox(f"No se pudo abrir Preferencias:\n{exc}",
                          "Error", wx.OK | wx.ICON_ERROR, self)
        # La pestaña API puede haber cambiado la sesión: refrescar.
        self._actualizar_estado_online()

    def _on_transmision(self, event):
        from ytchat.ui.gui_transmision import abrir_transmision
        abrir_transmision(self, self._cambiar_overlay,
                          supervisar=self._supervisar_transmision,
                          guardar_usuario=self._guardar_usuario_tiktok,
                          usuario_tiktok=self._config.get("tiktok_usuario", ""),
                          guardar_destino=self._guardar_destino_transmision)

    def _on_obs_micro(self, event):
        def _alternar():
            gestor = None
            try:
                gestor = GestorPanelObs()
                gestor.conectar()
                fuente = obs_audio.elegir_microfono(
                    gestor.fuentes_audio(), self._config.get("obs_microfono", ""))
                silenciada = gestor.alternar_silencio(fuente) if fuente else False
                texto = obs_audio.frase_microfono(fuente, silenciada)
            except Exception:
                texto = ("OBS no responde. En OBS, menú Herramientas, Configuración "
                         "del servidor WebSocket, activa el servidor.")
            finally:
                if gestor is not None:
                    try:
                        gestor.cerrar()
                    except Exception:
                        pass
            wx.CallAfter(anunciar, texto)

        diagnostico.crear_hilo(_alternar, "MicrofonoObs").start()

    # ── Gestor de descargas (gui_descargas) ──────────────────────────────────
    # Abre el diálogo siempre (no requiere conexión). Si le llega una URL, la
    # precarga (caso "Descargar este vídeo"). Importamos gui_descargas perezoso
    # para que el ciclo de imports (gui → gui_descargas → gui) no se queje.

    def _abrir_descargas(self, url: str | None = None) -> None:
        try:
            from ytchat.ui.gui_descargas import abrir
        except Exception as exc:
            logger.warning("No se pudo abrir el gestor de descargas: %s", exc)
            wx.MessageBox(f"No se pudo abrir el gestor de descargas:\n{exc}",
                          "Error", wx.OK | wx.ICON_ERROR, self)
            return
        try:
            abrir(self, url_inicial=url)
        except Exception as exc:
            logger.warning("gestor de descargas: %s", exc)
            wx.MessageBox(f"Error en el gestor de descargas:\n{exc}",
                          "Error", wx.OK | wx.ICON_ERROR, self)

    def _aplicar_preferencias_en_caliente(self):
        from ytchat.ui import gui_aplicar_preferencias
        gui_aplicar_preferencias.aplicar_en_caliente(self)

    def _actualizar_vigilante_obs(self):
        activos = set(self._config.get("estado_toggles") or ())
        if _OBS_COMPONENTES.intersection(activos):
            if self._obs_vigilante is None:
                self._obs_vigilante = obs_vigilante.VigilanteObs()
                self._obs_vigilante.iniciar()
        elif self._obs_vigilante is not None:
            self._obs_vigilante.detener()
            self._obs_vigilante = None

    def _on_about(self, event):
        wx.MessageBox(
            f"{APP_NAME} v{APP_VERSION}\n\n"
            "Lector accesible del chat de YouTube Live con voz de Windows "
            "o de ElevenLabs.",
            "Acerca de", wx.OK | wx.ICON_INFORMATION, self)

    def _on_marcar_incidencia(self, event):
        diagnostico.marcar_incidencia()
        anunciar("La marca de incidencia se guardó")

    # ── Handlers de voz / TTS ────────────────────────────────────────────────

    def _on_pausa(self, event):
        self._worker.toggle_pausa()
        pausado = self._worker.esta_pausado()
        self._sincronizar_pausa()
        _snd.reproducir("pausa" if pausado else "reanudar")
        anunciar("Pausado" if pausado else "Reanudado")

    def _on_vaciar(self, event):
        self._worker.vaciar_cola()
        _snd.reproducir("cola_vaciada")
        anunciar("Cola vaciada")

    def _on_detener_tts(self, event):
        self._worker.detener_actual()
        anunciar("TTS detenido")

    def _aplicar_voz(self, idx: int):
        self._worker.cambiar_voz(idx)
        self._voz_idx = idx
        try:    self._voz_nombre = self._nombre_voz(idx)
        except Exception: self._voz_nombre = "—"
        # Marcar el radio del submenú: al clicar lo hace wx solo, pero si
        # llegamos aquí desde Preferencias hay que marcarlo a mano.
        try:    self.voz_submenu.FindItemByPosition(idx).Check(True)
        except Exception: pass
        # Se guarda el NOMBRE, no el número: con el índice, instalar una voz
        # corre la lista y la app hablaría con otra sin avisar.
        self._config["voz"] = self._voz_nombre
        guardar_opcion(RUTA_CONFIG, "voz", "voz", self._voz_nombre)
        _snd.reproducir("voz_cambiada")
        anunciar(f"Voz: {self._voz_nombre}")

    def _nombre_voz(self, idx: int) -> str:
        it = self.voz_submenu.FindItemByPosition(idx)
        return it.GetItemLabelText() if it else "—"

    def _aplicar_filtro(self, idx: int):
        self._filtro = FILTROS[idx][1] if idx < len(FILTROS) else None
        self._rebuild_listbox()
        guardar_opcion(RUTA_CONFIG, "ui", "filtro_activo",
                       _NOMBRES_FILTRO[idx] if idx < len(_NOMBRES_FILTRO) else "todos")
        anunciar(f"Filtro: {FILTROS[idx][0]}. {self.lb_chat.GetCount()} mensajes")

    def _ajustar_rate(self, delta):
        # El worker mueve su porcentaje al instante (lo aplica en su hilo), así
        # que get_rate() ya devuelve el valor nuevo sin predecirlo aquí.
        self._worker.cambiar_rate(delta)
        pct = self._worker.get_rate()
        guardar_opcion(RUTA_CONFIG, "voz", "velocidad_voz", str(pct))
        anunciar(anuncio_ajuste.COMPARTIDO.frase(
            "velocidad_voz", f"Velocidad de la voz: {pct}", f"{pct}"))

    def _ajustar_volume(self, delta):
        self._worker.cambiar_volumen(delta)
        v = self._worker.get_volume()
        guardar_opcion(RUTA_CONFIG, "voz", "volumen", f"{v / 100:.2f}")
        anunciar(anuncio_ajuste.COMPARTIDO.frase(
            "volumen_voz", f"Volumen de la voz: {v}%", f"{v}%"))

    def _toggle_silenciar_sonidos(self):
        nuevo = not _snd.esta_silenciado()
        _snd.silenciar_todo(nuevo)
        self._config["silenciar_sonidos"] = nuevo
        self.mi_sil_sonidos.Check(nuevo)
        guardar_opcion(RUTA_CONFIG, "ui", "silenciar_sonidos", "true" if nuevo else "false")
        anunciar("Sonidos silenciados" if nuevo else "Sonidos activados")

    def _toggle_silenciar_lectura(self):
        nuevo = not self._config.get("silenciar_lectura", False)
        self._config["silenciar_lectura"] = nuevo
        self.mi_sil_lectura.Check(nuevo)
        guardar_opcion(RUTA_CONFIG, "sesion", "silenciar_lectura", "true" if nuevo else "false")
        anunciar("Lectura TTS silenciada" if nuevo else "Lectura TTS activada")

    def _snapshot_sesion(self) -> estado_sesion.SnapshotSesion:
        from ytchat.ui import gui_estado
        return gui_estado.snapshot_sesion(self)

    def _total_aportes_texto(self) -> str:
        from ytchat.ui import gui_estado
        return gui_estado.total_aportes_texto(self)

    def _anunciar_estado(self):
        from ytchat.ui import gui_estado
        gui_estado.anunciar_estado(self)

    def _anunciar_autor(self):
        from ytchat.ui import gui_estado
        gui_estado.anunciar_autor(self)

    def _describir_escena(self):
        from ytchat.ui import gui_estado
        gui_estado.describir_escena(self)

    def _anunciar_descripcion_escena(self, texto):
        self._descripcion_escena_en_curso = False
        anunciar(texto or "Sin información de la escena.")

    # ── Enviar al chat del directo (API oficial) ─────────────────────────────

    def _on_enviar_live(self, event):
        from ytchat.ui import gui_envio_chat
        gui_envio_chat.on_enviar_live(self, event)

    def _enviar_live_redactado(self, texto):
        from ytchat.ui import gui_envio_chat
        gui_envio_chat.enviar_live_redactado(self, texto)

    def _accion_api(self, accion, mensaje_ok: str, sonido: str = "enviado") -> None:
        from ytchat.ui import gui_envio_chat
        gui_envio_chat.accion_api(self, accion, mensaje_ok, sonido)

    def _api_ok(self, mensaje, sonido: str = "enviado"):
        from ytchat.ui import gui_envio_chat
        gui_envio_chat.api_ok(self, mensaje, sonido)

    def _api_err(self, exc):
        from ytchat.ui import gui_envio_chat
        gui_envio_chat.api_err(self, exc)

    def _actualizar_estado_online(self):
        from ytchat.ui import gui_envio_chat
        gui_envio_chat.actualizar_estado_online(self)

    def _actualizar_motivo_redaccion(self):
        from ytchat.ui import gui_envio_chat
        gui_envio_chat.actualizar_motivo_redaccion(self)

    def _sesion_api_disponible(self) -> bool:
        return bool(youtube_api.google_disponible() and credenciales.hay_sesion())

    def _iniciar_programados_si_corresponde(self, ahora: float) -> None:
        from ytchat.ui import gui_envio_chat
        gui_envio_chat.iniciar_programados_si_corresponde(self, ahora)

    def _enviar_programado(self, mensaje: dict, ahora: float) -> None:
        from ytchat.ui import gui_envio_chat
        gui_envio_chat.enviar_programado(self, mensaje, ahora)

    def _programado_enviado(self, mensaje: dict) -> None:
        from ytchat.ui import gui_envio_chat
        gui_envio_chat.programado_enviado(self, mensaje)

    def _programado_fallo(self, exc) -> None:
        from ytchat.ui import gui_envio_chat
        gui_envio_chat.programado_fallo(self, exc)

    def _procesar_programado(self) -> None:
        from ytchat.ui import gui_envio_chat
        gui_envio_chat.procesar_programado(self)

    def _moderar(self, autor: str, canal_id: str, segundos: int | None) -> None:
        from ytchat.ui import gui_envio_chat
        gui_envio_chat.moderar(self, autor, canal_id, segundos)

    # ── Chat: teclado, menú, copiar, silenciar ───────────────────────────────

    def _on_chat_key(self, event):
        k = event.GetKeyCode()
        # La orilla suena sin consumir la tecla: NVDA sigue leyendo la fila.
        if sonidos_eventos.es_orilla(k, self.lb_chat.GetSelection(),
                                     self.lb_chat.GetCount()):
            _snd.reproducir("orilla")
        if k == ord('C') and event.ControlDown():
            self._copiar_mensaje()
        elif k == wx.WXK_WINDOWS_MENU:
            self._mostrar_menu_chat()
        else:
            # Enter se atiende en EVT_CHAR_HOOK porque wx no lo entrega aquí.
            event.Skip()

    def _on_chat_char_hook(self, event):
        if (event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)
                and event.GetModifiers() == wx.MOD_NONE):
            # Solo Enter a secas: Alt+Enter es el acelerador de «Enviar mensaje»
            # y debe seguir hasta el menú.
            self._copiar_mensaje()
        else:
            event.Skip()

    def _on_chat_menu(self, event):
        self._mostrar_menu_chat()

    def _mostrar_menu_chat(self):
        idx = self.lb_chat.GetSelection()
        if idx == wx.NOT_FOUND:
            return
        menu = wx.Menu()

        id_copiar   = wx.NewIdRef()
        id_copiar2  = wx.NewIdRef()
        id_releer   = wx.NewIdRef()
        id_link     = wx.NewIdRef()
        id_sil_tts  = wx.NewIdRef()
        id_sil_full = wx.NewIdRef()
        id_rehab    = wx.NewIdRef()
        id_alias    = wx.NewIdRef()

        menu.Append(id_copiar,  "Copiar mensaje")
        menu.Append(id_copiar2, "Copiar todo (autor: mensaje, hora)")
        menu.Append(id_releer,  "Releer con TTS")
        menu.AppendSeparator()
        menu.Append(id_link,    "Abrir enlace")
        menu.AppendSeparator()

        registro_sel = self._get_selected_data()
        autor = registro_sel.autor if registro_sel else ""
        if autor:
            autor_mostrado = alias.visible(autor)
            if self._autor_esta_silenciado(autor):
                menu.Append(id_rehab, f"Rehabilitar a {autor_mostrado} (dejar de silenciar)")
            else:
                menu.Append(id_sil_tts,  f"Silenciar a {autor_mostrado} (solo TTS)")
                menu.Append(id_sil_full, f"Silenciar a {autor_mostrado} (ocultar y TTS)")
            if alias.clave(autor) not in alias.vigente():
                menu.Append(id_alias, f"Poner &alias a {autor_mostrado}…")
            else:
                menu.Append(id_alias, f"Cambiar el &alias de {autor_mostrado}…")

        id_ban     = wx.NewIdRef()
        id_timeout = wx.NewIdRef()
        plataforma_sel = registro_sel.plataforma if registro_sel else ""
        identificador_sel = registro_sel.identificador if registro_sel else ""
        moderable = bool(autor and plataforma_sel == "youtube" and identificador_sel
                         and self._live_chat_id
                         and youtube_api.google_disponible() and credenciales.hay_sesion())
        if moderable:
            menu.AppendSeparator()
            menu.Append(id_timeout, f"Expulsar 5 min a {autor_mostrado} (timeout)")
            menu.Append(id_ban,     f"Banear a {autor_mostrado} del directo (permanente)")
            menu.Bind(wx.EVT_MENU, lambda e: self._moderar(autor, identificador_sel, 300), id=id_timeout)
            menu.Bind(wx.EVT_MENU, lambda e: self._moderar(autor, identificador_sel, None), id=id_ban)

        # Los handlers van sobre el propio menú (no sobre la ventana): así mueren
        # con él y no se acumulan bindings en cada apertura del menú contextual.
        self._bind_menu((menu, id_copiar), self._copiar_mensaje)
        self._bind_menu((menu, id_copiar2), self._copiar_todo)
        self._bind_menu((menu, id_releer), self._releer_mensaje)
        self._bind_menu((menu, id_link), self._abrir_enlace)
        self._bind_menu((menu, id_sil_tts), self._silenciar_autor, autor, False)
        self._bind_menu((menu, id_sil_full), self._silenciar_autor, autor, True)
        self._bind_menu((menu, id_rehab), self._rehabilitar_autor, autor)
        self._bind_menu((menu, id_alias), self._editar_alias_autor, autor)

        self.lb_chat.PopupMenu(menu)
        menu.Destroy()

    def _editar_alias_autor(self, autor: str) -> None:
        mapa = alias.vigente()
        actual = mapa.get(alias.clave(autor), "")
        dialogo = wx.TextEntryDialog(
            self, f"Alias para {autor}. Dejar vacío para quitarlo.",
            "Alias del usuario", value=actual)
        try:
            if dialogo.ShowModal() != wx.ID_OK:
                return
            nuevo = dialogo.GetValue()
        finally:
            dialogo.Destroy()
            self.lb_chat.SetFocus()

        actualizado = alias.poner(mapa, autor, nuevo)
        alias.guardar(paths.alias(), actualizado)
        alias.usar(actualizado)
        self._rebuild_listbox()
        anunciar(f"Alias guardado, {actualizado[alias.clave(autor)]}"
                 if nuevo.strip() else "Alias quitado")

    def _copiar_mensaje(self):
        data = self._get_selected_data()
        if data is None:
            return
        mensaje = data.texto
        self._clipboard_set(mensaje)
        _snd.reproducir("copiar")
        anunciar("Mensaje copiado")

    def _copiar_enlace_directo(self):
        enlace = getattr(self, "_enlace_directo", "")
        if not enlace:
            anunciar("No hay ningún directo conectado.")
            return
        self._clipboard_set(enlace)
        _snd.reproducir("copiar")
        anunciar("Enlace del directo copiado.")

    def _copiar_todo(self):
        data = self._get_selected_data()
        if data is None:
            return
        linea = f"{data.autor}: {data.texto}, {data.hora}"
        if data.monto:
            linea += f" [{data.monto}]"
        self._clipboard_set(linea)
        _snd.reproducir("copiar")
        anunciar("Línea copiada")

    def _releer_mensaje(self):
        data = self._get_selected_data()
        if data is None:
            return
        from ytchat.voice.tts_worker import construir_tts
        self._cola.put({"texto_tts": construir_tts(data.autor, data.texto, self._config),
                        "autor": data.autor})

    def _abrir_enlace(self):
        data = self._get_selected_data()
        if data is None:
            return
        urls = _URL_RE.findall(data.texto)
        if not urls:
            anunciar("No se encontró ningún enlace")
            wx.MessageBox("No se encontró ningún enlace en este mensaje.",
                          "Sin enlace", wx.OK | wx.ICON_INFORMATION, self)
            return
        webbrowser.open(urls[0])
        anunciar("Abriendo enlace")

    # ── Silenciado en caliente ───────────────────────────────────────────────

    def _silenciar_autor(self, autor: str, ocultar: bool) -> None:
        if not autor:
            return
        al = autor.lower().strip()
        self._config.setdefault("silenciados_runtime", set()).add(al)
        sil_oculto = self._config.setdefault("silenciados_ocultar", set())
        if ocultar:
            sil_oculto.add(al)
            self._rebuild_listbox()
        else:
            sil_oculto.discard(al)
        anunciar(f"{autor} silenciado")

    def _rehabilitar_autor(self, autor: str) -> None:
        if not autor:
            return
        al = autor.lower().strip()
        self._config.setdefault("silenciados_runtime", set()).discard(al)
        self._config.setdefault("silenciados_ocultar", set()).discard(al)
        self._rebuild_listbox()
        anunciar(f"{autor} rehabilitado")

    def _autor_esta_silenciado(self, autor: str) -> bool:
        return autor.lower().strip() in self._config.get("silenciados_runtime", set())

    def _autor_esta_oculto(self, autor: str) -> bool:
        return autor.lower().strip() in self._config.get("silenciados_ocultar", set())

    # ── Selección y portapapeles ─────────────────────────────────────────────

    def _get_selected_data(self):
        idx = self.lb_chat.GetSelection()
        if idx == wx.NOT_FOUND:
            return None
        return self._chat.dato_en_fila(idx)

    def _clipboard_set(self, text: str) -> None:
        copiar_al_portapapeles(text)

    # ── Cierre y timer ───────────────────────────────────────────────────────

    def _on_close(self, event):
        if self._apagando:
            return
        if not getattr(self, "_cerrar_sin_preguntar", False):
            supervisor = getattr(self, "_supervisor", None)
            mensaje = mensaje_confirmar_salida(
                (getattr(self, "_config", None) or {}).get(
                    "confirmar_salida", True),
                bool(getattr(self, "_conectado", False)),
                bool(supervisor is not None and supervisor.activo),
                bool(getattr(self, "_obs_transmitiendo", False)))
            puede_vetar = callable(getattr(event, "CanVeto", None)) \
                and event.CanVeto()
            if mensaje is not None and puede_vetar:
                dialogo = wx.MessageDialog(
                    self, mensaje, "Salir",
                    wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION | wx.CENTRE)
                try:
                    respuesta = dialogo.ShowModal()
                finally:
                    dialogo.Destroy()
                if respuesta != wx.ID_YES:
                    event.Veto()
                    return
        self._apagando = True
        self._alive = False
        self._diagnostico_parada.set()
        self._actualizar_vigilante_obs_cierre()
        supervisor = getattr(self, "_supervisor", None)
        if supervisor is not None and supervisor.activo:
            try:
                supervisor.abandonar()
            except Exception:
                pass
            self._supervisor = None
        try:    self._timer.Stop()
        except Exception: pass
        try:    self._diagnostico_timer.Stop()
        except Exception: pass
        if self._pendientes_timer is not None:
            try:    self._pendientes_timer.Stop()
            except Exception: pass
            self._pendientes_timer = None
        hilos_previos = diagnostico.hilos_vivos_de_la_aplicacion()
        if apagado.hilos_captura_vivos(hilos_previos):
            anunciar("Cerrando")
        try:    self.Hide()
        except Exception: pass
        if self.on_desconectar_cb:
            try:    self.on_desconectar_cb()
            except Exception: pass
        self._parada.set()
        overlay_servidor.apagar()
        try:
            self._rep_panel.detener_todo()
        except Exception: pass
        try:
            self._musica.cerrar()
        except Exception: pass
        try:
            # Interrumpir lo que se esté leyendo (purga) antes de parar, para que
            # el cierre sea inmediato y no termine el mensaje en curso.
            self._worker.detener_actual()
            self._worker.detener()
        except Exception: pass
        try:    _snd.cerrar()
        except Exception: pass
        self._cierre_inicio = time.monotonic()
        self._cierre_tope = apagado.TOPE_ESPERA_CIERRE
        self._comprobar_cierre()

    def _actualizar_vigilante_obs_cierre(self):
        vigilante = getattr(self, "_obs_vigilante", None)
        if vigilante is not None:
            vigilante.detener()
            self._obs_vigilante = None

    def _comprobar_cierre(self):
        nombres = diagnostico.hilos_vivos_de_la_aplicacion()
        transcurrido = time.monotonic() - self._cierre_inicio
        if apagado.hay_que_seguir_esperando(nombres, transcurrido, self._cierre_tope):
            wx.CallLater(200, self._comprobar_cierre)
            return
        diagnostico.logger.log(apagado.nivel_registro_cierre(nombres),
            "%s", apagado.componer_resultado_cierre(nombres, self._cierre_tope))
        if not nombres:
            diagnostico.registrar_cierre_fallos()
        self.Destroy()

    def _on_timer(self, event):
        if self._alive:
            try:    self._actualizar_sb()
            except Exception: pass
            try:    self._procesar_programado()
            except Exception: pass
            try:    self._avisar_descartes()
            except Exception: pass

    def _avisar_descartes(self) -> None:
        if descartes.hay_que_avisar(self._stats.descartados,
                                    self._descartes_avisado):
            try:
                _snd.reproducir("aviso")
            except Exception:
                pass
            anunciar(descartes.frase_aviso(
                self._config.get("umbral_solo_nombre", 0)))
            self._descartes_avisado = True

    def _on_diagnostico_timer(self, event):
        if not self._alive:
            return
        ahora = time.monotonic()
        self._diagnostico_marca = ahora
        censo = diagnostico.debe_censar_hilos(self._diagnostico_censo, ahora)
        if censo:
            self._diagnostico_censo, texto = censo
            diagnostico.logger.info("%s", texto)

    # ── API pública (main.py la invoca vía wx.CallAfter) ─────────────────────

    def agregar_mensaje_chat(self, autor: str, mensaje: str, hora: str,
                             tipo: str = TIPO_TEXTO, monto: str = "",
                             canal_id: str = "", plataforma: str = "",
                             rol: str = "") -> None:
        if not self._alive:
            return
        # Si ya no estamos conectados, descartar: puede ser un mensaje rezagado
        # de un hilo de captura anterior (bloqueado en una lectura de red) que
        # llega tras desconectar. Si no, se solaparía con el directo siguiente.
        # La captura solo emite mensajes tras «conectado», así que en uso normal
        # esto no descarta nada legítimo.
        if not self._conectado:
            return
        # No tocar self._chat/lb_chat aquí: se encola y se procesa en el
        # volcado agrupado (ver _volcar_pendientes) para no disparar un
        # Append/Delete por mensaje mientras NVDA navega la lista.
        registro = MensajeChat(
            plataforma=plataforma, autor=autor, identificador=canal_id,
            texto=mensaje, hora=hora, tipo=tipo, monto=monto, rol=rol)
        self._pendientes.append(registro)
        # Si el temporizador ya corre, NO reiniciarlo: con un chat activo
        # (mensajes cada menos de MS_VOLCADO_CHAT) reiniciar pospondría el
        # volcado indefinidamente y no aparecería nada hasta una pausa.
        if self._pendientes_timer is None:
            self._pendientes_timer = wx.CallLater(MS_VOLCADO_CHAT, self._volcar_pendientes)

    def _procesar_mensaje_chat(self, registro: MensajeChat) -> bool:
        """Aplica UN mensaje ya desencolado al modelo y a lb_chat. Devuelve si
        quedó visible (se le hizo Append). Solo lo llama _volcar_pendientes."""
        if self._autor_esta_oculto(registro.autor):
            return False

        if registro.tipo == TIPO_ME_GUSTA:
            # El me gusta solo suena: no toca ni el modelo ni la lista, para
            # no desalinear fila ↔ mensaje.
            _snd.reproducir(sonidos_eventos.sonido_de_mensaje(
                registro.tipo, registro.rol, registro.monto,
                registro.plataforma))
            return False

        # El modelo (lista_chat) recorta el historial y nos dice cuántas filas
        # viejas borrar por arriba, manteniendo fila ↔ mensaje siempre alineados
        # (antes se descontaba dos veces y, pasados 500 mensajes, copiar o
        # banear caían sobre el mensaje equivocado).
        visible = self._filtro is None or registro.tipo == self._filtro
        borrar = self._chat.agregar(registro, visible)
        for _ in range(borrar):
            self.lb_chat.Delete(0)

        if registro.tipo in (TIPO_SUPERCHAT, TIPO_STICKER):
            _snd.reproducir(sonidos_eventos.sonido_de_mensaje(
                registro.tipo, registro.rol, registro.monto,
                registro.plataforma))
            self._sumar_superchat(registro.monto)
        elif registro.tipo == TIPO_MIEMBRO:
            _snd.reproducir("nuevo_miembro")
        else:
            _snd.reproducir(sonidos_eventos.sonido_de_mensaje(registro.tipo,
                                                             registro.rol))

        if visible:
            self.lb_chat.Append(self._format_display(
                registro.autor, registro.texto, registro.hora, registro.tipo, registro.monto))
        return visible

    def _volcar_pendientes(self) -> None:
        """Procesa TODOS los mensajes en espera de una vez: modelo y vista se
        mutan juntos aquí (nunca al encolar), así que fila↔mensaje se mantienen
        alineados igual que antes. Con más de un pendiente, Freeze/Thaw evita
        repintar fila a fila."""
        self._pendientes_timer = None
        pendientes, self._pendientes = self._pendientes, []
        if not pendientes or not self._alive or not self._conectado:
            return
        freeze = len(pendientes) > 1
        if freeze:
            self.lb_chat.Freeze()
        hubo_visible = False
        try:
            for registro in pendientes:
                if self._procesar_mensaje_chat(registro):
                    hubo_visible = True
        finally:
            if freeze:
                self.lb_chat.Thaw()
        # Un solo SetFirstItem al final (no uno por mensaje), y solo si el foco
        # no está en la lista (si el usuario está navegando, no le movemos la
        # vista) y algo se añadió de verdad.
        if hubo_visible and wx.Window.FindFocus() is not self.lb_chat:
            self.lb_chat.SetFirstItem(self.lb_chat.GetCount() - 1)

    def _flush_pendientes_ahora(self) -> None:
        """Vuelca ya lo encolado, sin esperar el temporizador. Se usa antes de
        leer/reconstruir la lista desde self._chat (cambio de filtro) para que
        no falte lo más reciente todavía sin procesar."""
        if self._pendientes_timer is not None:
            try:    self._pendientes_timer.Stop()
            except Exception: pass
            self._pendientes_timer = None
        self._volcar_pendientes()

    def _descartar_pendientes(self) -> None:
        """Tira lo encolado sin procesarlo. Se usa donde hoy se limpia la lista
        entera (desconectar, cambiar de vídeo): esos mensajes pertenecen a la
        sesión que se está borrando."""
        if self._pendientes_timer is not None:
            try:    self._pendientes_timer.Stop()
            except Exception: pass
            self._pendientes_timer = None
        self._pendientes.clear()

    def set_conectado(self, conectado: bool,
                        sonido_desconexion: str = "desconectado") -> None:
        if not self._alive:
            return
        estaba = self._conectado
        self._conectado = conectado
        if conectado:
            if not estaba:
                if self._config.get("recordar_direccion", True):
                    direccion = self.txt_url.GetValue()
                    self._config["ultima_direccion"] = direccion
                    guardar_opcion(RUTA_CONFIG, "sesion", "ultima_direccion",
                                   direccion)
                self._mostrar_zona(True)
                self._region_idx = REG_CONTENIDO
                self._anunciar_conectado()
                wx.CallAfter(self._foco_contenido)
        else:
            self._reiniciar_datos_sesion()
            # Solo si veníamos de una conexión real: ocultar, sonar y avisar.
            # (Un fallo de conexión nunca llegó a "conectado", así que no suena.)
            if estaba:
                self._mostrar_zona(False)
                self.set_titulo_stream("")
                self._fijar_tipo(MENSAJE_INICIAL)
                # El fin del directo de TikTok llega con su propio sonido;
                # el resto de los cortes sigue sonando «desconectado».
                _snd.reproducir(sonido_desconexion)
                anunciar("Desconectado")
                # Sacar el foco del panel del reproductor ANTES de que quede
                # oculto: si el foco sigue dentro, wx tarda en repintar y el
                # panel «se queda» visible hasta que tabulas. Al campo URL.
                wx.CallAfter(self.txt_url.SetFocus)
        self._set_conectado_ui(conectado)
        self._actualizar_estado_online()

    def _reiniciar_datos_sesion(self) -> None:
        """Borra TODO el estado de la sesión para que volver a conectar sea como
        recién abierta la app y nada del directo anterior se solape: chat,
        comentarios, reproductor, cola de lectura, super chats y contadores. NO
        toca las preferencias del usuario (filtro, voz, sonidos, tema)."""
        self._live_chat_id = ""
        self._video_id_sesion = ""
        self._enlace_directo = ""
        self._causa_sin_chat = ""
        self._usuario_tiktok_sesion = ""
        self._conexion_propia = False
        self._chat_propio = False
        self._tipo_video = deteccion.DESCONOCIDO
        self._es_tiktok = False
        self._descartes_avisado = False
        # Chat: datos, lista visible y lo que aún estaba en cola sin volcar (es
        # de la sesión que se cierra; no debe colarse en la siguiente).
        self._descartar_pendientes()
        self._chat.limpiar()
        try:    self.lb_chat.Clear()
        except Exception: pass
        # Super Chats acumulados de la sesión.
        self._sc_totales.clear()
        # Panel de información del vídeo.
        self._metadatos = {}
        try:    self.txt_info.SetValue("")
        except Exception: pass
        # Reproductor y panel de comentarios.
        try:    self._rep_panel.detener_todo()
        except Exception: pass
        try:    self._com_panel.limpiar()
        except Exception: pass
        # Cola de lectura y lo que se esté leyendo ahora mismo.
        try:
            self._worker.vaciar_cola()
            self._worker.detener_actual()
        except Exception: pass
        # Contadores a cero.
        try:    self._stats.reset()
        except Exception: pass
        self._actualizar_sb()

    def _mostrar_zona(self, mostrar: bool) -> None:
        self._zona.Show(mostrar)
        self._panel_principal.Layout()
        self._ajustar_minimo_ventana()

    def _anunciar_conectado(self) -> None:
        t = self._tipo_video
        if t == deteccion.LIVE:
            msg = "Conectado al directo. Leyendo el chat en vivo."
        elif t == deteccion.UPCOMING:
            msg = "Directo programado. Aún no hay chat; puedes ver los comentarios."
        elif t == deteccion.VOD:
            msg = "Vídeo conectado. Comentarios y reproductor disponibles."
        else:
            msg = "Conectado."
        anunciar(msg)

    def set_live_chat_id(self, live_chat_id: str, causa: str = "",
                         video_id: str | None = None, propio: bool = False) -> None:
        if not self._alive:
            return
        if video_id is not None and video_id != self._video_id_sesion:
            # Respuesta tardía del hilo LiveChatId de una conexión anterior:
            # con ese id el compositor y los mensajes programados escribirían
            # en el chat del directo equivocado.
            return
        self._live_chat_id = live_chat_id or ""
        self._causa_sin_chat = causa or ""
        self._chat_propio = bool(propio)
        self._actualizar_estado_online()

    def set_espectadores(self, n: int) -> None:
        """Actualiza el conteo de espectadores en vivo (TikTok lo refresca cada
        pocos segundos). Así F2 dice cuántos hay AHORA, no solo al conectar."""
        if not self._alive:
            return
        try:    self._metadatos["vistas"] = int(n)
        except Exception: pass

    def set_inicio_directo(self, comienzo: str) -> None:
        if not self._alive:
            return
        self._metadatos["comienzo_directo"] = comienzo or ""

    def set_tipo_video(self, tipo: str, video_id: str) -> None:
        if not self._alive:
            return
        self._tipo_video = tipo
        self._video_id_sesion = video_id or ""
        self._es_tiktok = False   # esta ruta es la de YouTube
        # Empezar el chat en limpio en cada conexión: el reset al desconectar ya
        # lo hace, pero así garantizamos que nunca quede nada del vídeo anterior.
        self._descartar_pendientes()
        self._chat.limpiar()
        self._sc_totales.clear()
        try:    self.lb_chat.Clear()
        except Exception: pass
        es_live = deteccion.tiene_chat_en_vivo(tipo)
        autoplay = bool(self._config.get("autoplay_reproductor", True))
        # Comentarios: autocargar solo cuando no hay chat en vivo (en un directo
        # no queremos saturar). Reproductor: siempre, con autoplay según prefs.
        try:    self._com_panel.set_video(video_id, autocargar=not es_live)
        except Exception: pass
        try:    self._rep_panel.set_video(video_id, autoplay=autoplay)
        except Exception: pass

        # ChangeSelection: sin anuncio de pestaña; el de «conectado» que viene
        # después ya dice qué hay disponible.
        if tipo == deteccion.LIVE:
            self._fijar_tipo("Directo en vivo: leyendo el chat.")
            self.nb.ChangeSelection(PAG_CHAT)
        elif tipo == deteccion.UPCOMING:
            self._fijar_tipo("Directo programado: aún sin chat. Hay comentarios.")
            self.nb.ChangeSelection(PAG_COMENTARIOS)
        elif tipo == deteccion.VOD:
            self._fijar_tipo("Vídeo subido: comentarios y reproductor.")
            self.nb.ChangeSelection(PAG_COMENTARIOS)
        else:
            self._fijar_tipo("Tipo no determinado: intentando leer el chat.")
        self._actualizar_boton_directo()

    def configurar_tiktok(self, usuario: str, url_flujo: str) -> None:
        """Prepara la ventana para un directo de TikTok: chat en limpio, pestaña
        de chat al frente, comentarios fuera (TikTok no los tiene aquí) y el
        reproductor con el flujo de TikTok (FLV, o HLS si no hay FLV). Lo llama main vía wx.CallAfter."""
        if not self._alive:
            return
        self._tipo_video = deteccion.LIVE
        self._es_tiktok = True
        self._usuario_tiktok_sesion = usuario or ""
        self._descartar_pendientes()
        self._chat.limpiar()
        self._sc_totales.clear()
        try:    self.lb_chat.Clear()
        except Exception: pass
        try:    self._com_panel.mostrar_no_disponible(
                    "Los comentarios no están disponibles en los directos de TikTok.")
        except Exception: pass
        autoplay = bool(self._config.get("autoplay_reproductor", True))
        try:    self._rep_panel.set_flujo(url_flujo, autoplay=autoplay)
        except Exception as exc: logger.debug("reproductor tiktok: %s", exc)
        self._fijar_tipo(f"Directo de TikTok de @{usuario}: leyendo el chat.")
        self.nb.ChangeSelection(PAG_CHAT)
        self._actualizar_boton_directo()

    def set_url(self, url: str) -> None:
        self.txt_url.SetValue(url)

    def set_metadatos(self, meta: dict) -> None:
        """Rellena el panel de información con lo que trae yt-dlp. Se llama desde
        el hilo de conexión vía wx.CallAfter; el panel puede estar oculto por
        preferencia (igual guardamos el texto, para que aparezca ya hecho si lo
        muestran)."""
        if not self._alive:
            return
        self._metadatos = meta or {}
        try:
            self.txt_info.SetValue(metadatos.formatear(self._metadatos))
            self.txt_info.SetInsertionPoint(0)   # que el lector empiece arriba
        except Exception as exc:
            logger.debug("set_metadatos: %s", exc)

    def _idx_pag_info(self) -> int:
        for i in range(self.nb.GetPageCount()):
            if self.nb.GetPage(i) is self._pag_info:
                return i
        return -1

    def set_metadatos_visible(self, visible: bool) -> None:
        """Añade o quita la pestaña de Información según la preferencia. Al
        ocultarla NO se destruye el panel, así reaparece con su contenido."""
        idx = self._idx_pag_info()
        if visible and idx == -1:
            self.nb.AddPage(self._pag_info, "Información")
            self._pag_info.Show()
        elif not visible and idx != -1:
            self.nb.RemovePage(idx)
            self._pag_info.Hide()
        self._zona.Layout()

    def set_titulo_stream(self, titulo: str) -> None:
        if not self._alive:
            return
        self._titulo_stream = (titulo or "").strip()
        if self._titulo_stream:
            # Formato tipo navegador: «Nombre del vídeo — YTChat TTS».
            self.SetTitle(f"{self._titulo_stream} — {APP_NAME}")
        else:
            self.SetTitle(f"{APP_NAME} v{APP_VERSION}")

    def auto_conectar(self) -> None:
        self._on_conectar(None)

    def poblar_voces(self, voces: list, idx_actual: int = 0) -> None:
        # Vaciar el submenú de voz y reconstruir con radio items.
        for it in list(self.voz_submenu.GetMenuItems()):
            self.voz_submenu.Delete(it)
        if not voces:
            it = self.voz_submenu.Append(wx.ID_ANY, "(no disponible)")
            it.Enable(False)
            self._voz_nombre = "—"
            return
        for i, nombre in enumerate(voces):
            it = self.voz_submenu.AppendRadioItem(wx.ID_ANY, nombre)
            self._bind_menu(it, self._aplicar_voz, i)
        idx_actual = idx_actual if 0 <= idx_actual < len(voces) else 0
        self.voz_submenu.FindItemByPosition(idx_actual).Check(True)
        self._voz_idx = idx_actual
        self._voz_nombre = voces[idx_actual]

    def _marcar_filtro(self):
        idx = _IDX_FILTRO.get(
            _NOMBRES_FILTRO[0] if self._filtro is None else "", 0)
        # Buscar el índice cuyo valor coincide con self._filtro.
        for i, (_, val) in enumerate(FILTROS):
            if val == self._filtro:
                idx = i
                break
        if 0 <= idx < len(self.fi_items):
            self.fi_items[idx].Check(True)

    def _sincronizar_checks(self):
        try:    self.mi_sil_sonidos.Check(_snd.esta_silenciado())
        except Exception: pass
        try:    self.mi_sil_lectura.Check(self._config.get("silenciar_lectura", False))
        except Exception: pass

    # ── Formato y helpers ────────────────────────────────────────────────────

    def _format_display(self, autor, msg, hora, tipo, monto):
        autor = alias.visible(autor)
        # Si "quitar emojis" está activo, también se ocultan en la lista (incluye
        # los shortcodes :nombre: de YouTube). Los marcadores 💲🎨⭐ se conservan.
        if self._config.get("limpiar_emojis", True):
            from ytchat.voice.tts_worker import quitar_emojis
            msg = quitar_emojis(msg)
        if tipo == TIPO_SUPERCHAT and monto:
            return f"💲 [{monto}] {autor}: {msg}, {hora}"
        if tipo == TIPO_STICKER and monto:
            return f"🎨 [{monto}] {autor}, {hora}"
        if tipo == TIPO_MIEMBRO:
            return f"⭐ NUEVO MIEMBRO: {autor}, {hora}"
        if tipo == TIPO_ENTRADA:
            return f"👋 {autor} entró, {hora}"
        if tipo == TIPO_SEGUIR:
            return f"{autor} sigue el canal, {hora}"
        if tipo == TIPO_COMPARTIR:
            return f"{autor} compartió el directo, {hora}"
        if tipo == TIPO_COFRE:
            return f"{autor} envió un cofre, {hora}"
        return f"{autor}: {msg}, {hora}"

    def _rebuild_listbox(self) -> None:
        # Que lo que acaba de llegar (aún en cola, sin pasar por self._chat) no
        # se pierda del recuento/reconstrucción: se procesa YA con el estado
        # vigente antes de leer el modelo.
        self._flush_pendientes_ahora()
        self.lb_chat.Clear()
        visibles = self._chat.reconstruir(
            lambda it: not self._autor_esta_oculto(it.autor)
            and (self._filtro is None or it.tipo == self._filtro))
        for registro in visibles:
            self.lb_chat.Append(self._format_display(
                registro.autor, registro.texto, registro.hora, registro.tipo, registro.monto))

    def _set_conectado_ui(self, conectado: bool) -> None:
        # Botón (toggle), items de menú Conectar/Desconectar y campo URL. El
        # resto (ocultar zona, sonido, título) lo gestiona set_conectado.
        self._conectando = False
        self.btn_conectar.SetLabel("&Desconectar" if conectado else "&Conectar")
        self.btn_conectar.Enable()
        self.mi_conectar.Enable(not conectado)
        self.mi_desconectar.Enable(conectado)
        self.txt_url.Enable(not conectado)
        self._actualizar_menus_por_conexion()
        self._actualizar_boton_directo()

    def _actualizar_menus_por_conexion(self) -> None:
        """Deshabilita en la barra de menú lo que solo aplica con una conexión
        activa: navegar por paneles, el filtro y las acciones de voz sobre una
        lectura en curso. Así el usuario no llega por el menú a paneles que no
        existen aún. Los ajustes de voz y «Ir a URL» /
        «Anunciar estado» quedan siempre disponibles.

        El ítem «Descargar este vídeo» sigue las reglas del diseño: solo se
        habilita con conexión YouTube NO-live (TikTok y live están deshabilitados
        en v1). Si la URL no se puede obtener del reproductor, se deshabilita."""
        con = bool(self._conectado)
        for it in getattr(self, "_mi_ver_conexion", []):
            try:    it.Enable(con)
            except Exception: pass
        try:    self._mi_filtro_sub.Enable(con)
        except Exception: pass
        for it in getattr(self, "_mi_voz_conexion", []):
            try:    it.Enable(con)
            except Exception: pass

        # Descargar este vídeo: YouTube + conexión + no live + URL disponible.
        # El panel del reproductor gestiona sus propios avisos, pero afinamos
        # el ítem para que:
        #   - TikTok → off (es TikTok, no YouTube)
        #   - Live   → off (out of scope v1, ver spec R: Live y TikTok off)
        #   - sin URL → off (no hay nada que descargar)
        try:
            descargar_este_on = False
            if con and not self._es_tiktok and getattr(self, "_rep_panel", None):
                try:
                    if not self._rep_panel.get_es_live():
                        descargar_este_on = bool(self._rep_panel.get_url_para_descarga())
                except Exception:
                    descargar_este_on = False
            if hasattr(self, "mi_descargar_este"):
                self.mi_descargar_este.Enable(descargar_este_on)
        except Exception as exc:
            logger.debug("enable mi_descargar_este: %s", exc)

    def _actualizar_sb(self) -> None:
        sin_tts = " [sin TTS]" if self._config.get("silenciar_lectura", False) else ""
        if self._conectado and self._titulo_stream:
            estado = f"Conectado: {self._titulo_stream[:35]}{sin_tts}"
        elif self._conectado:
            estado = f"Conectado{sin_tts}"
        else:
            estado = f"Desconectado{sin_tts}"
        self.sb.SetStatusText(estado, 0)

        try:    self.sb.SetStatusText(f"Voz vel: {self._worker.get_rate()}", 1)
        except Exception: self.sb.SetStatusText("Voz vel: --", 1)

        nombre = self._voz_nombre or "—"
        if len(nombre) > 28:
            nombre = nombre[:25] + "..."
        self.sb.SetStatusText(f"Voz: {nombre}", 2)

        try:    self.sb.SetStatusText(f"Cola: {self._cola.qsize()}", 3)
        except Exception: self.sb.SetStatusText("Cola: —", 3)
        try:    self.sb.SetStatusText(f"Leídos: {self._stats.leidos}", 4)
        except Exception: self.sb.SetStatusText("Leídos: —", 4)

        try:    self.sb.SetStatusText(f"Voz vol: {self._worker.get_volume()}%", 5)
        except Exception: self.sb.SetStatusText("Voz vol: --", 5)

        if self._config.get("mostrar_total_superchats", True):
            self.sb.SetStatusText(self._formato_total_sc(), 6)
        else:
            self.sb.SetStatusText("", 6)

    # ── Acumulación de Super Chats ───────────────────────────────────────────

    def _sumar_superchat(self, monto: str) -> None:
        from ytchat.capture.montos import parsear_monto
        r = parsear_monto(monto)
        if r is None:
            return
        divisa, valor = r
        self._sc_totales[divisa] = self._sc_totales.get(divisa, 0.0) + valor

    def _formato_total_sc(self) -> str:
        try:    n = self._stats.superchats
        except Exception: n = 0
        if not self._sc_totales:
            return f"SC: {n}"
        if len(self._sc_totales) == 1:
            d, t = next(iter(self._sc_totales.items()))
            return f"SC: {n} ({d}{t:.2f})"
        partes = [f"{d}{t:.0f}" for d, t in self._sc_totales.items()]
        return f"SC: {n} ({', '.join(partes)})"


# ── Portapapeles ─────────────────────────────────────────────────────────────
# Compartido con el panel de comentarios: primero wx y, si falla (p. ej. otro
# proceso tiene el portapapeles abierto), la vía Win32 directa como respaldo.

def copiar_al_portapapeles(text: str) -> None:
    try:
        if wx.TheClipboard.Open():
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(text))
                wx.TheClipboard.Flush()
            finally:
                wx.TheClipboard.Close()
            return
    except Exception:
        pass
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        u32 = ctypes.windll.user32
        if not u32.OpenClipboard(0):
            return
        try:
            u32.EmptyClipboard()
            encoded = text.encode("utf-16-le") + b"\x00\x00"
            h = k32.GlobalAlloc(0x0042, len(encoded))
            if not h:
                return
            p = k32.GlobalLock(h)
            if not p:
                k32.GlobalFree(h)
                return
            ctypes.memmove(p, encoded, len(encoded))
            k32.GlobalUnlock(h)
            if not u32.SetClipboardData(13, h):  # CF_UNICODETEXT
                k32.GlobalFree(h)
        finally:
            u32.CloseClipboard()
    except Exception:
        pass


# ── Entrada ──────────────────────────────────────────────────────────────────

_gui_frame: YTChatFrame | None = None


class AplicacionYTChat(wx.App):
    def OnInit(self):
        self.Bind(wx.EVT_END_SESSION, self._on_fin_sesion)
        # Hay que guardar la referencia en la app, si el recolector la libera
        # wx queda llamando a memoria liberada
        try:
            self._wx_log = _LogWx()
            wx.Log.SetActiveTarget(self._wx_log)
        except Exception as exc:
            logger.warning("No se pudo instalar el registro de wx: %s", exc)
        return True

    def OnAssert(self, archivo, linea, condicion, mensaje):
        # En un ejecutable empaquetado las aserciones de wx se pierden enteras.
        logger.warning("wx aserción archivo=%s línea=%s condición=%s mensaje=%s",
                       archivo, linea, condicion, mensaje)

    def _on_fin_sesion(self, event):
        if _gui_frame is not None:
            _gui_frame._on_close(event)


def iniciar_gui(config, cola, stats, worker, parada,
                url_inicial: str = "",
                iniciar_captura_cb=None,
                detener_captura_cb=None) -> None:
    global _gui_frame, RUTA_CONFIG

    RUTA_CONFIG = paths.config_ini()

    app = AplicacionYTChat(redirect=False)
    # El lector de JAWS crea su COM en el hilo que lo inicializa: tiene que ser
    # con la aplicación de wx ya en pie, y antes de crear el frame.
    _lector_init()
    # El worker avisa por acá cuando ElevenLabs falla y se cae a la voz de
    # Windows; `anunciar` reenvía al hilo de la interfaz.
    worker.al_avisar = anunciar
    frame = YTChatFrame(None, config, cola, stats, worker, parada)
    _gui_frame = frame
    frame.on_conectar_cb    = iniciar_captura_cb
    frame.on_desconectar_cb = detener_captura_cb

    h = WxAnnouncingHandler()
    h.setLevel(logging.INFO)
    logging.getLogger().addHandler(h)

    voces = worker.voces()
    idx_voz = escala_voz.resolver_voz(config.get("voz"), voces)
    frame.poblar_voces(voces, 0 if idx_voz is None else idx_voz)

    # Conversión de una sola vez: los números de voz viejos pasan a nombre y se
    # fijan en config.ini, así instalar una voz no cambia la voz elegida.
    for clave in ("voz", "voz_eventos"):
        nombre = escala_voz.migrar_voz(config.get(clave), voces)
        if nombre is not None:
            config[clave] = nombre
            guardar_opcion(RUTA_CONFIG, "voz", clave, nombre)

    # Restaurar filtro de la sesión anterior.
    fa = config.get("filtro_activo", "todos")
    idx_f = _IDX_FILTRO.get(fa, 0)
    if 0 <= idx_f < len(FILTROS):
        frame._filtro = FILTROS[idx_f][1]
        frame._marcar_filtro()

    # Restaurar silenciado de sonidos si la sesión anterior lo tenía activo.
    if config.get("silenciar_sonidos", False):
        _snd.silenciar_todo(True)
    frame._sincronizar_checks()

    if url_inicial:
        frame.set_url(url_inicial)
    elif config.get("recordar_direccion", True) and config.get("ultima_direccion", ""):
        frame.set_url(config["ultima_direccion"])
        try:
            frame.txt_url.SelectAll()
        except Exception:
            pass

    frame.Show()
    try:
        frame.Raise()
        frame.txt_url.SetFocus()
    except Exception:
        pass
    from ytchat.ui import gui_actualizar_app, gui_directo_huerfano
    gui_actualizar_app.programar_confirmacion_arranque()
    gui_actualizar_app.programar_resultado_actualizacion(frame)
    gui_actualizar_app.programar_aviso_version(frame)
    gui_directo_huerfano.programar_revision(frame)
    if config.get("sonido_inicio", True):
        diagnostico.crear_hilo(
            lambda: _snd.reproducir("app_inicio"), "SonidoInicio").start()
    wx.CallAfter(frame._arrancar_precalentamiento)

    if url_inicial and iniciar_captura_cb:
        wx.CallAfter(frame.auto_conectar)

    app.MainLoop()
    _gui_frame = None

    try:    logging.getLogger().removeHandler(h)
    except Exception: pass
