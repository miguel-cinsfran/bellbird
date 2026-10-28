"""Barra de menú de la ventana principal.

El cuerpo de `construir_menu` es el antiguo `YTChatFrame._build_menubar`,
movido sin cambios: cada etiqueta con su `&`, cada atajo, cada id, el orden
de los menús y de sus elementos, los textos de ayuda y los enlaces con los
manejadores quedan idénticos. En la clase queda un delegado de una línea
porque lo enlazan la construcción, las preferencias y las pruebas.
"""

from __future__ import annotations

import os
import webbrowser

import wx

from ytchat.core import diagnostico
from ytchat.core.idioma import _
from ytchat.core import paths
from ytchat.obs import obs_ventana
from ytchat.ui.accesibilidad import anunciar
from ytchat.ui.atajos_captura import ETIQUETAS

logger = diagnostico.obtener_logger(__name__)


def construir_menu(frame):
    from ytchat.ui.gui import (
        FILTROS, PAG_CHAT, PAG_COMENTARIOS, REG_CONEXION, REG_REPRODUCTOR,
    )
    anterior = frame.GetMenuBar()
    mb = wx.MenuBar()

    # Archivo
    m = wx.Menu()
    frame.mi_conectar = m.Append(wx.ID_ANY, _("&Conectar") + frame._accel("conectar"))
    frame.mi_desconectar = m.Append(wx.ID_ANY, _("&Desconectar") + frame._accel("desconectar"))
    frame.mi_copiar_enlace = m.Append(wx.ID_ANY, _("Copiar &enlace del directo") + frame._accel("copiar_enlace"))
    m.AppendSeparator()
    mi_historial = m.Append(wx.ID_ANY, _("&Historial de directos…") + frame._accel("abrir_historial"))
    m.AppendSeparator()
    mi_salir = m.Append(wx.ID_EXIT, _("&Salir") + "\tAlt+F4")
    mb.Append(m, _("&Archivo"))
    frame.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(frame._conectar_si_procede), frame.mi_conectar)
    frame.Bind(wx.EVT_MENU, lambda e: frame._desconectar_si_procede(), frame.mi_desconectar)
    frame._bind_menu(frame.mi_copiar_enlace, frame._copiar_enlace_directo)
    frame.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(frame._on_historial), mi_historial)
    frame.Bind(wx.EVT_MENU, lambda e: frame.Close(), mi_salir)
    # Ver
    _construir_menu_ver(frame, mb)

    # Chat
    m = wx.Menu()
    frame.mi_enviar_live = m.Append(
        wx.ID_ANY,
        _("&Enviar mensaje al chat del directo (solo YouTube)…") + frame._accel("enviar_chat"))
    m.AppendSeparator()
    sub_f = wx.Menu()
    frame.fi_items = []
    for i, (nombre, _sin_uso) in enumerate(FILTROS):
        it = sub_f.AppendRadioItem(wx.ID_ANY, nombre)
        frame.fi_items.append(it)
        frame._bind_menu(it, frame._aplicar_filtro, i)
    frame._mi_filtro_sub = m.AppendSubMenu(sub_f, _("&Filtro de mensajes"))
    mb.Append(m, _("&Chat"))
    frame.Bind(wx.EVT_MENU, frame._on_enviar_live, frame.mi_enviar_live)

    # Voz (TTS)
    m = wx.Menu()
    frame.mi_pausa = m.Append(wx.ID_ANY, _("&Pausar lectura") + frame._accel("pausa"))
    mi_det = m.Append(wx.ID_ANY, _("&Detener voz") + frame._accel("detener_tts"))
    mi_vac = m.Append(wx.ID_ANY, _("&Vaciar cola"))
    # Estas tres actúan sobre una lectura en curso: sin conexión no hay nada
    # que pausar/detener/vaciar. Los ajustes de voz de abajo sí quedan libres.
    frame._mi_voz_conexion = [frame.mi_pausa, mi_det, mi_vac]
    m.AppendSeparator()
    mi_vmenos = m.Append(wx.ID_ANY, _("Hablar más &lento") + frame._accel("velocidad_menos"))
    mi_vmas   = m.Append(wx.ID_ANY, _("Hablar más &rápido") + frame._accel("velocidad_mas"))
    mi_volm   = m.Append(wx.ID_ANY, _("&Bajar volumen de la voz") + frame._accel("volumen_menos"))
    mi_volM   = m.Append(wx.ID_ANY, _("&Subir volumen de la voz") + frame._accel("volumen_mas"))
    m.AppendSeparator()
    frame.mi_sil_lectura = m.AppendCheckItem(
        wx.ID_ANY, _("S&ilenciar lectura TTS") + frame._accel("silenciar_lectura"))
    frame.mi_sil_sonidos = m.AppendCheckItem(
        wx.ID_ANY, _("Silenciar s&onidos") + frame._accel("silenciar_sonidos"))
    m.AppendSeparator()
    frame.voz_submenu = wx.Menu()
    m.AppendSubMenu(frame.voz_submenu, _("Seleccionar vo&z"))
    mb.Append(m, _("Vo&z"))
    frame._bind_menu(frame.mi_pausa, frame._on_pausa, None)
    frame._bind_menu(mi_det, frame._on_detener_tts, None)
    frame._bind_menu(mi_vac, frame._on_vaciar, None)
    frame._bind_menu(mi_vmenos, frame._ajustar_rate, -1)
    frame._bind_menu(mi_vmas, frame._ajustar_rate, +1)
    frame._bind_menu(mi_volm, frame._ajustar_volume, -5)
    frame._bind_menu(mi_volM, frame._ajustar_volume, +5)
    frame._bind_menu(frame.mi_sil_lectura, frame._toggle_silenciar_lectura)
    frame._bind_menu(frame.mi_sil_sonidos, frame._toggle_silenciar_sonidos)

    # Reproductor
    m = wx.Menu()
    mi_rep_play  = m.Append(wx.ID_ANY, _("&Reproducir o pausa") + frame._accel("rep_play"))
    mi_rep_retro = m.Append(wx.ID_ANY, _("R&etroceder 1 minuto") + frame._accel("rep_retro"))
    mi_rep_avanz = m.Append(wx.ID_ANY, _("&Avanzar 1 minuto") + frame._accel("rep_avanz"))
    mi_rep_directo = m.Append(wx.ID_ANY, _("&Ir al directo") + frame._accel("rep_directo"))
    mi_rep_stop  = m.Append(wx.ID_ANY, _("De&tener reproducción") + frame._accel("rep_detener"))
    mi_rep_mute  = m.Append(wx.ID_ANY, _("&Silenciar o activar audio") + frame._accel("rep_mute"))
    mi_rep_fs    = m.Append(wx.ID_ANY, _("Pantalla &completa") + frame._accel("pantalla_completa"))
    # Submenú de calidad (radio). Se elige la disponible más cercana.
    sub_cal = wx.Menu()
    for etiqueta, altura in ((_("Automática"), None), (_("1080p"), 1080), (_("720p"), 720),
                             (_("480p"), 480), (_("360p"), 360), (_("240p"), 240), (_("144p"), 144)):
        it = sub_cal.AppendRadioItem(wx.ID_ANY, etiqueta)
        frame._bind_menu(it, frame._rep_accion, "set_calidad", altura)
    m.AppendSubMenu(sub_cal, _("Ca&lidad del vídeo"))
    m.AppendSeparator()
    # Descargar este vídeo (solo YouTube, no live). Se habilita en
    # `_actualizar_menus_por_conexion` cuando hay URL reproducible.
    frame.mi_descargar_este = m.Append(
        wx.ID_ANY, _("Descargar este &vídeo"))
    m.AppendSeparator()
    mi_rep_volm  = m.Append(wx.ID_ANY, _("&Bajar volumen del reproductor") + frame._accel("rep_vol_menos"))
    mi_rep_volM  = m.Append(wx.ID_ANY, _("S&ubir volumen del reproductor") + frame._accel("rep_vol_mas"))
    m.AppendSeparator()
    frame.mi_rep_botones = m.AppendCheckItem(wx.ID_ANY, _("Mostrar botones en &pantalla"))
    frame.mi_rep_botones.Check(bool(frame._config.get("mostrar_botones_reproductor", True)))
    frame._bind_menu(frame.mi_rep_botones, frame._toggle_botones_rep)
    mb.Append(m, _("&Reproductor"))
    frame._bind_menu(mi_rep_play, frame._rep_accion, "_toggle_play")
    frame._bind_menu(mi_rep_retro, frame._rep_accion, "_buscar_rel", -60_000)
    frame._bind_menu(mi_rep_avanz, frame._rep_accion, "_buscar_rel", +60_000)
    frame._bind_menu(mi_rep_directo, frame._rep_accion, "ir_al_directo")
    frame._bind_menu(mi_rep_stop, frame._rep_accion, "_detener")
    frame._bind_menu(mi_rep_mute, frame._rep_accion, "_toggle_mute")
    frame._bind_menu(mi_rep_fs, frame._rep_accion, "alternar_pantalla_completa")
    frame.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(
        frame._abrir_descargas,
        url=frame._rep_panel.get_url_para_descarga() if frame._rep_panel else None),
        frame.mi_descargar_este)
    frame._bind_menu(mi_rep_volm, frame._rep_accion, "ajustar_volumen", -20)
    frame._bind_menu(mi_rep_volM, frame._rep_accion, "ajustar_volumen", +20)

    # Transmisión
    _construir_menu_transmision(frame, mb)

    # Música
    _construir_menu_musica(frame, mb)

    # Herramientas
    m = wx.Menu()
    # Gestor de descargas: SIEMPRE habilitado (funciona sin conexión de
    # chat, abriendo una URL pegada a mano). Ctrl+S es el atajo.
    frame.mi_descargas = m.Append(
        wx.ID_ANY, _("Gestor de &descargas…") + frame._accel("descargas_abrir"))
    frame.mi_actualizar_ytdlp = m.Append(wx.ID_ANY, _("&Actualizar yt-dlp"))
    m.AppendSeparator()
    mi_pref = m.Append(wx.ID_ANY, _("&Preferencias…") + frame._accel("abrir_preferencias"))
    mb.Append(m, _("&Herramientas"))
    frame.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(frame._abrir_descargas), frame.mi_descargas)
    frame.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(frame._on_actualizar_ytdlp, None),
              frame.mi_actualizar_ytdlp)
    frame.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(frame._on_preferencias, None), mi_pref)

    _construir_menu_ayuda(frame, mb)

    frame.SetMenuBar(mb)
    # Al reconstruir (Preferencias), la barra vieja solo se desengancha: hay
    # que destruirla, y el item de pausa nace como «Pausar» aunque la
    # lectura siga pausada.
    if anterior is not None:
        try:    anterior.Destroy()
        except Exception: pass
    frame._sincronizar_pausa()
    _registrar_menus(frame)


def _mostrar_obs() -> None:
    """Trae al frente la ventana principal de OBS, si está abierto."""
    texto = obs_ventana.mostrar()
    if texto:
        anunciar(texto)


def _construir_menu_transmision(frame, mb):
    from ytchat.ui import gui_transmitir
    m = wx.Menu()
    frame.mi_transmision = m.Append(
        wx.ID_ANY, _("&Panel de transmisión…") + frame._accel("abrir_transmision"))
    frame.mi_obs_micro = m.Append(
        wx.ID_ANY, _("Silenciar el &micrófono de OBS") + frame._accel("obs_micro"))
    frame.mi_mostrar_obs = m.Append(
        wx.ID_ANY, _("Mostrar &OBS") + frame._accel("mostrar_obs"))
    frame.mi_avisos_sobrecarga = m.AppendCheckItem(
        wx.ID_ANY,
        _("&Avisar cuando OBS no da abasto") + frame._accel("avisos_sobrecarga"))
    frame.mi_avisos_sobrecarga.Check(
        bool(frame._config.get("avisar_sobrecarga", True)))
    frame.mi_grabar_al_transmitir = m.AppendCheckItem(
        wx.ID_ANY, _("&Grabar también al transmitir"))
    frame.mi_grabar_al_transmitir.Check(
        bool(frame._config.get("grabar_al_transmitir", False)))
    mb.Append(m, _("&Transmisión"))
    frame.Bind(wx.EVT_MENU,
              lambda e: wx.CallAfter(frame._on_transmision, None),
              frame.mi_transmision)
    frame.Bind(wx.EVT_MENU, frame._on_obs_micro, frame.mi_obs_micro)
    frame._bind_menu(frame.mi_mostrar_obs, _mostrar_obs)
    frame._bind_menu(frame.mi_avisos_sobrecarga,
                     frame._alternar_aviso_sobrecarga)
    frame._bind_menu(frame.mi_grabar_al_transmitir,
                     gui_transmitir.alternar_grabar_al_transmitir, frame)


def _construir_menu_ayuda(frame, mb):
    m = wx.Menu()
    mi_guia = m.Append(wx.ID_ANY, _("&Guía de configuración de la API…"))
    mi_incidente = m.Append(wx.ID_ANY, _("&Marcar incidencia") + frame._accel("marcar_incidencia"))
    mi_registros = m.Append(wx.ID_ANY, _("Abrir la carpeta de &registros"))
    mi_actualizar_app = m.Append(wx.ID_ANY, _("&Buscar actualizaciones…"))
    mi_about = m.Append(wx.ID_ABOUT, _("&Acerca de"))
    mb.Append(m, _("A&yuda"))
    frame.Bind(wx.EVT_MENU, lambda e: webbrowser.open(
        "https://github.com/miguel-cinsfran/ytchat-tts/blob/main/docs/CONFIGURACION_API.md"),
        mi_guia)
    frame.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(
        frame._on_marcar_incidencia, None), mi_incidente)
    frame.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(
        abrir_carpeta_registros, frame), mi_registros)
    frame.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(
        frame._on_actualizar_app, None), mi_actualizar_app)
    frame.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(frame._on_about, None), mi_about)


def abrir_carpeta_registros(frame) -> None:
    """Abre en el explorador la carpeta con los registros de la aplicación."""
    try:
        os.startfile(str(paths.carpeta_datos()))  # noqa: S606
    except Exception as exc:
        wx.MessageBox(_("No se pudo abrir la carpeta de registros:\n\n{exc}").format(exc=exc),
                      _("Carpeta de registros"), wx.OK | wx.ICON_ERROR, frame)


def _registrar_menus(frame) -> None:
    """Anota cada comando del menú principal sin impedir que corra.

    Se enlaza después que los manejadores propios: wx llama primero al
    último enlazado, así este registra y con `Skip` sigue el del ítem.
    """
    def al_elegir(evento) -> None:
        ident = evento.GetId()
        logger.debug("MENU id=%s etiqueta=%s", ident,
                     _etiqueta_menu(frame, ident))
        evento.Skip()

    frame.Bind(wx.EVT_MENU, al_elegir)


def _etiqueta_menu(frame, ident: int) -> str:
    """El texto del ítem con ese id en la barra, sin `&` ni atajo."""
    try:
        barra = frame.GetMenuBar()
        for indice in range(barra.GetMenuCount()):
            etiqueta = _buscar_en_menu(barra.GetMenu(indice), ident)
            if etiqueta is not None:
                return etiqueta
    except Exception:
        return "?"
    return "?"


def _buscar_en_menu(menu, ident: int):
    for item in menu.GetMenuItems():
        if item.GetId() == ident:
            return item.GetItemLabelText().replace("&", "").split("\t")[0]
        if item.IsSubMenu():
            etiqueta = _buscar_en_menu(item.GetSubMenu(), ident)
            if etiqueta is not None:
                return etiqueta
    return None


def _abrir_ia(frame):
    from ytchat.ui import ia_ventana
    ia_ventana.abrir_ventana(frame)


def _consulta_rapida(frame):
    from ytchat.ui import ia_consulta_rapida
    ia_consulta_rapida.consultar(frame)


def _construir_menu_ver(frame, mb):
    from ytchat.ui.gui import (
        PAG_CHAT, PAG_COMENTARIOS, REG_CONEXION, REG_REPRODUCTOR,
    )
    m = wx.Menu()
    mi_sig = m.Append(wx.ID_ANY, _("Región &siguiente") + "\tF6")
    mi_ant = m.Append(wx.ID_ANY, _("Región &anterior") + "\tShift+F6")
    m.AppendSeparator()
    mi_conx = m.Append(wx.ID_ANY, _("Ir a co&nexión (URL)"))
    mi_lista = m.Append(wx.ID_ANY, _("Ir a la &lista del panel actual") + frame._accel("ir_lista"))
    mi_chat = m.Append(wx.ID_ANY, _("Ir a &Chat en vivo"))
    mi_com  = m.Append(wx.ID_ANY, _("Ir a Co&mentarios"))
    mi_rep  = m.Append(wx.ID_ANY, _("Ir al &Reproductor"))
    m.AppendSeparator()
    mi_estado = m.Append(wx.ID_ANY, _("Anunciar &estado") + frame._accel("anunciar_estado"))
    mi_autor = m.Append(wx.ID_ANY, _("Anunciar a&utor del último mensaje") + frame._accel("anunciar_autor"))
    sub_rec = wx.Menu()
    for n in range(1, 11):
        accion = f"chat_reciente_{n}"
        item = sub_rec.Append(wx.ID_ANY, _(ETIQUETAS[accion]) + frame._accel(accion))
        frame._bind_menu(item, frame._leer_reciente, n)
    m.AppendSubMenu(sub_rec, _("Mensajes recientes &del chat"))
    mi_escena = m.Append(wx.ID_ANY, _("Describir la escena de &OBS") + frame._accel("describir_escena"))
    mi_ia = m.Append(wx.ID_ANY, _("Preguntar a la &IA sobre la imagen…") + frame._accel("preguntar_ia"))
    mi_rapida = m.Append(wx.ID_ANY, _("Consul&ta rápida a la IA") + frame._accel("consulta_rapida_ia"))
    mb.Append(m, _("&Ver"))
    frame.Bind(wx.EVT_MENU, lambda e: frame._navegar_region(+1), mi_sig)
    frame.Bind(wx.EVT_MENU, lambda e: frame._navegar_region(-1), mi_ant)
    frame.Bind(wx.EVT_MENU, lambda e: frame._ir_region(REG_CONEXION), mi_conx)
    frame.Bind(wx.EVT_MENU, lambda e: frame._ir_lista(), mi_lista)
    frame.Bind(wx.EVT_MENU, lambda e: frame._ir_pestana(PAG_CHAT), mi_chat)
    frame.Bind(wx.EVT_MENU, lambda e: frame._ir_pestana(PAG_COMENTARIOS), mi_com)
    frame.Bind(wx.EVT_MENU, lambda e: frame._ir_region(REG_REPRODUCTOR), mi_rep)
    frame._bind_menu(mi_estado, frame._anunciar_estado)
    frame._bind_menu(mi_autor, frame._anunciar_autor)
    frame._bind_menu(mi_escena, frame._describir_escena)
    frame._bind_menu(mi_ia, _abrir_ia, frame)
    frame._bind_menu(mi_rapida, _consulta_rapida, frame)
    # De «Ver», solo tiene sentido con conexión la navegación por paneles;
    # «Ir a conexión (URL)» y «Anunciar estado» quedan siempre disponibles.
    frame._mi_ver_conexion = [mi_sig, mi_ant, mi_lista, mi_chat, mi_com, mi_rep]


def _construir_menu_musica(frame, mb):
    m = wx.Menu()
    frame.mi_musica_ventana = m.Append(
        wx.ID_ANY, _("&Elegir música…") + frame._accel("musica_ventana"))
    m.AppendSeparator()
    frame.mi_musica_play = m.Append(
        wx.ID_ANY, _("Reproducir o &pausar") + frame._accel("musica_play"))
    frame.mi_musica_siguiente = m.Append(
        wx.ID_ANY, _("&Siguiente canción") + frame._accel("musica_siguiente"))
    frame.mi_musica_anterior = m.Append(
        wx.ID_ANY, _("Canción &anterior") + frame._accel("musica_anterior"))
    frame.mi_musica_vol_mas = m.Append(
        wx.ID_ANY, _("Subir el &volumen") + frame._accel("musica_vol_mas"))
    frame.mi_musica_vol_menos = m.Append(
        wx.ID_ANY, _("&Bajar el volumen") + frame._accel("musica_vol_menos"))
    frame.mi_musica_que_suena = m.Append(
        wx.ID_ANY, _("&Qué suena") + frame._accel("musica_que_suena"))
    frame.mi_musica_adelantar = m.Append(
        wx.ID_ANY, _("Adelantar 10 segu&ndos") + frame._accel("musica_adelantar"))
    frame.mi_musica_retroceder = m.Append(
        wx.ID_ANY, _("Re&troceder 10 segundos") + frame._accel("musica_retroceder"))
    m.AppendSeparator()
    frame.mi_musica_silenciar = m.AppendCheckItem(
        wx.ID_ANY, _("Silenciar la &música") + frame._accel("musica_silenciar"))
    mi_detener = m.Append(
        wx.ID_ANY, _("&Detener la música") + frame._accel("musica_detener"))
    frame.mi_musica_aleatorio = m.AppendCheckItem(
        wx.ID_ANY, _("&Orden aleatorio") + frame._accel("musica_aleatorio"))
    frame.mi_musica_aleatorio.Check(
        bool(frame._config.get("musica_aleatorio", False)))
    mi_repetir = m.Append(
        wx.ID_ANY, _("Cambiar la &repetición") + frame._accel("musica_repetir"))
    mb.Append(m, _("&Música"))
    for item, accion in (
            (frame.mi_musica_ventana, "abrir_ventana"),
            (frame.mi_musica_play, "reproducir_o_pausar"),
            (frame.mi_musica_siguiente, "siguiente"),
            (frame.mi_musica_anterior, "anterior"),
            (frame.mi_musica_vol_mas, "subir_volumen"),
            (frame.mi_musica_vol_menos, "bajar_volumen"),
            (frame.mi_musica_que_suena, "que_suena"),
            (frame.mi_musica_adelantar, "adelantar"),
            (frame.mi_musica_retroceder, "retroceder"),
            (frame.mi_musica_silenciar, "alternar_silencio"),
            (mi_detener, "detener"),
            (frame.mi_musica_aleatorio, "alternar_aleatorio"),
            (mi_repetir, "ciclar_repetir")):
        frame._bind_menu(item, lambda a=accion: getattr(frame._musica, a)())
