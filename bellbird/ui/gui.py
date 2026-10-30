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
from wx.lib.wordwrap import wordwrap

from bellbird.core.config import APP_NAME, APP_VERSION, TIPO_TEXTO, FILTROS
from bellbird.core.config import parsear_atajos, detectar_conflictos_atajos, guardar_opcion
from bellbird.core.idioma import N_, _
from bellbird.core import paths
from bellbird.core import anuncio_ajuste
from bellbird.core import sonidos_eventos
from bellbird.capture import deteccion
from bellbird.capture import metadatos
from bellbird.capture import estado_sesion
from bellbird.core import historial
from bellbird.ui.lista_chat import MensajeChat, texto_fila
from bellbird.ui.chat_vivo import ControladorChat
from bellbird.ui import atajos_captura, recientes_inicio as recientes
from bellbird.voice import escala_voz
from bellbird.voice import sound_player as _snd
from bellbird.youtube import credenciales
from bellbird.youtube import youtube_api
from bellbird.core import diagnostico
from bellbird.core import apagado
from bellbird.capture.montos import texto_importes
from bellbird.obs import overlay_servidor
from bellbird.capture import programados
from bellbird.capture import descartes
from bellbird.capture import redaccion
from bellbird.capture import alias
from bellbird.obs import obs_entradas_audio
from bellbird.obs import obs_estado
from bellbird.obs import obs_vigilante
from bellbird.obs import obs_activacion
from bellbird.obs import obs_cliente
from bellbird.obs.obs_panel import GestorPanelObs
from bellbird.player import flujo_tiktok
from bellbird.ui.barra_estado import anchos_barra_estado
from bellbird.ui.gui_redactar import PanelRedactar
from bellbird.ui.sesion_conectada import SesionConectada

# Mapeo entre índice de FILTROS y clave persistida en config.ini.
_NOMBRES_FILTRO = ("todos", "texto", "superchat", "miembro", "avisos")
_IDX_FILTRO     = {"todos": 0, "texto": 1, "superchat": 2, "miembro": 3, "avisos": 4}
# Controles para AnuncioAjuste.COMPARTIDO, compartidos con el reproductor.
_CONTROL_VELOCIDAD = "velocidad_voz"
_CONTROL_VOLUMEN = "volumen_voz"

MAX_ITEMS_CHAT  = 500
TIMER_STATUS_MS = 1000
TIMER_DIAGNOSTICO_MS = 100
ANCHO_DEFECTO   = 860
ALTO_DEFECTO    = 700

# Mensaje bajo la barra de URL cuando no hay conexión. Breve pero completo:
# qué se puede pegar y cómo conectar.
MENSAJE_INICIAL = N_("Sin conectar. Pega un enlace de YouTube (directo o vídeo) o "
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
# Traductores: regiones que recorre F6 en la ventana principal.
_NOMBRE_REGION = (N_("Conexión"), N_("Contenido"), N_("Reproductor"))

logger = diagnostico.obtener_logger(__name__)
_OBS_COMPONENTES = frozenset(("obs_transmision", "obs_grabacion", "obs_escena"))


# Reexportados: muchos módulos todavía los piden a gui.
from bellbird.ui.accesibilidad import (
    ContadorAccesible, WxAnnouncingHandler, _lector_init, anunciar,
    nombre_accesible, registro_es_anunciable,
)
from bellbird.ui.busqueda_teclado import instalar_busqueda_tipo
from bellbird.ui.tema import ALTO_CONTRASTE, _T, _pintar, _tc, _titulo


def anunciar_conflictos_atajos(raw: dict | None) -> None:
    for perdedora, conservada, combinacion in detectar_conflictos_atajos(raw):
        anunciar(
            _("Conflicto de atajos: {perdedora} se quedó sin atajo porque "
              "{conservada} usa {combinacion}.").format(
                perdedora=perdedora, conservada=conservada, combinacion=combinacion))


def caja_de_grupo(panel, titulo):
    """Crea una caja y devuelve el sizer junto al padre de sus controles."""
    caja = wx.StaticBox(panel, label=titulo)
    return wx.StaticBoxSizer(caja, wx.VERTICAL), caja


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
        return (_("¿Salir de la aplicación? Hay un chat conectado y una transmisión en curso."))
    if chat_conectado:
        return _("¿Salir de la aplicación? Hay un chat conectado.")
    if transmision:
        return _("¿Salir de la aplicación? Hay una transmisión en curso.")
    return None


class YTChatFrame(wx.Frame):

    def __init__(self, parent, config, cola, stats, worker, parada):
        super().__init__(
            parent,
            # Traductores: título de la ventana: nombre de la app y versión.
            title=_("{app} v{version}").format(app=APP_NAME, version=APP_VERSION),
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
        self._texto_tipo = _(MENSAJE_INICIAL)   # texto de lbl_tipo sin saltos de Wrap
        self._titulo_stream = ""
        self.sesion = SesionConectada()
        self._obs_transmitiendo = False   # OBS emite sin supervisor a la vista

        self._sc_totales: dict[str, float] = {}
        self.programador = programados.ProgramadorMensajes(
            programados.cargar(paths.mensajes_programados()))

        # Voz activa: se elige en un submenú de radio.
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
        from bellbird.ui import gui_menu
        gui_menu.construir_menu(self)

    def _sincronizar_pausa(self) -> None:
        try:    pausado = bool(self._worker.esta_pausado())
        except Exception: return
        self.mi_pausa.SetItemLabel(
            (_("&Reanudar lectura") if pausado else _("&Pausar lectura")) + self._accel("pausa"))

    def _cambiar_overlay(self, encender):
        from bellbird.ui import gui_transmitir
        return gui_transmitir.cambiar_overlay(self, encender)

    def _guardar_usuario_tiktok(self, usuario):
        from bellbird.ui import gui_transmitir
        return gui_transmitir.guardar_usuario_tiktok(self, usuario)

    def _guardar_destino_transmision(self, destino):
        from bellbird.ui import gui_transmitir
        return gui_transmitir.guardar_destino_transmision(self, destino)

    def _alternar_aviso_sobrecarga(self):
        from bellbird.ui import gui_transmitir
        gui_transmitir.alternar_aviso_sobrecarga(self)

    def _guardar_datos_directo_youtube(self, titulo, descripcion, privacidad,
                                        latencia=None, ninos=False, dvr=True,
                                        categoria="", etiquetas=None,
                                        miniatura="", lista="",
                                        lista_titulo=""):
        from bellbird.ui import gui_transmitir
        return gui_transmitir.guardar_datos_directo_youtube(
            self, titulo, descripcion, privacidad, latencia, ninos, dvr,
            categoria, etiquetas, miniatura, lista, lista_titulo)

    def _actualizar_boton_directo(self) -> None:
        from bellbird.ui import gui_transmitir
        gui_transmitir.actualizar_boton_directo(self)

    def _al_terminar_supervisor(self) -> None:
        from bellbird.ui import gui_transmitir
        gui_transmitir.al_terminar_supervisor(self)

    def _supervisar_transmision(self, accion, destino="", usuario="", revision=None):
        from bellbird.ui import gui_transmitir
        return gui_transmitir.supervisar_transmision(self, accion, destino, usuario, revision)

    def _on_actualizar_ytdlp(self, event):
        from bellbird.ui import gui_actualizar_ytdlp
        gui_actualizar_ytdlp.abrir_ventana_actualizacion(self)

    def _on_actualizar_app(self, event):
        from bellbird.ui import gui_actualizar_app
        gui_actualizar_app.abrir_ventana_actualizacion(self)

    # ── Construcción de la UI ────────────────────────────────────────────────

    def _build_ui(self):
        # Importes diferidos para evitar el ciclo (esos módulos importan de gui).
        from bellbird.ui.gui_comentarios import ComentariosPanel
        from bellbird.player.reproductor import ReproductorPanel

        panel = wx.Panel(self, name="PanelPrincipal")
        _pintar(panel, _T.bg, _T.text)
        vs = wx.BoxSizer(wx.VERTICAL)

        # ── Barra superior: URL + tipo + Conectar ──
        row = wx.BoxSizer(wx.HORIZONTAL)
        lbl = wx.StaticText(panel, label=_("&Enlace o ID:"), name="EtiquetaURL")
        _titulo(lbl)
        row.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.txt_url = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER, name=_("Enlace del directo o vídeo"))
        _tc(self.txt_url)
        self.txt_url.SetToolTip(
            _("Enlace de YouTube (directo o vídeo) o de un directo de TikTok "
              "(tiktok.com/@usuario/live). También vale el ID de 11 caracteres de "
              "YouTube. Pulsa Intro para conectar."))
        row.Add(self.txt_url, 1, wx.EXPAND | wx.RIGHT, 8)
        # Traductores: nombre accesible del botón para conectar.
        self.btn_conectar = wx.Button(panel, label=_("&Conectar"), name=_("Conectar"))
        _pintar(self.btn_conectar, _T.primary, _T.primary_t)
        self.btn_conectar.SetFont(self.btn_conectar.GetFont().Bold())
        row.Add(self.btn_conectar, 0, wx.ALIGN_CENTER_VERTICAL)
        from bellbird.ui.boton_directo import BotonDirecto
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

        # Traductores: cuaderno con los paneles.
        self.nb = wx.Notebook(self._zona, name=_("Paneles"))
        _tc(self.nb, bg=_T.surface)
        self._pag_chat = self._build_pagina_chat(self.nb)
        self._com_panel = ComentariosPanel(self.nb, self._cola, self._config)
        self.nb.AddPage(self._pag_chat, _("Chat del directo"))
        # Traductores: pestaña de comentarios.
        self.nb.AddPage(self._com_panel, _("Comentarios"))
        # Pestaña de información del vídeo (solo lectura). Se añade SIEMPRE al
        # final, para no alterar los índices de Chat/Comentarios, y se puede
        # ocultar por preferencia. La rellena set_metadatos con lo de yt-dlp.
        self._pag_info = self._build_pagina_info(self.nb)
        self._metadatos = {}
        if bool(self._config.get("mostrar_metadatos", True)):
            # Traductores: pestaña con los datos del vídeo.
            self.nb.AddPage(self._pag_info, _("Información"))
        else:
            self._pag_info.Hide()
        # Piso para que la lista del chat, los comentarios y la información no
        # queden aplastados por el reproductor en ventanas bajas: 170 dejaba
        # ver 2-3 mensajes; con esto se ven varios más sin tocar el reproductor.
        self.nb.SetMinSize((-1, 260))
        zvs.Add(self.nb, 4, wx.EXPAND | wx.BOTTOM, 10)

        # Proporción 4/1 para lo que sobra, pero a 860x700 mandan los mínimos, que ya superan los 700.
        self._rep_panel = ReproductorPanel(self._zona, self._config)
        # Al alternar los botones del reproductor (desde su interruptor o el menú),
        # sincronizamos la casilla del menú y persistimos la preferencia.
        self._rep_panel.on_botones_toggle = self._on_botones_rep_cambio
        zvs.Add(self._rep_panel, 1, wx.EXPAND)

        self._zona.SetSizer(zvs)
        vs.Add(self._zona, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self._zona.Hide()
        self._inicio = recientes.armar(panel, vs, self._zona, self._reconectar_desde_historial)

        panel.SetSizer(vs)
        self._panel_principal = panel

        # Control de la música: nace sin tocar VLC ni el disco.
        from bellbird.ui import gui_musica
        self._musica = gui_musica.ControlMusica(self)

        # Regiones que recorre F6 / Shift+F6.
        self._region_idx = REG_CONTENIDO
        self._regiones = [
            lambda: self.txt_url.SetFocus(),
            self._foco_contenido,
            self._rep_panel.anclar_foco,
        ]

        self.sb = self.CreateStatusBar(7, name="BarraEstado")
        # (Sin fondo: la barra de estado nativa lo ignora.)
        _pintar(self.sb, fg=_T.dim)
        self.sb.SetStatusWidths(anchos_barra_estado(lambda t: self.sb.GetTextExtent(t)[0]))
        self._actualizar_sb()
        self._set_conectado_ui(False)   # estado inicial: desconectado

    def _build_pagina_chat(self, parent) -> wx.Panel:
        pag = wx.Panel(parent, name="PaginaChat")
        _pintar(pag, _T.bg, _T.text)
        vs = wx.BoxSizer(wx.VERTICAL)

        lbl = wx.StaticText(pag, label=_("Mensajes del chat:"), name="EtiquetaChat")
        _titulo(lbl)
        vs.Add(lbl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)

        self.lb_chat = wx.ListBox(
            pag, style=wx.LB_SINGLE | wx.LB_HSCROLL, name=_("Chat del directo"))
        _tc(self.lb_chat)
        pt = int(self._config.get("tamanio_fuente_chat", 12))
        self.lb_chat.SetFont(wx.Font(
            pt, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        self.lb_chat.SetToolTip(
            _("Mensajes del chat. Intro copia el mensaje. "
              "La tecla de aplicaciones abre el menú contextual."))
        # msaa=False: ver el porqué en nombre_accesible() (lista dinámica).
        nombre_accesible(self.lb_chat, _("Chat del directo"), msaa=False)
        self.chat_vivo = ControladorChat(
            self.lb_chat, MAX_ITEMS_CHAT,
            activo=lambda: self._alive and self._conectado,
            autor_oculto=self._autor_esta_oculto,
            formatear=self._format_display,
            al_superchat=self._sumar_superchat)
        vs.Add(self.lb_chat, 1, wx.EXPAND | wx.ALL, 8)

        self._panel_redactar = PanelRedactar(
            pag, _("&Mensaje:"), redaccion.MAXIMO_CHAT, self._enviar_live_redactado)
        vs.Add(self._panel_redactar, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        pag.SetSizer(vs)
        self._actualizar_motivo_redaccion()
        # Mensajes recientes: lee con Ctrl+Mayús y un número, también fuera.
        # Nace acá, donde ya existe lb_chat.
        from bellbird.ui import chat_recientes
        self._recientes = chat_recientes.LecturaRecientes(
            self, self.lb_chat, self._config, self._cola)
        return pag

    def _build_pagina_info(self, parent) -> wx.Panel:
        pag = wx.Panel(parent, name="PaginaInfo")
        _pintar(pag, _T.bg, _T.text)
        vs = wx.BoxSizer(wx.VERTICAL)

        lbl = wx.StaticText(pag, label=_("Información del vídeo:"), name="EtiquetaInfo")
        _titulo(lbl)
        vs.Add(lbl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)

        # Solo lectura y multilínea. TE_AUTO_URL (con TE_RICH2, necesario en
        # Windows) hace clicables los enlaces de la descripción SIN romper la
        # lectura con NVDA, que recorre el cuadro como texto normal (flechas,
        # selección, copiar). Es la opción accesible frente a un wx.html.
        self.txt_info = wx.TextCtrl(
            pag, value="", name=_("Información del vídeo"),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_AUTO_URL | wx.TE_RICH2)
        _tc(self.txt_info)
        self.txt_info.SetToolTip(
            _("Datos del vídeo: canal, vistas, descripción. Solo lectura. Para "
              "abrir un enlace, cópialo y pégalo en el navegador."))
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
        """Parte lbl_tipo al ancho actual sin StaticText.Wrap, que a veces no parte."""
        if not hasattr(self, "lbl_tipo"):
            return
        try:
            ancho = max(200, self.lbl_tipo.GetParent().GetClientSize().Width - 20)
            dc = wx.ClientDC(self.lbl_tipo)
            dc.SetFont(self.lbl_tipo.GetFont())
            self.lbl_tipo.SetLabel(wordwrap(self._texto_tipo, ancho, dc).rstrip("\n"))
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
            anunciar(_("Conéctate primero para usar los paneles"))
            return
        self._region_idx = (self._region_idx + delta) % len(self._regiones)
        self._ir_region(self._region_idx)

    def _ir_region(self, idx: int):
        if not (0 <= idx < len(self._regiones)):
            return
        if idx != REG_CONEXION and not self._conectado:
            anunciar(_("Conéctate primero para usar los paneles"))
            return
        self._region_idx = idx
        try:    self._regiones[idx]()
        except Exception as exc: logger.debug("ir_region %d: %s", idx, exc)
        nombre = _(_NOMBRE_REGION[idx])
        if idx == REG_CONTENIDO:
            # Traductores: región actual y pestaña al moverse con F6.
            nombre = _("{region}: {pagina}").format(
                region=nombre, pagina=self.nb.GetPageText(self.nb.GetSelection()))
        anunciar(nombre)

    def _ir_lista(self):
        """Alt+L: foco directo a la lista de la pestaña actual (chat o comentarios)."""
        if not self._conectado:
            anunciar(_("Conéctate primero"))
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
            anunciar(_("El reproductor no está disponible"))
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
                self.sesion.enlace_directo = url
            else:
                self.sesion.enlace_directo = ""
        except Exception as exc:
            logger.debug("registrar historial: %s", exc)

    def _on_historial(self):
        self._inicio.abrir_historial()

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
                anunciar(_("Conexión cancelada"))
                self.txt_url.SetFocus()
        else:
            url = self.txt_url.GetValue().strip()
            if not url:
                wx.MessageBox(_("Introduce un enlace o un ID de YouTube."),
                              _("Falta el enlace"), wx.OK | wx.ICON_WARNING, self)
                self.txt_url.SetFocus()
                return
            self._conectando = True
            # El botón y «Desconectar» siguen activos para poder cancelar una
            # conexión que no responde.
            self.btn_conectar.SetLabel(_("&Cancelar conexión"))
            self.btn_conectar.Enable()
            self.mi_conectar.Enable(False)
            self.mi_desconectar.Enable(True)
            self.txt_url.Disable()
            _snd.reproducir("conectando")
            # Traductores: aviso mientras se conecta.
            anunciar(_("Conectando"))
            if self.on_conectar_cb:
                self.on_conectar_cb(url)
            self._actualizar_boton_directo()

    def url_invalida(self):
        """La URL/ID no es válida: restaurar la UI y avisar (sin esperas)."""
        if not self._alive:
            return
        _snd.reproducir("error")
        self._set_conectado_ui(False)
        anunciar(_("El enlace o el ID de YouTube no es válido"))
        self.txt_url.SetFocus()
        wx.MessageBox(_("El enlace o el ID de YouTube no es válido. Revisa lo que pegaste."),
                      _("Enlace no válido"), wx.OK | wx.ICON_WARNING, self)

    def _on_preferencias(self, event):
        try:
            from bellbird.ui.gui_preferencias import abrir_preferencias
            avisos = []
            acepto = abrir_preferencias(self, self._config, avisos=avisos)
            # La lista ya se guardó en disco al tocar sus botones: se relee
            # haya aceptado o no, y el reloj se arma de nuevo con la lista nueva.
            self.programador.recargar(programados.cargar(paths.mensajes_programados()))
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
            wx.MessageBox(_("No se pudo abrir Preferencias:\n{detalle}").format(detalle=exc),
                          # Traductores: título de un cuadro de error.
                          _("Error"), wx.OK | wx.ICON_ERROR, self)
        # La pestaña API puede haber cambiado la sesión: refrescar.
        self._actualizar_estado_online()

    def _on_transmision(self, event):
        from bellbird.ui.gui_transmision import abrir_transmision
        abrir_transmision(self, self._cambiar_overlay,
                          supervisar=self._supervisar_transmision,
                          guardar_usuario=self._guardar_usuario_tiktok,
                          usuario_tiktok=self._config.get("tiktok_usuario", ""),
                          guardar_destino=self._guardar_destino_transmision)

    def _on_obs_micro(self, event):
        def avisar(texto, sonido):
            def _avisar():
                if sonido:
                    _snd.reproducir(sonido)
                anunciar(texto)
            wx.CallAfter(_avisar)

        anterior = self.mi_obs_micro.IsChecked()
        def _alternar():
            obs_entradas_audio.microfono_por_atajo(
                self._config.get("obs_microfono", ""), avisar,
                lambda e: wx.CallAfter(self.mi_obs_micro.Check, anterior if e is None else e))

        diagnostico.crear_hilo(_alternar, "MicrofonoObs").start()

    # ── Gestor de descargas (gui_descargas) ──────────────────────────────────
    # Abre el diálogo siempre (no requiere conexión). Si le llega una URL, la
    # precarga (caso "Descargar este vídeo"). Importamos gui_descargas perezoso
    # para que el ciclo de imports (gui → gui_descargas → gui) no se queje.

    def _abrir_descargas(self, url: str | None = None) -> None:
        try:
            from bellbird.ui.gui_descargas import abrir
        except Exception as exc:
            logger.warning("No se pudo abrir el gestor de descargas: %s", exc)
            wx.MessageBox(_("No se pudo abrir el Administrador de descargas:\n{detalle}").format(detalle=exc),
                          # Traductores: título de un cuadro de error.
                          _("Error"), wx.OK | wx.ICON_ERROR, self)
            return
        try:
            abrir(self, url_inicial=url)
        except Exception as exc:
            logger.warning("gestor de descargas: %s", exc)
            wx.MessageBox(_("Error en el Administrador de descargas:\n{detalle}").format(detalle=exc),
                          # Traductores: título de un cuadro de error.
                          _("Error"), wx.OK | wx.ICON_ERROR, self)

    def _aplicar_preferencias_en_caliente(self):
        from bellbird.ui import gui_aplicar_preferencias
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
            _("{app} v{version}\n\n"
              "Lector accesible del chat de YouTube Live con voz de Windows "
              "o de ElevenLabs.").format(app=APP_NAME, version=APP_VERSION),
            _("Acerca de"), wx.OK | wx.ICON_INFORMATION, self)

    def _on_marcar_incidencia(self, event):
        diagnostico.marcar_incidencia()
        anunciar(_("La marca de incidencia se guardó"))

    # ── Handlers de voz / TTS ────────────────────────────────────────────────

    def _on_pausa(self, event):
        self._worker.toggle_pausa()
        pausado = self._worker.esta_pausado()
        self._sincronizar_pausa()
        _snd.reproducir("pausa" if pausado else "reanudar")
        # Traductores: lectura en pausa o reanudada.
        anunciar(_("Pausado") if pausado else _("Reanudado"))

    def _on_vaciar(self, event):
        self._worker.vaciar_cola()
        _snd.reproducir("cola_vaciada")
        anunciar(_("Cola vaciada"))

    def _on_detener_tts(self, event):
        self._worker.detener_actual()
        anunciar(_("Voz detenida"))

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
        # Traductores: {nombre} es la voz activa.
        anunciar(_("Voz: {nombre}").format(nombre=self._voz_nombre))

    def _nombre_voz(self, idx: int) -> str:
        it = self.voz_submenu.FindItemByPosition(idx)
        return it.GetItemLabelText() if it else "—"

    def _aplicar_filtro(self, idx: int):
        self.chat_vivo.filtro = FILTROS[idx][1] if idx < len(FILTROS) else None
        self.chat_vivo.reconstruir()
        guardar_opcion(RUTA_CONFIG, "ui", "filtro_activo",
                       _NOMBRES_FILTRO[idx] if idx < len(_NOMBRES_FILTRO) else "todos")
        anunciar(_("Filtro: {filtro}. {n} mensajes").format(filtro=FILTROS[idx][0], n=self.lb_chat.GetCount()))

    def _ajustar_rate(self, delta):
        # El worker mueve su porcentaje al instante (lo aplica en su hilo), así
        # que get_rate() ya devuelve el valor nuevo sin predecirlo aquí.
        self._worker.cambiar_rate(delta)
        pct = self._worker.get_rate()
        guardar_opcion(RUTA_CONFIG, "voz", "velocidad_voz", str(pct))
        anunciar(anuncio_ajuste.COMPARTIDO.frase(
            _CONTROL_VELOCIDAD, _("Velocidad de la voz: {valor}").format(valor=pct), f"{pct}"))

    def _ajustar_volume(self, delta):
        self._worker.cambiar_volumen(delta)
        v = self._worker.get_volume()
        guardar_opcion(RUTA_CONFIG, "voz", "volumen", f"{v / 100:.2f}")
        anunciar(anuncio_ajuste.COMPARTIDO.frase(
            _CONTROL_VOLUMEN, _("Volumen de la voz: {valor}%").format(valor=v), f"{v}%"))

    def _toggle_silenciar_sonidos(self):
        nuevo = not _snd.esta_silenciado()
        _snd.silenciar_todo(nuevo)
        self._config["silenciar_sonidos"] = nuevo
        self.mi_sil_sonidos.Check(nuevo)
        guardar_opcion(RUTA_CONFIG, "ui", "silenciar_sonidos", "true" if nuevo else "false")
        anunciar(_("Sonidos silenciados") if nuevo else _("Sonidos activados"))

    def _toggle_silenciar_lectura(self):
        nuevo = not self._config.get("silenciar_lectura", False)
        self._config["silenciar_lectura"] = nuevo
        self.mi_sil_lectura.Check(nuevo)
        guardar_opcion(RUTA_CONFIG, "sesion", "silenciar_lectura", "true" if nuevo else "false")
        anunciar(_("Lectura silenciada") if nuevo else _("Lectura activada"))

    def _snapshot_sesion(self) -> estado_sesion.SnapshotSesion:
        from bellbird.ui import gui_estado
        return gui_estado.snapshot_sesion(self)

    def _total_aportes_texto(self) -> str:
        from bellbird.ui import gui_estado
        return gui_estado.total_aportes_texto(self)

    def _anunciar_estado(self):
        from bellbird.ui import gui_estado
        gui_estado.anunciar_estado(self)

    def _anunciar_autor(self):
        from bellbird.ui import gui_estado
        gui_estado.anunciar_autor(self)

    def _leer_reciente(self, n: int):
        self._recientes.leer(n)

    def _describir_escena(self):
        from bellbird.ui import gui_estado
        gui_estado.describir_escena(self)

    def _anunciar_descripcion_escena(self, texto):
        self._descripcion_escena_en_curso = False
        anunciar(texto or _("Sin información de la escena."))

    # ── Enviar al chat del directo (API oficial) ─────────────────────────────

    def _on_enviar_live(self, event):
        from bellbird.ui import gui_envio_chat
        gui_envio_chat.on_enviar_live(self, event)

    def _enviar_live_redactado(self, texto):
        from bellbird.ui import gui_envio_chat
        gui_envio_chat.enviar_live_redactado(self, texto)

    def _accion_api(self, accion, mensaje_ok: str, sonido: str = "enviado") -> None:
        from bellbird.ui import gui_envio_chat
        gui_envio_chat.accion_api(self, accion, mensaje_ok, sonido)

    def _api_ok(self, mensaje, sonido: str = "enviado"):
        from bellbird.ui import gui_envio_chat
        gui_envio_chat.api_ok(self, mensaje, sonido)

    def _api_err(self, exc):
        from bellbird.ui import gui_envio_chat
        gui_envio_chat.api_err(self, exc)

    def _actualizar_estado_online(self):
        from bellbird.ui import gui_envio_chat
        gui_envio_chat.actualizar_estado_online(self)

    def _actualizar_motivo_redaccion(self):
        from bellbird.ui import gui_envio_chat
        gui_envio_chat.actualizar_motivo_redaccion(self)

    def _sesion_api_disponible(self) -> bool:
        return bool(youtube_api.google_disponible() and credenciales.hay_sesion())

    def _iniciar_programados_si_corresponde(self, ahora: float) -> None:
        from bellbird.ui import gui_envio_chat
        gui_envio_chat.iniciar_programados_si_corresponde(self, ahora)

    def _enviar_programado(self, mensaje: dict, ahora: float) -> None:
        from bellbird.ui import gui_envio_chat
        gui_envio_chat.enviar_programado(self, mensaje, ahora)

    def _programado_enviado(self, mensaje: dict) -> None:
        from bellbird.ui import gui_envio_chat
        gui_envio_chat.programado_enviado(self, mensaje)

    def _programado_fallo(self, exc) -> None:
        from bellbird.ui import gui_envio_chat
        gui_envio_chat.programado_fallo(self, exc)

    def _procesar_programado(self) -> None:
        from bellbird.ui import gui_envio_chat
        gui_envio_chat.procesar_programado(self)

    def _moderar(self, autor: str, canal_id: str, segundos: int | None) -> None:
        from bellbird.ui import gui_envio_chat
        gui_envio_chat.moderar(self, autor, canal_id, segundos)

    # ── Chat: teclado, menú, copiar, silenciar ───────────────────────────────

    def _on_chat_key(self, event):
        k = event.GetKeyCode()
        # La orilla suena sin consumir la tecla: NVDA sigue leyendo la fila.
        if sonidos_eventos.es_orilla(k, self.lb_chat.GetSelection(), self.lb_chat.GetCount()):
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

        menu.Append(id_copiar,  _("Copiar mensaje"))
        menu.Append(id_copiar2, _("Copiar todo (autor: mensaje, hora)"))
        menu.Append(id_releer,  _("Leer en voz alta"))
        menu.AppendSeparator()
        menu.Append(id_link,    _("Abrir enlace"))
        menu.AppendSeparator()

        registro_sel = self._get_selected_data()
        autor = registro_sel.autor if registro_sel else ""
        if autor:
            autor_mostrado = alias.visible(autor)
            if self._autor_esta_silenciado(autor):
                menu.Append(id_rehab, _("Rehabilitar a {autor} (dejar de silenciar)").format(autor=autor_mostrado))
            else:
                menu.Append(id_sil_tts,  _("Silenciar voz de {autor}").format(autor=autor_mostrado))
                menu.Append(id_sil_full, _("Ocultar y silenciar a {autor}").format(autor=autor_mostrado))
            if alias.clave(autor) not in alias.vigente():
                menu.Append(id_alias, _("Poner &alias a {autor}…").format(autor=autor_mostrado))
            else:
                menu.Append(id_alias, _("Cambiar el &alias de {autor}…").format(autor=autor_mostrado))

        id_ban     = wx.NewIdRef()
        id_timeout = wx.NewIdRef()
        plataforma_sel = registro_sel.plataforma if registro_sel else ""
        identificador_sel = registro_sel.identificador if registro_sel else ""
        moderable = bool(autor and plataforma_sel == "youtube" and identificador_sel
                         and self.sesion.live_chat_id
                         and youtube_api.google_disponible() and credenciales.hay_sesion())
        if moderable:
            menu.AppendSeparator()
            menu.Append(id_timeout, _("Suspender temporalmente a {autor} (5 minutos)").format(autor=autor_mostrado))
            menu.Append(id_ban,     _("Ocultar a {autor} en el canal de YouTube").format(autor=autor_mostrado))
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
            self, _("Alias para {autor}. Déjalo vacío para eliminarlo.").format(autor=autor),
            _("Alias del usuario"), value=actual)
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
        self.chat_vivo.reconstruir()
        anunciar(_("Alias guardado, {nuevo}").format(nuevo=actualizado[alias.clave(autor)])
                  if nuevo.strip() else _("Alias eliminado"))

    def _copiar_mensaje(self):
        data = self._get_selected_data()
        if data is None:
            return
        mensaje = data.texto
        self._clipboard_set(mensaje)
        _snd.reproducir("copiar")
        anunciar(_("Mensaje copiado"))

    def _copiar_enlace_directo(self):
        enlace = self.sesion.enlace_directo
        if not enlace:
            anunciar(_("No hay ningún directo conectado."))
            return
        self._clipboard_set(enlace)
        _snd.reproducir("copiar")
        anunciar(_("Enlace del directo copiado."))

    def _copiar_todo(self):
        data = self._get_selected_data()
        if data is None:
            return
        linea = f"{data.autor}: {data.texto}, {data.hora}"
        if data.monto:
            linea += f" [{data.monto}]"
        self._clipboard_set(linea)
        _snd.reproducir("copiar")
        anunciar(_("Línea copiada"))

    def _releer_mensaje(self):
        data = self._get_selected_data()
        if data is None:
            return
        from bellbird.voice.tts_worker import construir_tts
        self._cola.put({"texto_tts": construir_tts(data.autor, data.texto, self._config),
                        "autor": data.autor})

    def _abrir_enlace(self):
        data = self._get_selected_data()
        if data is None:
            return
        urls = _URL_RE.findall(data.texto)
        if not urls:
            anunciar(_("No se encontró ningún enlace"))
            wx.MessageBox(_("No se encontró ningún enlace en este mensaje."),
                          _("Sin enlace"), wx.OK | wx.ICON_INFORMATION, self)
            return
        webbrowser.open(urls[0])
        anunciar(_("Abriendo enlace"))

    # ── Silenciado en caliente ───────────────────────────────────────────────

    def _silenciar_autor(self, autor: str, ocultar: bool) -> None:
        if not autor:
            return
        al = autor.lower().strip()
        self._config.setdefault("silenciados_runtime", set()).add(al)
        sil_oculto = self._config.setdefault("silenciados_ocultar", set())
        if ocultar:
            sil_oculto.add(al)
            self.chat_vivo.reconstruir()
        else:
            sil_oculto.discard(al)
        # Traductores: {autor} es el autor del mensaje.
        anunciar(_("{autor} silenciado").format(autor=autor))

    def _rehabilitar_autor(self, autor: str) -> None:
        if not autor:
            return
        al = autor.lower().strip()
        self._config.setdefault("silenciados_runtime", set()).discard(al)
        self._config.setdefault("silenciados_ocultar", set()).discard(al)
        self.chat_vivo.reconstruir()
        # Traductores: {autor} es el autor del mensaje.
        anunciar(_("{autor} rehabilitado").format(autor=autor))

    def _autor_esta_silenciado(self, autor: str) -> bool:
        return autor.lower().strip() in self._config.get("silenciados_runtime", set())

    def _autor_esta_oculto(self, autor: str) -> bool:
        return autor.lower().strip() in self._config.get("silenciados_ocultar", set())

    # ── Selección y portapapeles ─────────────────────────────────────────────

    def _get_selected_data(self):
        idx = self.lb_chat.GetSelection()
        if idx == wx.NOT_FOUND:
            return None
        return self.chat_vivo.modelo.dato_en_fila(idx)

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
            puede_vetar = callable(getattr(event, "CanVeto", None)) and event.CanVeto()
            if mensaje is not None and puede_vetar:
                # Traductores: título del cuadro para salir.
                dialogo = wx.MessageDialog(
                    self, mensaje, _("Salir"),
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
        self.chat_vivo.descartar()
        hilos_previos = diagnostico.hilos_vivos_de_la_aplicacion()
        if apagado.hilos_captura_vivos(hilos_previos):
            # Traductores: aviso mientras se cierra la app.
            anunciar(_("Cerrando"))
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
            self._recientes.cerrar()
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
        if descartes.hay_que_avisar(self._stats.descartados, self.sesion.descartes_avisado):
            try:
                _snd.reproducir("aviso")
            except Exception:
                pass
            anunciar(descartes.frase_aviso(self._config.get("umbral_solo_nombre", 0)))
            self.sesion.descartes_avisado = True

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
        # No tocar el modelo ni la lista aquí: se encola y se procesa en el
        # volcado agrupado (ver volcar) para no disparar un
        # Append/Delete por mensaje mientras NVDA navega la lista.
        registro = MensajeChat(
            plataforma=plataforma, autor=autor, identificador=canal_id,
            texto=mensaje, hora=hora, tipo=tipo, monto=monto, rol=rol)
        self.chat_vivo.encolar(registro)

    def set_conectado(self, conectado: bool,
                        sonido_desconexion: str = "desconectado") -> None:
        if not self._alive:
            return
        estaba = self._conectado
        self._conectado = conectado
        if conectado:
            if not estaba:
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
                self._fijar_tipo(_(MENSAJE_INICIAL))
                # El fin del directo de TikTok llega con su propio sonido;
                # el resto de los cortes sigue sonando «desconectado».
                _snd.reproducir(sonido_desconexion)
                # Traductores: aviso al desconectar.
                anunciar(_("Desconectado"))
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
        self.sesion = SesionConectada()
        # Chat: datos, lista visible y lo que aún estaba en cola sin volcar (es
        # de la sesión que se cierra; no debe colarse en la siguiente).
        self.chat_vivo.descartar()
        self.chat_vivo.modelo.limpiar()
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
        t = self.sesion.tipo_video
        if t == deteccion.LIVE:
            msg = _("Conectado al directo. Leyendo el chat.")
        elif t == deteccion.UPCOMING:
            msg = _("Directo programado. Aún no hay chat; puedes ver los comentarios.")
        elif t == deteccion.VOD:
            msg = _("Vídeo conectado. Comentarios y reproductor disponibles.")
        else:
            # Traductores: aviso genérico al conectar.
            msg = _("Conectado.")
        anunciar(msg)

    def set_live_chat_id(self, live_chat_id: str, causa: str = "",
                         video_id: str | None = None, propio: bool = False) -> None:
        if not self._alive:
            return
        if not self.sesion.acepta_chat_de(video_id):
            return
        self.sesion.live_chat_id = live_chat_id or ""
        self.sesion.causa_sin_chat = causa or ""
        self.sesion.chat_propio = bool(propio)
        self._actualizar_estado_online()

    def set_espectadores(self, n: int, total: int | None = None) -> None:
        """Espectadores en vivo; TikTok lo refresca cada pocos segundos."""
        if not self._alive:
            return
        for clave, valor in (("vistas", n), ("vistas_total", total)):
            try:    self._metadatos[clave] = int(valor)
            except Exception: pass

    def set_inicio_directo(self, comienzo: str) -> None:
        if not self._alive:
            return
        self._metadatos["comienzo_directo"] = comienzo or ""

    def set_tipo_video(self, tipo: str, video_id: str) -> None:
        if not self._alive:
            return
        self.sesion.tipo_video = tipo
        self.sesion.video_id = video_id or ""
        self.sesion.es_tiktok = False   # esta ruta es la de YouTube
        # Empezar el chat en limpio en cada conexión: el reset al desconectar ya
        # lo hace, pero así garantizamos que nunca quede nada del vídeo anterior.
        self.chat_vivo.descartar()
        self.chat_vivo.modelo.limpiar()
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
            self._fijar_tipo(_("Directo: leyendo el chat."))
            self.nb.ChangeSelection(PAG_CHAT)
        elif tipo == deteccion.UPCOMING:
            self._fijar_tipo(_("Directo programado: aún sin chat. Hay comentarios."))
            self.nb.ChangeSelection(PAG_COMENTARIOS)
        elif tipo == deteccion.VOD:
            self._fijar_tipo(_("Vídeo subido: comentarios y reproductor."))
            self.nb.ChangeSelection(PAG_COMENTARIOS)
        else:
            self._fijar_tipo(_("Tipo no determinado: intentando leer el chat."))
        self._actualizar_boton_directo()

    def configurar_tiktok(self, usuario: str, url_flujo: str) -> None:
        """Prepara la ventana para un directo de TikTok: chat en limpio, pestaña
        de chat al frente, comentarios fuera (TikTok no los tiene aquí) y el
        reproductor con el flujo de TikTok (FLV, o HLS si no hay FLV). Lo llama main vía wx.CallAfter."""
        if not self._alive:
            return
        reconexion = self.sesion.es_reconexion_tiktok(usuario)
        previo = self.sesion.url_flujo_tiktok
        self.sesion.tipo_video = deteccion.LIVE
        self.sesion.es_tiktok = True
        self.sesion.usuario_tiktok = usuario or ""
        self.sesion.url_flujo_tiktok = url_flujo or ""
        if not reconexion:
            self.chat_vivo.descartar()
            self.chat_vivo.modelo.limpiar()
            self._sc_totales.clear()
            try:    self.lb_chat.Clear()
            except Exception: pass
        try:    self._com_panel.mostrar_no_disponible(
                    _("Los comentarios no están disponibles en los directos de TikTok."))
        except Exception: pass
        if not (reconexion
                and flujo_tiktok.mismo_flujo(url_flujo, previo)):
            autoplay = (False if reconexion
                        else bool(self._config.get("autoplay_reproductor", True)))
            try:    self._rep_panel.set_flujo(url_flujo, autoplay=autoplay)
            except Exception as exc: logger.debug("reproductor tiktok: %s", exc)
        self._fijar_tipo(_("Directo de TikTok de @{usuario}: leyendo el chat.").format(usuario=usuario))
        if not reconexion:
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
            # Traductores: pestaña con los datos del vídeo.
            self.nb.AddPage(self._pag_info, _("Información"))
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
            # Formato tipo navegador: «Nombre del vídeo — Bellbird».
            # Traductores: {titulo} es el vídeo y {app} la app.
            self.SetTitle(_("{titulo} — {app}").format(titulo=self._titulo_stream, app=APP_NAME))
        else:
            # Traductores: título de la ventana: nombre de la app y versión.
            self.SetTitle(_("{app} v{version}").format(app=APP_NAME, version=APP_VERSION))

    def auto_conectar(self) -> None:
        self._on_conectar(None)

    def poblar_voces(self, voces: list, idx_actual: int = 0) -> None:
        # Vaciar el submenú de voz y reconstruir con radio items.
        for it in list(self.voz_submenu.GetMenuItems()):
            self.voz_submenu.Delete(it)
        if not voces:
            it = self.voz_submenu.Append(wx.ID_ANY, _("(no disponible)"))
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
        idx = _IDX_FILTRO.get(_NOMBRES_FILTRO[0] if self.chat_vivo.filtro is None else "", 0)
        # Buscar el índice cuyo valor coincide con el filtro del chat.
        for i, (_sin_uso, val) in enumerate(FILTROS):
            if val == self.chat_vivo.filtro:
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
            from bellbird.voice.tts_worker import quitar_emojis
            msg = quitar_emojis(msg)
        return texto_fila(autor, msg, hora, tipo, monto)

    def _set_conectado_ui(self, conectado: bool) -> None:
        # Botón (toggle), items de menú Conectar/Desconectar y campo URL. El
        # resto (ocultar zona, sonido, título) lo gestiona set_conectado.
        self._conectando = False
        self.btn_conectar.SetLabel(_("&Desconectar") if conectado else _("&Conectar"))
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
        existen aún. Los ajustes de voz y «Ir a conexión» /
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
            if con and not self.sesion.es_tiktok and getattr(self, "_rep_panel", None):
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
        sin_tts = _(" [sin voz]") if self._config.get("silenciar_lectura", False) else ""
        if self._conectado and self._titulo_stream:
            # Traductores: {titulo} es el vídeo; {sin_tts} avisa si la lectura está silenciada.
            estado = _("Conectado: {titulo}{sin_tts}").format(titulo=self._titulo_stream[:35], sin_tts=sin_tts)
        elif self._conectado:
            # Traductores: {sin_tts} avisa si la lectura está silenciada.
            estado = _("Conectado{sin_tts}").format(sin_tts=sin_tts)
        else:
            # Traductores: {sin_tts} avisa si la lectura está silenciada.
            estado = _("Desconectado{sin_tts}").format(sin_tts=sin_tts)
        self.sb.SetStatusText(estado, 0)

        try:    self.sb.SetStatusText(_("Voz vel: {valor}").format(valor=self._worker.get_rate()), 1)
        except Exception: self.sb.SetStatusText(_("Voz vel: --"), 1)

        nombre = self._voz_nombre or "—"
        if len(nombre) > 28:
            nombre = nombre[:25] + "..."
        # Traductores: {nombre} es la voz activa.
        self.sb.SetStatusText(_("Voz: {nombre}").format(nombre=nombre), 2)

        # Traductores: {n} son los mensajes en cola.
        try:    self.sb.SetStatusText(_("Cola: {n}").format(n=self._cola.qsize()), 3)
        # Traductores: la raya indica que no hay dato.
        except Exception: self.sb.SetStatusText(_("Cola: —"), 3)
        # Traductores: {n} son los mensajes leídos.
        try:    self.sb.SetStatusText(_("Leídos: {n}").format(n=self._stats.leidos), 4)
        # Traductores: la raya indica que no hay dato.
        except Exception: self.sb.SetStatusText(_("Leídos: —"), 4)

        try:    self.sb.SetStatusText(_("Voz vol: {valor}%").format(valor=self._worker.get_volume()), 5)
        except Exception: self.sb.SetStatusText(_("Voz vol: --"), 5)

        if self._config.get("mostrar_total_superchats", True):
            self.sb.SetStatusText(self._formato_total_sc(), 6)
        else:
            self.sb.SetStatusText("", 6)

    # ── Acumulación de Super Chats ───────────────────────────────────────────

    def _sumar_superchat(self, monto: str) -> None:
        from bellbird.capture.montos import sumar_monto
        sumar_monto(self._sc_totales, monto)

    def _formato_total_sc(self) -> str:
        try:    n = self._stats.superchats
        except Exception: n = 0
        importes = texto_importes(self._sc_totales)
        # Traductores: SC abrevia Super Chats; {n} e {importes} son cantidad e importes.
        if not importes:
            return _("SC: {n}").format(n=n)
        return _("SC: {n} ({importes})").format(n=n, importes=importes)


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
        frame.chat_vivo.filtro = FILTROS[idx_f][1]
        frame._marcar_filtro()

    # Restaurar silenciado de sonidos si la sesión anterior lo tenía activo.
    if config.get("silenciar_sonidos", False):
        _snd.silenciar_todo(True)
    frame._sincronizar_checks()

    if url_inicial:
        frame.set_url(url_inicial)

    frame.Show()
    try:
        frame.Raise()
        frame.txt_url.SetFocus()
    except Exception:
        pass
    from bellbird.ui import gui_actualizar_app, gui_directo_huerfano
    gui_actualizar_app.programar_confirmacion_arranque()
    gui_actualizar_app.programar_resultado_actualizacion(frame)
    gui_actualizar_app.programar_aviso_version(frame)
    gui_directo_huerfano.programar_revision(frame)
    if config.get("sonido_inicio", True):
        diagnostico.crear_hilo(lambda: _snd.reproducir("app_inicio"), "SonidoInicio").start()
    wx.CallAfter(frame._arrancar_precalentamiento)

    if url_inicial and iniciar_captura_cb:
        wx.CallAfter(frame.auto_conectar)

    app.MainLoop()
    _gui_frame = None

    try:    logging.getLogger().removeHandler(h)
    except Exception: pass
