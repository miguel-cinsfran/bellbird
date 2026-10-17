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


def cambiar_overlay(frame, encender):
    from ytchat.ui import gui as _gui
    puerto = frame._config.get("overlay_puerto", 8730)
    if encender:
        try:
            _gui.overlay_servidor.encender(puerto)
        except _gui.overlay_servidor.OverlayPuertoOcupadoError:
            _gui.anunciar(f"No se pudo activar el panel, el puerto {puerto} está ocupado")
            # El puerto ocupado solo afecta esta sesión, no la preferencia guardada.
            frame._config["overlay_activo"] = False
            return False
        frame._config["overlay_activo"] = True
        _gui.guardar_opcion(_gui.RUTA_CONFIG, "overlay", "activo", "true")
        _gui.anunciar(f"Panel de chat activo en el puerto {puerto}")
        return True
    _gui.overlay_servidor.apagar()
    frame._config["overlay_activo"] = False
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "overlay", "activo", "false")
    _gui.anunciar("Panel de chat apagado")
    return False


def guardar_usuario_tiktok(frame, usuario):
    from ytchat.ui import gui as _gui
    from ytchat.capture import tiktok_vivo
    usuario = tiktok_vivo.usuario_tiktok(usuario)
    frame._config["tiktok_usuario"] = usuario
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "tiktok", "usuario", usuario)
    return usuario


def guardar_destino_transmision(frame, destino):
    from ytchat.ui import gui as _gui
    from ytchat.obs.obs_destinos import DESTINOS
    destino = destino if destino in DESTINOS else ""
    frame._config["transmision_destino"] = destino
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "transmision", "destino", destino)
    return destino


def guardar_datos_directo_youtube(frame, titulo, descripcion, privacidad,
                                  latencia=None, ninos=False, dvr=True,
                                  categoria="", etiquetas=None,
                                  miniatura="", lista="",
                                  lista_titulo=""):
    from ytchat.ui import gui as _gui
    from ytchat.core.config import codificar_texto_ini
    from ytchat.youtube.emision import (
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
    from ytchat.ui import gui as _gui
    boton = getattr(frame, "_boton_directo", None)
    if boton is None:
        return
    from ytchat.obs import transmision_directa
    propio = transmision_directa.es_directo_propio(
        frame._es_tiktok,
        getattr(frame, "_usuario_tiktok_sesion", ""),
        frame._config.get("tiktok_usuario", ""),
        getattr(frame, "_conexion_propia", False))
    try:
        transmitiendo = bool(frame._supervisar_transmision("activo"))
    except Exception:
        transmitiendo = False
    transmitiendo = (transmitiendo
                     or bool(getattr(frame, "_obs_transmitiendo", False)))
    boton.actualizar(frame._conectado, frame._conectando, propio,
                     transmitiendo)


def al_terminar_supervisor(frame) -> None:
    from ytchat.ui import gui as _gui

    def _termino():
        if not frame._alive:
            return
        frame._obs_transmitiendo = False
        frame._actualizar_boton_directo()
    _gui.wx.CallAfter(_termino)


def supervisar_transmision(frame, accion, destino="", usuario="",
                           revision=None):
    from ytchat.ui import gui as _gui
    if accion == "activo":
        supervisor = getattr(frame, "_supervisor", None)
        return bool(supervisor is not None and supervisor.activo)
    if accion == "iniciar":
        supervisor = getattr(frame, "_supervisor", None)
        if supervisor is not None and supervisor.activo:
            _gui.anunciar("Ya hay una transmisión en curso.")
            return
        ganchos = {}
        if destino == "YouTube":
            from datetime import datetime, timezone
            from ytchat.ui.gui_directo_youtube import pedir_datos_directo
            from ytchat.youtube import emision
            datos = _gui.credenciales.cargar()
            if not _gui.credenciales.hay_sesion(datos):
                _gui.anunciar("Para transmitir a YouTube hace falta iniciar "
                              "sesión con Google, en Preferencias, pestaña API "
                              "y sesión.")
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
                _gui.anunciar("No se transmitió.")
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
        from ytchat.obs.obs_supervisor import SupervisorTransmision
        from ytchat.core import paths

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
                    from ytchat.youtube import emision as _emision
                    if guardados.get("ninos"):
                        _gui.anunciar(
                            "El directo está marcado como hecho para "
                            "niños y YouTube no tiene chat.")
                        return
                    if not _emision.chat_legible(
                            guardados["privacidad"]):
                        _gui.anunciar(
                            "El directo es privado y YouTube no deja "
                            "leer su chat. Para leerlo, transmite como "
                            "público o no listado.")
                        return
                if frame._conectado or frame._conectando:
                    _gui.anunciar("El chat ya estaba conectado, no lo cambié.")
                    return
                try:
                    frame.txt_url.SetValue(url)
                except Exception:
                    pass
                frame._conexion_propia = True
                frame._on_conectar(None)
            _gui.wx.CallAfter(_conectar)

        frame._supervisor = SupervisorTransmision(
            destino, usuario, al_anunciar=al_anunciar,
            al_conectar_chat=al_conectar_chat,
            al_terminar=frame._al_terminar_supervisor,
            ruta_fin_pendiente=paths.fin_pendiente(), **ganchos)
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
