"""Supervisión de la transmisión en directo.

Los cuerpos de estas funciones son los antiguos métodos de `YTChatFrame`
movidos sin cambios: `_supervisar_transmision`, `_al_terminar_supervisor`,
`_actualizar_boton_directo`, `_guardar_datos_directo_youtube`,
`_guardar_destino_transmision`, `_guardar_usuario_tiktok` y
`_cambiar_overlay`. En la clase quedan delegados de una o dos líneas con
el mismo nombre y la misma firma, porque los usan eventos, otros módulos
y pruebas.

Los nombres que las pruebas reemplazan en el módulo `gui` (`anunciar`,
`guardar_opcion`, `RUTA_CONFIG`, `_snd`, `overlay_servidor`,
`diagnostico`, `credenciales`, `youtube_api`, `wx`) se acceden siempre
por el módulo en el momento de la llamada, nunca con un `from` directo.
"""

from __future__ import annotations

from bellbird.core.idioma import _


def cambiar_overlay(frame, encender):
    from bellbird.ui import gui as _gui
    puerto = frame._config.get("overlay_puerto", 8730)
    if encender:
        try:
            _gui.overlay_servidor.encender(puerto)
        except _gui.overlay_servidor.OverlayPuertoOcupadoError:
            _gui.anunciar(_("No se pudo activar el panel, el puerto {puerto} está ocupado").format(puerto=puerto))
            # El puerto ocupado solo afecta esta sesión, no la preferencia guardada.
            frame._config["overlay_activo"] = False
            return False
        frame._config["overlay_activo"] = True
        _gui.guardar_opcion(_gui.RUTA_CONFIG, "overlay", "activo", "true")
        _gui.anunciar(_("Panel de chat activo en el puerto {puerto}").format(puerto=puerto))
        from bellbird.obs import obs_panel_recarga
        _gui.diagnostico.crear_hilo(
            obs_panel_recarga.recargar_fuente_panel,
            "RecargarPanelObs").start()
        return True
    _gui.overlay_servidor.apagar()
    frame._config["overlay_activo"] = False
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "overlay", "activo", "false")
    _gui.anunciar(_("Panel de chat apagado"))
    return False


def guardar_usuario_tiktok(frame, usuario):
    from bellbird.ui import gui as _gui
    from bellbird.capture import tiktok_vivo
    usuario = tiktok_vivo.usuario_tiktok(usuario)
    frame._config["tiktok_usuario"] = usuario
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "tiktok", "usuario", usuario)
    return usuario


def guardar_destino_transmision(frame, destino):
    from bellbird.ui import gui as _gui
    from bellbird.obs.obs_destinos import DESTINOS
    destino = destino if destino in DESTINOS else ""
    frame._config["transmision_destino"] = destino
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "transmision", "destino", destino)
    return destino


def alternar_aviso_sobrecarga(frame) -> None:
    """Invierte la preferencia, sincroniza el menú y la guarda.

    El supervisor la consulta en cada vuelta, así que el cambio vale en pleno
    directo desde la vuelta siguiente. Sin sonido, como los otros
    interruptores del menú.
    """
    from bellbird.ui import gui as _gui
    nuevo = not bool(frame._config.get("avisar_sobrecarga", True))
    frame._config["avisar_sobrecarga"] = nuevo
    item = getattr(frame, "mi_avisos_sobrecarga", None)
    if item is not None:
        item.Check(nuevo)
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "transmision", "avisar_sobrecarga",
                        "true" if nuevo else "false")
    _gui.anunciar(_("Avisos de sobrecarga activados") if nuevo
                  else _("Avisos de sobrecarga desactivados"))


def alternar_grabar_al_transmitir(frame) -> None:
    """Invierte la preferencia, sincroniza el menú y la guarda.

    La casilla se consulta cuando la transmisión arranca bien, no al
    detenerse: un cambio vale desde la próxima transmisión que arranque.
    Sin sonido, como los otros interruptores del menú.
    """
    from bellbird.ui import gui as _gui
    nuevo = not bool(frame._config.get("grabar_al_transmitir", False))
    frame._config["grabar_al_transmitir"] = nuevo
    item = getattr(frame, "mi_grabar_al_transmitir", None)
    if item is not None:
        item.Check(nuevo)
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "transmision",
                        "grabar_al_transmitir", "true" if nuevo else "false")
    _gui.anunciar(_("Grabación al transmitir activada") if nuevo
                  else _("Grabación al transmitir desactivada"))


def guardar_datos_directo_youtube(frame, titulo, descripcion, privacidad,
                                  latencia=None, ninos=False, dvr=True,
                                  categoria="", etiquetas=None,
                                  miniatura="", lista="",
                                  lista_titulo=""):
    from bellbird.ui import gui as _gui
    from bellbird.core.config import codificar_texto_ini
    from bellbird.youtube.emision import (
        CATEGORIAS, LATENCIAS, LATENCIA_INICIAL, PRIVACIDADES,
        PRIVACIDAD_INICIAL)
    titulo = (titulo or "").strip()[:100]
    descripcion = descripcion or ""
    if privacidad not in PRIVACIDADES:
        privacidad = PRIVACIDAD_INICIAL
    if latencia not in LATENCIAS:
        latencia = LATENCIA_INICIAL
    if categoria not in {identificador for identificador, _t in CATEGORIAS}:
        categoria = ""
    etiquetas = list(etiquetas or [])
    miniatura = (miniatura or "").strip()
    lista = (lista or "").strip()
    lista_titulo = (lista_titulo or "").strip() if lista else ""
    nimios_texto = "true" if ninos else "false"
    dvr_texto = "true" if dvr else "false"
    etiquetas_texto = ", ".join(etiquetas)
    frame._config["transmision_youtube_titulo"] = titulo
    frame._config["transmision_youtube_descripcion"] = descripcion
    frame._config["transmision_youtube_privacidad"] = privacidad
    frame._config["transmision_youtube_latencia"] = latencia
    frame._config["transmision_youtube_ninos"] = ninos
    frame._config["transmision_youtube_dvr"] = dvr
    frame._config["transmision_youtube_categoria"] = categoria
    frame._config["transmision_youtube_etiquetas"] = etiquetas_texto
    frame._config["transmision_youtube_miniatura"] = miniatura
    frame._config["transmision_youtube_lista"] = lista
    frame._config["transmision_youtube_lista_titulo"] = lista_titulo
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "transmision", "youtube_titulo",
                        codificar_texto_ini(titulo))
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "transmision", "youtube_descripcion",
                        codificar_texto_ini(descripcion))
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "transmision", "youtube_privacidad",
                        privacidad)
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "transmision", "youtube_latencia",
                        latencia)
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "transmision", "youtube_ninos",
                        nimios_texto)
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "transmision", "youtube_dvr",
                        dvr_texto)
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "transmision", "youtube_categoria",
                        categoria)
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "transmision", "youtube_etiquetas",
                        codificar_texto_ini(etiquetas_texto))
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "transmision", "youtube_miniatura",
                        codificar_texto_ini(miniatura))
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "transmision", "youtube_lista",
                        lista)
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "transmision", "youtube_lista_titulo",
                        codificar_texto_ini(lista_titulo))
    return {"titulo": titulo, "descripcion": descripcion,
            "privacidad": privacidad, "latencia": latencia,
            "ninos": bool(ninos), "dvr": bool(dvr),
            "categoria": categoria, "etiquetas": etiquetas,
            "miniatura": miniatura, "lista": lista,
            "lista_titulo": lista_titulo}


def actualizar_boton_directo(frame) -> None:
    from bellbird.ui import gui as _gui
    boton = getattr(frame, "_boton_directo", None)
    if boton is None:
        return
    from bellbird.obs import transmision_directa
    propio = transmision_directa.es_directo_propio(
        frame.sesion.es_tiktok,
        frame.sesion.usuario_tiktok,
        frame._config.get("tiktok_usuario", ""),
        frame.sesion.conexion_propia)
    try:
        transmitiendo = bool(frame._supervisar_transmision("activo"))
    except Exception:
        transmitiendo = False
    transmitiendo = (transmitiendo
                     or bool(getattr(frame, "_obs_transmitiendo", False)))
    try:
        deteniendo = bool(frame._supervisar_transmision("deteniendo"))
    except Exception:
        deteniendo = False
    boton.actualizar(frame._conectado, frame._conectando, propio,
                     transmitiendo, deteniendo)


def al_terminar_supervisor(frame) -> None:
    from bellbird.ui import gui as _gui

    def _termino():
        if not frame._alive:
            return
        frame._obs_transmitiendo = False
        frame._actualizar_boton_directo()
    _gui.wx.CallAfter(_termino)


def _deteniendo(supervisor) -> bool:
    # `is True` porque un doble sin el estado (un Mock) devolvería un objeto
    # verdadero al preguntarle, y no está deteniendo nada.
    return getattr(supervisor, "deteniendo", False) is True


def _parametros_supervisor(frame, al_anunciar):
    """Arma los enganches del supervisor que leen la configuración del frame."""
    from bellbird.obs import obs_grabacion, obs_salida
    from bellbird.obs.obs_panel import GestorPanelObs

    def grabando():
        return bool(frame._config.get("grabar_al_transmitir", False))

    grabacion = obs_grabacion.GrabacionAlTransmitir(
        activa=grabando, al_anunciar=al_anunciar, crear_gestor=GestorPanelObs)
    return {
        "avisar_sobrecarga": lambda: bool(
            frame._config.get("avisar_sobrecarga", True)),
        "crear_gestor": grabacion.envolver_crear_gestor(GestorPanelObs),
        "esperar_salida": grabacion.envolver_esperar_salida(
            obs_salida.esperar_salida),
    }


def supervisar_transmision(frame, accion, destino="", usuario="",
                           revision=None):
    from bellbird.ui import gui as _gui
    if accion == "activo":
        supervisor = getattr(frame, "_supervisor", None)
        return bool(supervisor is not None
                    and (supervisor.activo or _deteniendo(supervisor)))
    if accion == "deteniendo":
        supervisor = getattr(frame, "_supervisor", None)
        return bool(supervisor is not None and _deteniendo(supervisor))
    if accion == "iniciar":
        supervisor = getattr(frame, "_supervisor", None)
        if supervisor is not None and _deteniendo(supervisor):
            _gui.anunciar(
                _("Deteniendo la transmisión. Esperando a que OBS confirme."))
            return
        if supervisor is not None and supervisor.activo:
            _gui.anunciar(_("Ya hay una transmisión en curso."))
            return
        ganchos = {}
        if destino == "YouTube":
            from datetime import datetime, timezone
            from bellbird.ui.gui_directo_youtube import pedir_datos_directo
            from bellbird.youtube import emision
            datos = _gui.credenciales.cargar()
            if not _gui.credenciales.hay_sesion(datos):
                _gui.anunciar(_("Para transmitir a YouTube hace falta iniciar "
                                "sesión con Google, en Preferencias, categoría API "
                                "y sesión."))
                return
            cliente = _gui.youtube_api.ClienteYouTube(
                _gui.credenciales.efectivas(datos))
            pedido = pedir_datos_directo(
                frame,
                frame._config.get("transmision_youtube_titulo", ""),
                frame._config.get("transmision_youtube_descripcion", ""),
                frame._config.get("transmision_youtube_privacidad",
                                  emision.PRIVACIDAD_INICIAL),
                revision,
                frame._config.get("transmision_youtube_latencia",
                                  emision.LATENCIA_INICIAL),
                frame._config.get("transmision_youtube_ninos", False),
                frame._config.get("transmision_youtube_dvr", True),
                frame._config.get("transmision_youtube_categoria", ""),
                frame._config.get("transmision_youtube_etiquetas", ""),
                frame._config.get("transmision_youtube_miniatura", ""),
                frame._config.get("transmision_youtube_lista", ""),
                frame._config.get("transmision_youtube_lista_titulo", ""),
                emision.cargador_listas(
                    cliente, lambda nuevo:
                    _gui.credenciales.guardar_campo("token", nuevo)))
            if pedido is None:
                _gui.anunciar(_("No se transmitió."))
                return
            guardados = frame._guardar_datos_directo_youtube(
                pedido["titulo"], pedido["descripcion"],
                pedido["privacidad"], pedido.get("latencia"),
                pedido.get("ninos", False), pedido.get("dvr", True),
                pedido.get("categoria", ""), pedido.get("etiquetas", []),
                pedido.get("miniatura", ""), pedido.get("lista", ""),
                pedido.get("lista_titulo", ""))
            try:
                cuerpo = emision.cuerpo_emision(
                    guardados["titulo"], guardados["descripcion"],
                    guardados["privacidad"],
                    datetime.now(timezone.utc).isoformat(),
                    latencia=guardados.get("latencia",
                                           emision.LATENCIA_INICIAL),
                    ninos=guardados.get("ninos", False),
                    dvr=guardados.get("dvr", True))
            except emision.EmisionError as exc:
                _gui.anunciar(str(exc))
                return
            extras = {"categoria": guardados.get("categoria", ""),
                      "etiquetas": guardados.get("etiquetas", []),
                      "miniatura": guardados.get("miniatura", ""),
                      "lista": guardados.get("lista", ""),
                      "titulo": guardados["titulo"],
                      "descripcion": guardados["descripcion"]}
            preparar, esperar, finalizar = emision.ganchos_youtube(
                cliente, cuerpo,
                lambda nuevo: _gui.credenciales.guardar_campo("token", nuevo),
                extras=extras, avisar=_gui.anunciar)
            ganchos = {"preparar_emision": preparar,
                       "esperar_emision": esperar,
                       "finalizar_emision": finalizar}
        from bellbird.obs.obs_supervisor import SupervisorTransmision
        from bellbird.core import paths

        def al_anunciar(frase, sonido):
            def _decir():
                if not frame._alive:
                    return
                if sonido:
                    _gui._snd.reproducir(sonido)
                _gui.anunciar(frase)
            _gui.wx.CallAfter(_decir)

        def al_conectar_chat(url):
            def _conectar():
                if not frame._alive:
                    return
                if destino == "YouTube":
                    from bellbird.youtube import emision as _emision
                    if guardados.get("ninos"):
                        frame.sesion.enlace_directo = url
                        _gui.anunciar(
                            _("El directo está marcado como hecho para "
                              "niños y YouTube no tiene chat."))
                        return
                    if not _emision.chat_legible(
                            guardados["privacidad"]):
                        frame.sesion.enlace_directo = url
                        _gui.anunciar(
                            _("El directo es privado y YouTube no deja "
                              "leer su chat. Para leerlo, transmite como "
                              "público o no listado."))
                        return
                if frame._conectado or frame._conectando:
                    _gui.anunciar(_("El chat ya estaba conectado y no se cambió."))
                    return
                try:
                    frame.txt_url.SetValue(url)
                except Exception as error:
                    _gui.logger.debug("no se pudo mostrar la dirección: %s", error)
                frame.sesion.conexion_propia = True
                frame._on_conectar(None)
            _gui.wx.CallAfter(_conectar)

        frame._supervisor = SupervisorTransmision(
            destino, usuario, al_anunciar=al_anunciar,
            al_conectar_chat=al_conectar_chat,
            al_terminar=frame._al_terminar_supervisor,
            ruta_fin_pendiente=paths.fin_pendiente(),
            **_parametros_supervisor(frame, al_anunciar),
            **ganchos)
        frame._supervisor.iniciar()
        frame._actualizar_boton_directo()
        return
    if accion == "detener":
        supervisor = getattr(frame, "_supervisor", None)
        if supervisor is None:
            return
        _gui.diagnostico.crear_hilo(
            supervisor.detener, "DetenerSupervisor").start()
        frame._actualizar_boton_directo()
        return
