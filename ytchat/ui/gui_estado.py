"""Estado de sesión que se dice con F2 y descripción de escena.

Los cuerpos de estas funciones son los antiguos métodos de `YTChatFrame`
movidos sin cambios: `_snapshot_sesion`, `_total_aportes_texto`,
`_anunciar_estado`, `_anunciar_autor` y `_describir_escena`. En la clase
quedan delegados de una o dos líneas con el mismo nombre y la misma firma,
porque los usan el menú Ver, los atajos y las pruebas.

`_anunciar_descripcion_escena` queda en la clase: son dos líneas que solo
bajan una bandera y anuncian.

Los nombres que las pruebas reemplazan en el módulo `gui` (`anunciar`,
`GestorPanelObs`, `obs_activacion`, `obs_cliente`, `diagnostico`, `wx`,
`estado_sesion`, `deteccion`, `atajos_captura`, `overlay_servidor`,
`programados`, `descartes`, `obs_estado`, `time`) se acceden siempre por el
módulo en el momento de la llamada, nunca con un `from` directo.
"""

from __future__ import annotations

from ytchat.capture.montos import texto_importes


def _entero_en(meta, clave):
    valor = meta.get(clave)
    try:    return int(valor) if valor is not None else None
    except (TypeError, ValueError): return None


def snapshot_sesion(frame):
    """Reúne el estado actual para F2. Los datos del vídeo salen de los
    metadatos capturados al conectar (título, canal, espectadores)."""
    from ytchat.ui import gui as _gui
    # Tipo: hay que distinguir TikTok de YouTube (ambos son LIVE por dentro).
    if frame._conectado and frame.sesion.es_tiktok:
        tipo = "live_tiktok"
    elif frame.sesion.tipo_video == _gui.deteccion.LIVE:
        tipo = "live_youtube"
    elif frame.sesion.tipo_video == _gui.deteccion.VOD:
        tipo = "vod"
    elif frame.sesion.tipo_video == _gui.deteccion.UPCOMING:
        tipo = "upcoming"
    else:
        tipo = ""
    meta = frame._metadatos or {}
    espectadores = _entero_en(meta, "vistas")
    espectadores_total = _entero_en(meta, "vistas_total")
    def _seguro(fn, defecto):
        try:    return fn()
        except Exception: return defecto
    def _texto_atajo_directo():
        at = (frame._atajos or {}).get("rep_directo")
        return at.texto if at is not None else ""
    vigilante = getattr(frame, "_obs_vigilante", None)
    estado_obs = _seguro(lambda: vigilante.estado(), None) if vigilante else None
    transmision = estado_obs.transmision if estado_obs else None
    grabacion = estado_obs.grabacion if estado_obs else None
    supervisor = getattr(frame, "_supervisor", None)
    supervisada = _seguro(
        lambda: supervisor.frase_estado()
        if supervisor is not None and supervisor.activo else "", "")
    return _gui.estado_sesion.SnapshotSesion(
        conectado=frame._conectado,
        tipo=tipo,
        titulo=frame._titulo_stream,
        canal=(meta.get("canal") or "").strip(),
        espectadores=espectadores,
        espectadores_total=espectadores_total,
        segundos_directo=_seguro(lambda: int(_gui.time.time() - _gui.datetime.fromisoformat(
            meta["comienzo_directo"].replace("Z", "+00:00")).timestamp()), None),
        desfase_directo=_seguro(lambda: frame._rep_panel.frase_posicion_directo() if frame._rep_panel._desfase_relevo_segundos() > 0 else "", ""),
        atajo_directo=_seguro(
            lambda: _gui.atajos_captura.atajo_legible(_texto_atajo_directo()), ""),
        mensajes_leidos=_seguro(lambda: frame._stats.leidos, 0),
        aportes=_seguro(lambda: frame._stats.superchats, 0),
        total_aportes=frame._total_aportes_texto(),
        en_cola=_seguro(lambda: frame._cola.qsize(), 0),
        voz_velocidad=_seguro(lambda: frame._worker.get_rate(), 0),
        voz_volumen=_seguro(lambda: frame._worker.get_volume(), 0),
        lectura_silenciada=bool(frame._config.get("silenciar_lectura", False)),
        overlay_puerto=_gui.overlay_servidor.puerto_actual(),
        overlay_clientes=_gui.overlay_servidor.cuantos_miran(),
        programados_proximo=(
            _gui.programados.describir_proximo(frame._mensajes_programados, _gui.time.time())
            if frame._config.get("programados_activo", False) else ""),
        descartados=_gui.descartes.frase_estado(
            _seguro(lambda: frame._stats.descartados, 0)),
        musica=_seguro(lambda: frame._musica.texto_estado(), ""), igualando=_seguro(lambda: frame._musica.texto_igualando(), ""),
        obs_transmision=(_gui.obs_estado.frase_transmision(
            transmision["outputActive"], transmision["outputDuration"],
            transmision["outputSkippedFrames"], transmision["outputTotalFrames"])
            if transmision else ""),
        obs_grabacion=(_gui.obs_estado.frase_grabacion(
            grabacion["outputActive"], grabacion["outputPaused"],
            grabacion["outputTimecode"]) if grabacion else ""),
        obs_escena=(_gui.obs_estado.frase_escena_al_aire(estado_obs.escena)
                    if estado_obs else ""),
        transmision_supervisada=supervisada,
    )


def total_aportes_texto(frame) -> str:
    """Solo el importe acumulado de Super Chats (sin el «SC: n»), para F2."""
    return texto_importes(frame._sc_totales)


def anunciar_estado(frame):
    from ytchat.ui import gui as _gui
    toggles = frame._config.get("estado_toggles") or _gui.estado_sesion.ACTIVOS_DEFECTO
    texto = _gui.estado_sesion.formatear_estado(frame._snapshot_sesion(), toggles)
    _gui.anunciar(texto or "Sin información de estado.")


def anunciar_autor(frame):
    from ytchat.ui import gui as _gui
    # Por el lector, no por la voz: no espera detrás de la cola.
    autor = frame._worker.ultimo_autor() or ""
    if autor:
        _gui.anunciar(f"Último mensaje leído de {autor}")
    else:
        _gui.anunciar("Todavía no se leyó ningún mensaje.")


def describir_escena(frame):
    from ytchat.ui import gui as _gui
    if frame._descripcion_escena_en_curso:
        return
    if not _gui.obs_activacion.obs_esta_en_ejecucion():
        _gui.anunciar("OBS no está abierto.")
        return
    frame._descripcion_escena_en_curso = True

    def _trabajo():
        gestor = None
        try:
            gestor = _gui.GestorPanelObs()
            gestor.conectar()
            texto = gestor.descripcion_escena()
        except Exception as error:
            texto = _gui.obs_cliente.mensaje_de_fallo_obs(error)
        finally:
            if gestor is not None:
                try:
                    gestor.cerrar()
                except Exception:
                    pass
            _gui.wx.CallAfter(frame._anunciar_descripcion_escena, texto)

    _gui.diagnostico.crear_hilo(_trabajo, "DescribirEscena").start()
