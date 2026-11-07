"""Supervisión de la transmisión en directo.

Los cuerpos de estas funciones son los antiguos métodos de `VentanaPrincipal`
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

from guyrapu.core.idioma import _
from guyrapu.restream import transmitir
from guyrapu.ui.aviso_importante import avisar


def cambiar_overlay(frame, encender):
    from guyrapu.ui import gui as _gui
    puerto = frame._config.get("overlay_puerto", 8730)
    if encender:
        try:
            _gui.overlay_servidor.encender(puerto)
        except _gui.overlay_servidor.OverlayPuertoOcupadoError:
            _gui.anunciar(_("No se pudo activar el chat en el vídeo: el puerto {puerto} "
                            "está en uso. Cámbialo en Preferencias, categoría "
                            "OBS.").format(puerto=puerto))
            # El puerto ocupado solo afecta esta sesión, no la preferencia guardada.
            frame._config["overlay_activo"] = False
            return False
        frame._config["overlay_activo"] = True
        _gui.guardar_opcion(_gui.RUTA_CONFIG, "overlay", "activo", "true")
        _gui.anunciar(_("Chat en el vídeo activado"))
        from guyrapu.obs import obs_panel_recarga
        _gui.diagnostico.crear_hilo(
            obs_panel_recarga.recargar_fuente_panel,
            "RecargarPanelObs").start()
        return True
    _gui.overlay_servidor.apagar()
    frame._config["overlay_activo"] = False
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "overlay", "activo", "false")
    _gui.anunciar(_("Chat en el vídeo desactivado"))
    return False


def guardar_usuario_tiktok(frame, usuario):
    from guyrapu.ui import gui as _gui
    from guyrapu.capture import tiktok_vivo
    usuario = tiktok_vivo.usuario_tiktok(usuario)
    frame._config["tiktok_usuario"] = usuario
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "tiktok", "usuario", usuario)
    return usuario


def guardar_destino_transmision(frame, destino):
    from guyrapu.ui import gui as _gui
    destino = destino if transmitir.es_opcion_valida(destino) else ""
    frame._config["transmision_destino"] = destino
    _gui.guardar_opcion(_gui.RUTA_CONFIG, "transmision", "destino", destino)
    return destino


def alternar_aviso_sobrecarga(frame) -> None:
    """Invierte la preferencia, sincroniza el menú y la guarda.

    El supervisor la consulta en cada vuelta, así que el cambio vale en pleno
    directo desde la vuelta siguiente. Sin sonido, como los otros
    interruptores del menú.
    """
    from guyrapu.ui import gui as _gui
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
    from guyrapu.ui import gui as _gui
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
    from guyrapu.ui import gui as _gui
    from guyrapu.core.config import codificar_texto_ini
    from guyrapu.youtube.emision import (
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
    from guyrapu.ui import gui as _gui
    boton = getattr(frame, "_boton_directo", None)
    if boton is None:
        return
    from guyrapu.obs import transmision_directa
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
    from guyrapu.ui import gui as _gui

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


def _decir_anuncio(frame, frase, sonido, importante):
    from guyrapu.ui import gui as _gui
    if not frame._alive:
        return
    if importante:
        return avisar(frase, sonido,
                      error=sonido in ("error", "transmision_problema"))
    _gui._snd.reproducir(sonido)
    _gui.anunciar(frase)


def _parametros_supervisor(frame, al_anunciar):
    """Arma los enganches del supervisor que leen la configuración del frame."""
    from guyrapu.obs import obs_grabacion, obs_salida
    from guyrapu.obs.obs_panel import GestorPanelObs

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


def _rechazar_si_hay_transmision(frame) -> bool:
    from guyrapu.ui import gui as _gui
    supervisor = getattr(frame, "_supervisor", None)
    if supervisor is not None and _deteniendo(supervisor):
        _gui.anunciar(
            _("Deteniendo la transmisión. Esperando a que OBS confirme."))
        return True
    if supervisor is not None and supervisor.activo:
        _gui.anunciar(_("Ya hay una transmisión en curso."))
        return True
    return False


def _iniciar_restream(frame, destino, revision):
    from guyrapu.restream import ganchos as restream_ganchos
    return restream_ganchos.supervisar_restream(
        frame, destino, revision=revision)


def supervisar_transmision(frame, accion, destino="", usuario="",
                           revision=None):
    from guyrapu.ui import gui as _gui
    if accion == "activo":
        supervisor = getattr(frame, "_supervisor", None)
        return bool(supervisor is not None
                    and (supervisor.activo or _deteniendo(supervisor)))
    if accion == "deteniendo":
        supervisor = getattr(frame, "_supervisor", None)
        return bool(supervisor is not None and _deteniendo(supervisor))
    if accion == "iniciar":
        if _rechazar_si_hay_transmision(frame):
            return
        if transmitir.es_restream(destino):
            return _iniciar_restream(frame, destino, revision)
        ganchos = {}
        if destino == "YouTube":
            from guyrapu.ui import inicio_youtube
            armado = inicio_youtube.pedir_y_armar(frame, revision)
            if armado is None:
                return
            guardados, ganchos = armado
        from guyrapu.obs.obs_supervisor import SupervisorTransmision
        from guyrapu.core import paths

        def al_anunciar(frase, sonido, importante=False):
            _gui.wx.CallAfter(lambda: _decir_anuncio(frame, frase, sonido, importante))

        def al_conectar_chat(url):
            def _conectar():
                if not frame._alive:
                    return
                if destino == "YouTube":
                    from guyrapu.ui import inicio_youtube
                    if inicio_youtube.sin_chat(frame, guardados, url):
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
