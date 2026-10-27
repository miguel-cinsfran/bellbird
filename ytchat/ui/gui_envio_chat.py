"""Enviar al chat del directo por API oficial y mensajes programados.

Los cuerpos de estas funciones son los antiguos métodos de `YTChatFrame`
movidos sin cambios: `_on_enviar_live`, `_enviar_live_redactado`,
`_accion_api`, `_api_ok`, `_api_err`, `_actualizar_estado_online`,
`_actualizar_motivo_redaccion`, `_iniciar_programados_si_corresponde`,
`_enviar_programado`, `_programado_enviado`, `_programado_fallo`,
`_procesar_programado` y `_moderar`. En la clase quedan delegados de una
o dos líneas con el mismo nombre y la misma firma, porque los usan el
menú Chat, el compositor, el temporizador y las pruebas.

`_sesion_api_disponible` queda en la clase: es una sola línea que solo
pregunta si hay sesión.

Los nombres que las pruebas reemplazan en el módulo `gui` (`anunciar`,
`_snd`, `wx`, `diagnostico`, `logger`, `youtube_api`, `credenciales`,
`redaccion`, `deteccion`, `programados`, `time`, `random`) se acceden
siempre por el módulo en el momento de la llamada, nunca con un `from`
directo.
"""

from __future__ import annotations


def on_enviar_live(frame, event):
    from ytchat.ui import gui as _gui
    # Alt+Enter sin poder escribir (sin conexión, TikTok, sin sesión…): decir
    # por qué en vez de callar; el motivo lo lleva el propio compositor.
    motivo = frame._panel_redactar.motivo()
    if motivo:
        _gui.anunciar(motivo)
        return
    frame._panel_redactar.enfocar()


def enviar_live_redactado(frame, texto):
    lcid = frame.sesion.live_chat_id
    frame._accion_api(lambda cli: cli.enviar_mensaje_live(lcid, texto),
                      "Mensaje enviado al chat")


def accion_api(frame, accion, mensaje_ok: str, sonido: str = "enviado") -> None:
    from ytchat.ui import gui as _gui
    _gui.anunciar("Enviando")

    def _run():
        try:
            cli = _gui.youtube_api.ClienteYouTube(_gui.credenciales.efectivas())
            accion(cli)
            if cli.token_actualizado():
                _gui.credenciales.guardar_campo("token", cli.token_actualizado())
            _gui.wx.CallAfter(frame._api_ok, mensaje_ok, sonido)
        except Exception as exc:
            _gui.logger.warning("acción API: %s", exc)
            if _gui.youtube_api.sesion_caducada(exc):
                _gui.credenciales.cerrar_sesion()
            _gui.wx.CallAfter(frame._api_err, exc)

    _gui.diagnostico.crear_hilo(_run, "AccionAPI").start()


def api_ok(frame, mensaje, sonido: str = "enviado"):
    from ytchat.ui import gui as _gui
    if not frame:   # la ventana pudo cerrarse mientras respondía la API
        return
    _gui._snd.reproducir(sonido)
    _gui.anunciar(mensaje)


def api_err(frame, exc):
    from ytchat.ui import gui as _gui
    if not frame:
        return
    if _gui.youtube_api.sesion_caducada(exc):
        _gui._snd.reproducir("error")
        _gui.anunciar(_gui.youtube_api.mensaje_error_api(exc))
        frame._actualizar_estado_online()
        try:
            from ytchat.ui.gui_preferencias import ofrecer_iniciar_sesion
            if ofrecer_iniciar_sesion(frame, frame._config):
                frame._aplicar_preferencias_en_caliente()
        except Exception as exc_:
            _gui.logger.warning("No se pudo ofrecer iniciar sesión: %s", exc_)
        return
    _gui._snd.reproducir("error")
    msg = _gui.youtube_api.mensaje_error_api(exc)
    _gui.anunciar(msg)
    _gui.wx.MessageBox(msg, "Error de la API", _gui.wx.OK | _gui.wx.ICON_ERROR, frame)


def actualizar_estado_online(frame):
    frame._actualizar_motivo_redaccion()
    try:    frame._com_panel.actualizar_estado()
    except Exception: pass


def actualizar_motivo_redaccion(frame):
    from ytchat.ui import gui as _gui
    try:
        motivo = _gui.redaccion.motivo_chat(
            frame._conectado, frame.sesion.es_tiktok, frame.sesion.tipo_video == _gui.deteccion.LIVE,
            _gui.youtube_api.google_disponible(), frame._sesion_api_disponible(),
            bool(frame.sesion.live_chat_id), frame.sesion.causa_sin_chat)
        frame._panel_redactar.establecer_motivo(motivo)
    except Exception:
        pass


def iniciar_programados_si_corresponde(frame, ahora: float) -> None:
    from ytchat.ui import gui as _gui
    if frame.programador.reloj_iniciado:
        return
    if not frame._config.get("programados_activo", False):
        return
    frame.programador.iniciar_reloj_si_falta(ahora, _gui.random.randint)


def enviar_programado(frame, mensaje: dict, ahora: float) -> None:
    from ytchat.ui import gui as _gui
    frame.programador.empezar_envio()
    lcid = frame.sesion.live_chat_id
    texto = mensaje.get("texto", "")

    def _run():
        try:
            cli = _gui.youtube_api.ClienteYouTube(_gui.credenciales.efectivas())
            cli.enviar_mensaje_live(lcid, texto)
            if cli.token_actualizado():
                _gui.credenciales.guardar_campo("token", cli.token_actualizado())
            _gui.wx.CallAfter(frame._programado_enviado, mensaje)
        except Exception as exc:
            _gui.logger.warning("mensaje automático: error del servicio: %s", type(exc).__name__)
            if _gui.youtube_api.sesion_caducada(exc):
                _gui.credenciales.cerrar_sesion()
            _gui.wx.CallAfter(frame._programado_fallo, exc)

    _gui.diagnostico.crear_hilo(_run, "MensajeProgramado").start()


def programado_enviado(frame, mensaje: dict) -> None:
    from ytchat.ui import gui as _gui
    frame.programador.envio_hecho(mensaje, _gui.time.time(), _gui.random.randint)


def programado_fallo(frame, exc) -> None:
    from ytchat.ui import gui as _gui
    frame.programador.envio_fallido()
    if not frame._config.get("programados_activo", False):
        return
    frame._config["programados_activo"] = False
    if _gui.youtube_api.sesion_caducada(exc):
        _gui.anunciar("Los mensajes automáticos se detuvieron porque la sesión de YouTube caducó.")
    else:
        _gui.anunciar("Los mensajes automáticos se detuvieron por un error del servicio.")


def procesar_programado(frame) -> None:
    from ytchat.ui import gui as _gui
    propio = bool(frame.sesion.chat_propio or frame.sesion.conexion_propia)
    activo = bool(frame._config.get("programados_activo", False))
    if not _gui.programados.puede_enviar(
            activo, frame._conectado, frame.sesion.es_tiktok,
            frame.sesion.live_chat_id, propio, True) or not _gui.programados.puede_enviar(
            activo, frame._conectado, frame.sesion.es_tiktok,
            frame.sesion.live_chat_id, propio, frame._sesion_api_disponible()):
        # Sin las condiciones para mandar, el reloj no corre: al
        # reconectar arranca de nuevo en vez de salir todo de golpe.
        frame.programador.detener_reloj()
        return
    ahora = _gui.time.time()
    frame._iniciar_programados_si_corresponde(ahora)
    mensaje = frame.programador.siguiente(ahora)
    if mensaje is not None:
        frame._enviar_programado(mensaje, ahora)


def moderar(frame, autor: str, canal_id: str, segundos: int | None) -> None:
    from ytchat.ui import gui as _gui
    accion = "expulsar 5 minutos a" if segundos else "banear permanentemente a"
    if _gui.wx.MessageBox(f"¿Seguro que quieres {accion} {autor}?",
                          "Confirmar moderación",
                          _gui.wx.YES_NO | _gui.wx.ICON_QUESTION, frame) != _gui.wx.YES:
        return
    lcid = frame.sesion.live_chat_id
    ok = f"{autor} expulsado 5 minutos" if segundos else f"{autor} baneado del directo"
    frame._accion_api(
        lambda cli: cli.banear_usuario(lcid, canal_id, segundos), ok,
        sonido="moderacion")
