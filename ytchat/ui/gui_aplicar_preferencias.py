"""Preferencias aplicadas en caliente sin reabrir la app.

Los cuerpos de estas funciones son el antiguo
`YTChatFrame._aplicar_preferencias_en_caliente`, partido por lo que aplica
cada una (voz, interfaz y vista, reproductor, música). En la clase queda un
delegado de una línea. Los nombres que las pruebas reemplazan en el módulo
`gui` (`anunciar`, `wx`, `parsear_atajos`, `escala_voz`) se acceden por el
módulo en el momento de la llamada, nunca con un `from` directo.
"""

from __future__ import annotations

from ytchat.core import diagnostico


logger = diagnostico.obtener_logger(__name__)


def aplicar_en_caliente(frame):
    voces_actuales = _reconstruir_atajos_y_menu(frame)
    _aplicar_voz(frame, voces_actuales)
    _aplicar_ajustes_de_voz(frame)
    _aplicar_interfaz_y_vista(frame)
    _aplicar_reproductor(frame)
    _aplicar_musica(frame)
    _aplicar_recientes(frame)
    frame._actualizar_vigilante_obs()
    from ytchat.ui import gui as _gui
    _gui.anunciar("Preferencias aplicadas")


def _reconstruir_atajos_y_menu(frame):
    from ytchat.ui import gui as _gui
    # Reconstruir atajos y menú por si cambiaron las teclas.
    frame._atajos = _gui.parsear_atajos(frame._config.get("atajos_raw", {}))
    try:
        # Solo los radio items: si no había voces, el submenú tiene un item
        # deshabilitado «(no disponible)» que no debe repoblarse como voz.
        voces_actuales = [it.GetItemLabelText()
                          for it in frame.voz_submenu.GetMenuItems()
                          if it.GetKind() == _gui.wx.ITEM_RADIO]
    except Exception:
        voces_actuales = []
    frame._build_menubar()
    return voces_actuales


def _aplicar_voz(frame, voces_actuales):
    from ytchat.ui import gui as _gui
    # Preferencias puede haber cambiado el motor o la voz: aplicarlo en
    # caliente. Con el motor nuevo hay que repoblar el menú de voz.
    try:
        motor_cfg = frame._config.get("motor") or "sapi"
        if motor_cfg != (frame._worker.motor_activo() or ""):
            from ytchat.voice import motores
            voces_nuevas = motores.listar_voces(motor_cfg)
            idx_nuevo = _gui.escala_voz.resolver_voz(
                frame._config.get("voz"), voces_nuevas)
            frame.poblar_voces(voces_nuevas, 0 if idx_nuevo is None else idx_nuevo)
            frame._worker.cambiar_motor(motor_cfg, frame._config.get("voz"))
            _gui.anunciar(f"Motor de voz: "
                          f"{motores.NOMBRES.get(motor_cfg, motor_cfg)}")
        else:
            # Restaurar submenú de voz tras reconstruir (con lista vacía,
            # poblar_voces repone el item «(no disponible)»).
            frame.poblar_voces(voces_actuales, frame._voz_idx)
            if voces_actuales:
                # Preferencias puede haber cambiado la voz: aplicarla.
                idx_cfg = _gui.escala_voz.resolver_voz(
                    frame._config.get("voz"), voces_actuales)
                if idx_cfg is not None and idx_cfg != frame._voz_idx:
                    frame._aplicar_voz(idx_cfg)
    except Exception as exc:
        logger.debug("aplicar voz desde preferencias: %s", exc)


def _aplicar_ajustes_de_voz(frame):
    from ytchat.ui import gui as _gui
    # Velocidad, volumen y tono absolutos: solo si cambiaron, sin anunciar.
    try:
        vel_cfg = _gui.escala_voz.ajustar_velocidad(
            int(frame._config.get("velocidad_voz", _gui.escala_voz.VELOCIDAD_NORMAL)), 0)
        if vel_cfg != frame._worker.get_rate():
            frame._worker.fijar_rate(vel_cfg)
        vol_cfg = max(0, min(100, int(round(
            float(frame._config.get("volumen", 1.0)) * 100))))
        if vol_cfg != frame._worker.get_volume():
            frame._worker.fijar_volumen_pct(vol_cfg)
        tono_cfg = max(0, min(100, int(frame._config.get("tono", 50))))
        if tono_cfg != frame._worker.get_tono():
            frame._worker.fijar_tono(tono_cfg)
        # ElevenLabs: tope, «solo lo importante» y voz de respaldo también
        # se aplican en caliente (el worker los lee solo al crearse).
        frame._worker.configurar_elevenlabs(
            int(frame._config.get("elevenlabs_tope", 0) or 0),
            bool(frame._config.get("elevenlabs_solo_importantes", False)),
            frame._config.get("voz_respaldo") or "")
    except Exception as exc:
        logger.debug("aplicar ajustes de voz desde preferencias: %s", exc)


def _aplicar_interfaz_y_vista(frame):
    from ytchat.ui import gui as _gui
    frame._marcar_filtro()
    frame._sincronizar_checks()
    try:
        frame.mi_avisos_sobrecarga.Check(
            bool(frame._config.get("avisar_sobrecarga", True)))
    except Exception as exc:
        logger.debug("aplicar aviso de sobrecarga desde preferencias: %s", exc, exc_info=True)
    # Reconstruir la lista por si cambió "quitar emojis" o el filtro.
    frame._rebuild_listbox()
    # Restaurar estado de los items de conexión y del envío al chat tras
    # reconstruir el menú.
    frame._set_conectado_ui(frame._conectado)
    frame._actualizar_estado_online()
    # Tamaño de fuente del chat.
    try:
        pt = int(frame._config.get("tamanio_fuente_chat", 12))
        frame.lb_chat.SetFont(_gui.wx.Font(pt, _gui.wx.FONTFAMILY_DEFAULT,
                                           _gui.wx.FONTSTYLE_NORMAL, _gui.wx.FONTWEIGHT_NORMAL))
    except Exception as exc:
        logger.debug("aplicar fuente del chat desde preferencias: %s", exc, exc_info=True)
    # Panel de información del vídeo: mostrar u ocultar la pestaña.
    try:
        frame.set_metadatos_visible(bool(frame._config.get("mostrar_metadatos", True)))
    except Exception as exc:
        logger.debug("aplicar visibilidad de metadatos desde preferencias: %s", exc, exc_info=True)


def _aplicar_reproductor(frame):
    # Botones del reproductor: aplicar la preferencia al panel (que a su vez
    # sincroniza la casilla del menú vía on_botones_toggle).
    try:
        frame._rep_panel.set_botones_visibles(
            bool(frame._config.get("mostrar_botones_reproductor", True)))
        frame._rep_panel.set_solo_audio(
            bool(frame._config.get("reproductor_solo_audio", False)))
    except Exception as exc:
        logger.debug("aplicar botones del reproductor desde preferencias: %s", exc, exc_info=True)


def _aplicar_musica(frame):
    try:
        frame._musica.aplicar_preferencias()
    except Exception as exc:
        logger.debug("aplicar música desde preferencias: %s", exc, exc_info=True)


def _aplicar_recientes(frame):
    try:
        frame._recientes.aplicar_preferencias()
    except Exception as exc:
        logger.debug("aplicar recientes desde preferencias: %s", exc, exc_info=True)
