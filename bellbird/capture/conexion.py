"""Conexión y desconexión de sesiones de captura."""

import logging

from bellbird.core import diagnostico
from bellbird.voice import sound_player as _snd
from bellbird.capture import tiktok_captura
from bellbird.obs import overlay_servidor
from bellbird.obs.overlay_datos import evento_de_mensaje

from bellbird.capture.sesiones import RegistroSesiones


logger = diagnostico.obtener_logger(__name__)


class _VistaNula:
    """Vista que no hace nada: sin vista la conexión no toca la interfaz."""

    activa = False
    conexion_propia = False

    def __getattr__(self, nombre):
        if nombre.startswith("_"):
            raise AttributeError(nombre)
        return lambda *args, **kwargs: False


class Conexiones:
    def __init__(self, cola, config, stats, parada_app, crear_hilo=None,
                 registro=None, vista=None):
        self._cola = cola
        self._config = config
        self._stats = stats
        self._parada_app = parada_app
        self._crear_hilo = crear_hilo or diagnostico.crear_hilo
        self._registro = registro or RegistroSesiones()
        self._vista = vista if vista is not None else _VistaNula()

    @property
    def registro(self):
        return self._registro

    def conectar(self, url_raw):
        import main
        # ¿Es una URL de TikTok? Va por su propia rama de captura (fase 1:
        # chat + reproductor, sin comentarios ni moderación).
        usuario_tt = tiktok_captura.usuario_de_url(url_raw)
        if usuario_tt:
            self._conectar_tiktok(usuario_tt)
            return
        vid = main.extraer_video_id(url_raw)
        # Validar el formato ANTES de tocar la red: si no es un ID de 11
        # caracteres, es basura. Se rechaza al instante (sin esperas ni freeze).
        if not main._ID_RE.match(vid):
            self._vista.url_invalida()
            return
        sesion = self._registro.abrir()
        ps, gen = sesion.parada, sesion.gen

        def _on_msg(autor, mensaje, hora, tipo=main.TIPO_TEXTO, monto="", canal_id="", rol=""):
            if not self._registro.vigente(gen):
                return  # mensaje de una sesión anterior: descartar
            overlay_servidor.difundir(
                evento_de_mensaje(autor, mensaje, "youtube", monto or None))
            self._vista.agregar_mensaje(
                autor, mensaje, hora, tipo, monto, canal_id,
                plataforma="youtube", rol=rol)

        def _on_estado(tipo_estado, texto):
            if not self._registro.vigente(gen):
                return  # estado de una sesión anterior: descartar
            if not self._vista.activa:
                return
            if tipo_estado == "conectado":
                # set_conectado ya anuncia un mensaje claro según el tipo; no
                # repetimos el texto genérico aquí.
                self._vista.set_conectado(True)
                return
            if tipo_estado in ("error_permanente", "error", "desconectado"):
                self._vista.set_conectado(False)
                self._vista.set_titulo("")
            # El resto de estados (conectando, reintentando, errores) se anuncian.
            self._vista.anunciar(texto)

        def _refrescar_directo():
            try:
                from bellbird.youtube import credenciales
                from bellbird.youtube import youtube_api
                if not (youtube_api.google_disponible() and
                        credenciales.hay_lectura()):
                    return
                if not self._registro.vigente(gen):
                    return
                cliente = youtube_api.ClienteYouTube(credenciales.efectivas())
                # La primera consulta va nada más conectar, para tener enseguida los
                # espectadores y la hora de inicio; las siguientes, cada minuto.
                while not ps.is_set():
                    if not self._registro.vigente(gen):
                        return
                    detalles = None
                    try:
                        detalles = cliente.detalles_directo(vid)
                    except Exception as exc:
                        logger.debug("actualizar detalles del directo: %s", exc)
                    if not self._registro.vigente(gen):
                        return
                    if detalles is not None:
                        self._vista.set_espectadores(detalles["espectadores"])
                        self._vista.set_inicio_directo(detalles["comienzo"])
                    ps.wait(60)
            except Exception as exc:
                logger.debug("actualizar detalles del directo: %s", exc)

        def _run():
            # Una sola descarga del watch para sacar título, tipo y metadatos.
            # sesion_activa: si se desconecta a mitad, no encadena más pasos
            # y el hilo Chat termina rápido (el cierre de la app lo espera).
            titulo, tipo, metadatos = main.obtener_info_video(
                vid, sesion_activa=lambda: self._registro.vigente(gen))
            # Si mientras buscábamos info se desconectó o se conectó a otro vídeo,
            # esta sesión ya no vale: no tocar la GUI (si no, pisaríamos la nueva).
            if not self._registro.vigente(gen):
                return
            self._vista.fallo_video(metadatos)
            if titulo:
                self._vista.set_titulo_si_existe(titulo)
            self._vista.set_tipo_video_si_existe(tipo, vid)
            self._vista.set_metadatos_si_existe(metadatos)
            # Registrar en el historial (canal desde los metadatos de yt-dlp).
            # directo=True si es un live: su id cambia cada vez y, terminado,
            # no reconecta (se marca en la lista del historial).
            self._vista.registrar_historial_si_existe(
                "youtube", vid, f"https://www.youtube.com/watch?v={vid}",
                titulo, (metadatos or {}).get("canal", ""),
                tipo == main.deteccion.LIVE)

            if main.deteccion.tiene_chat_en_vivo(tipo):
                # Directo (o tipo no determinado): capturamos el chat con pytchat.
                # Resolver el id del chat en vivo en paralelo (red opcional).
                self._crear_hilo(main._resolver_live_chat_id, "LiveChatId",
                                 args=(vid,)).start()
                if tipo == main.deteccion.LIVE:
                    self._crear_hilo(_refrescar_directo, "DetallesDirecto",
                                     daemon=True).start()
                main.captura_con_reconexion(
                    vid, self._cola, self._config, ps, self._stats,
                    on_message=_on_msg, on_estado=_on_estado,
                    sesion_activa=lambda: self._registro.vigente(gen))
                # Solo refrescar la UI a «desconectado» si seguimos siendo la
                # sesión activa: un hilo viejo que termina tarde no debe apagar
                # el directo nuevo.
                if (self._registro.vigente(gen)
                        and not self._parada_app.is_set()):
                    self._vista.set_conectado_si_existe(False)
                    self._vista.set_titulo_si_existe("")
            else:
                # Vídeo subido o directo programado: no hay chat en vivo. No se
                # arranca pytchat; quedan disponibles comentarios y reproductor.
                # El sonido también va tras el guard: una sesión ya descartada
                # no debe sonar como si conectara.
                if (self._registro.vigente(gen)
                        and self._vista.set_conectado_si_existe(True)):
                    _snd.reproducir("conectado")

        self._crear_hilo(_run, "Chat").start()

    def _conectar_tiktok(self, usuario):
        """Rama TikTok: mismo esquema de sesión (ps + gen) que YouTube, con la
        captura de tiktok_captura y el pipeline común procesar_entrante."""
        import main
        offline_pasajero = self._vista.conexion_propia is True
        sesion = self._registro.abrir()
        ps, gen = sesion.parada, sesion.gen

        def _on_msg(autor, mensaje, hora, tipo=main.TIPO_TEXTO, monto="", canal_id="", rol=""):
            if not self._registro.vigente(gen):
                return
            overlay_servidor.difundir(
                evento_de_mensaje(autor, mensaje, "tiktok", monto or None))
            self._vista.agregar_mensaje(
                autor, mensaje, hora, tipo, monto, canal_id,
                plataforma="tiktok", rol=rol)

        def _on_evento(autor, mensaje, tipo, monto, canal_id):
            if not self._registro.vigente(gen):
                return
            logger.debug("TIKTOK_EVENTO tipo=%s monto=%s", tipo, monto)
            main.procesar_entrante(
                autor, mensaje, tipo, monto, canal_id,
                self._cola, self._config, self._stats, on_message=_on_msg,
                sesion_activa=lambda: self._registro.vigente(gen),
                etiqueta_monto="Regalo")

        def _on_estado(tipo_estado, texto):
            if not self._registro.vigente(gen):
                return
            if not self._vista.activa:
                return
            # Los sonidos van aquí (no en tiktok_captura, que queda sin wx ni
            # audio): mismo mapa de eventos que la captura de YouTube.
            if tipo_estado in ("conectando", "reintentando"):
                _snd.reproducir("conectando")
                if tipo_estado == "reintentando":
                    self._stats.inc("reconexiones")
            elif tipo_estado == "conectado":
                _snd.reproducir("conectado")
                self._vista.set_conectado(True)
                return  # set_conectado ya anuncia el mensaje adecuado
            elif tipo_estado in ("error_permanente", "error"):
                _snd.reproducir("error")
                self._vista.set_conectado(False)
                self._vista.set_titulo("")
            elif tipo_estado in ("desconectado", "fin_directo"):
                # «fin_directo» cierra igual que «desconectado»: solo cambia
                # el sonido que reproduce set_conectado al desconectar.
                sonido = ("fin_directo" if tipo_estado == "fin_directo"
                          else "desconectado")
                self._vista.set_conectado(False, sonido)
                self._vista.set_titulo("")
            elif tipo_estado in ("directo_pausado", "directo_reanudado"):
                _snd.reproducir(tipo_estado)
            self._vista.anunciar(texto)

        def _on_info(meta):
            # Llega al conectar, con título, espectadores y la URL HLS del
            # directo (clave interna que consume el reproductor, no el panel).
            if not self._registro.vigente(gen):
                return
            if not self._vista.activa:
                return
            url_flujo = meta.pop("_url_flujo", "")
            titulo = (meta.get("titulo") or "").strip() or f"TikTok de @{usuario}"
            self._vista.set_titulo(titulo)
            self._vista.configurar_tiktok(usuario, url_flujo)
            self._vista.set_metadatos(meta)
            # Registrar en el historial (TikTok reconecta por @usuario/live).
            self._vista.registrar_historial(
                "tiktok", usuario, f"https://www.tiktok.com/@{usuario}/live",
                titulo, (meta.get("canal") or ""), True)

        def _on_espectadores(n, total=None):
            if not self._registro.vigente(gen):
                return
            self._vista.set_espectadores(n, total)

        def _run():
            tiktok_captura.capturar_con_reconexion(
                usuario, self._config, ps,
                on_evento=_on_evento, on_estado=_on_estado, on_info=_on_info,
                on_espectadores=_on_espectadores,
                offline_pasajero=offline_pasajero)
            # Igual que en YouTube: solo apagar la UI si seguimos siendo la
            # sesión activa (un hilo viejo no debe pisar el directo nuevo).
            if (self._registro.vigente(gen)
                    and not self._parada_app.is_set()):
                self._vista.set_conectado_si_existe(False)
                self._vista.set_titulo_si_existe("")

        self._crear_hilo(_run, "TikTok").start()

    def desconectar(self):
        self._registro.cerrar()
