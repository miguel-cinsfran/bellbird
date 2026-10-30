"""Punto de entrada. Abre la interfaz gráfica directamente."""

from __future__ import annotations

import sys
import queue
import logging
import re
import threading
import warnings
import asyncio
import time
import urllib.request
import urllib.error
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# pytchat usa APIs de asyncio deprecadas.
warnings.filterwarnings("ignore", category=DeprecationWarning, module="asyncio")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pytchat")
warnings.filterwarnings("ignore", message=".*get_event_loop.*")

from bellbird.core.config import (
    APP_NAME, APP_VERSION,
    TIPO_TEXTO, TIPO_SUPERCHAT, TIPO_STICKER, TIPO_MIEMBRO, TIPO_ENTRADA,
    TIPO_SEGUIR, TIPO_COMPARTIR, TIPO_COFRE, TIPO_ME_GUSTA,
    configurar_logging, cargar_configuracion, cargar_sonidos,
)
from bellbird.core import avisos_tiktok
from bellbird.core import paths
from bellbird.core import migracion_datos
from bellbird.core.instancia import verificar_instancia_unica as _verificar_instancia_unica

from bellbird.voice.tts_worker import TTSWorker, sanitizar, construir_tts
from bellbird.voice.cola_tts import ColaTTS
from bellbird.voice import sound_player as _snd
from bellbird.capture import deteccion
from bellbird.capture.reconexion import FiltroNuevos, espera_reconexion
from bellbird.core import diagnostico
from bellbird.core import avisos_red
from bellbird.downloads import ytdlp_bin
from bellbird.capture import conexion
from bellbird.ui.vista_captura import VistaGui
from bellbird.capture import alias
from bellbird.core.sonidos_eventos import rol_de_autor, ROL_PROPIETARIO, ROL_MODERADOR
from bellbird.core.idioma import N_, _

logger = diagnostico.obtener_logger(__name__)

# Traducción pytchat → tipos internos.
_TIPO_MAP = {
    "textMessage": TIPO_TEXTO, "superChat": TIPO_SUPERCHAT,
    "superSticker": TIPO_STICKER, "newSponsor": TIPO_MIEMBRO,
}


# ── Extracción de URL / ID de YouTube ────────────────────────────────────────

_ID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')


def extraer_video_id(entrada: str) -> str:
    entrada = entrada.strip()
    if _ID_RE.match(entrada):
        return entrada
    try:
        parsed = urlparse(entrada if "://" in entrada else "https://" + entrada)
        host = parsed.netloc.lower()
        if "youtube.com" in host:
            qs = parse_qs(parsed.query)
            if "v" in qs and _ID_RE.match(qs["v"][0]):
                return qs["v"][0]
            m = re.search(r"/(?:live|shorts|embed|v|e)/([A-Za-z0-9_-]{11})(?:[/?#]|$)", parsed.path)
            if m:
                return m.group(1)
        elif "youtu.be" in host:
            m = re.match(r"^/([A-Za-z0-9_-]{11})(?:[/?#]|$)", parsed.path)
            if m:
                return m.group(1)
    except Exception as error:
        logger.debug("no se pudo extraer el id del vídeo de la dirección: %s", error)
    m = re.search(r"[/=]([A-Za-z0-9_-]{11})(?:[?&/#]|$)", entrada)
    if m and _ID_RE.match(m.group(1)):
        return m.group(1)
    return entrada


def _descargar_watch(video_id: str, timeout: float = 8.0, al_fallar=None) -> str:
    """Descarga (parcial) el HTML del watch. Cadena vacía si falla."""
    try:
        req = urllib.request.Request(f"https://www.youtube.com/watch?v={video_id}",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "es-ES,es;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            # Más bytes que antes: las banderas de directo aparecen algo después
            # del título dentro de videoDetails.
            return r.read(200_000).decode("utf-8", errors="ignore")
    except Exception as exc:
        logger.debug("_descargar_watch: %s", exc)
        if al_fallar:
            al_fallar(exc)
        return ""


def _parsear_titulo(html: str) -> str:
    if not html:
        return ""
    m = re.search(r'"videoDetails"[^}]{0,200}"title"\s*:\s*"([^"]+)"', html)
    if m:
        return m.group(1).replace("\\u0026", "&").replace("\\n", " ").replace("\\/", "/").strip()
    m = re.search(r"<title>([^<]+)</title>", html)
    if m:
        t = m.group(1).replace(" - YouTube", "").strip()
        if t and t.lower() != "youtube":
            return t
    return ""


def _clasificar_por_api(video_id: str) -> str:
    """Reserva: si hay API key, clasifica con la Data API. Si no, desconocido."""
    try:
        from bellbird.youtube import credenciales
        from bellbird.youtube import youtube_api
        if not (youtube_api.google_disponible() and credenciales.hay_lectura()):
            return deteccion.DESCONOCIDO
        cli = youtube_api.ClienteYouTube(credenciales.efectivas())
        resp = cli._lectura().videos().list(
            part="snippet", id=video_id).execute()
        items = resp.get("items", []) or []
        if not items:
            return deteccion.DESCONOCIDO
        lbc = items[0].get("snippet", {}).get("liveBroadcastContent")
        return deteccion.clasificar_desde_api(lbc)
    except Exception as exc:
        logger.debug("_clasificar_por_api: %s", exc)
        return deteccion.DESCONOCIDO


def _tipo_desde_ytdlp(info: dict) -> str:
    ls = (info.get("live_status") or "").strip()
    if ls == "is_live":
        return deteccion.LIVE
    if ls == "is_upcoming":
        return deteccion.UPCOMING
    if ls in ("was_live", "not_live", "post_live"):
        return deteccion.VOD
    if info.get("is_live"):
        return deteccion.LIVE
    return deteccion.DESCONOCIDO


def _metadatos_desde_ytdlp(info: dict) -> dict:
    """Saca del dict de yt-dlp los metadatos que muestra el panel de información.
    La extracción `process=False` ya los trae (canal, vistas, descripción…), así
    que no cuesta ninguna petición extra. Campos ausentes quedan en None/"" y el
    panel los omite."""
    return {
        "titulo":      (info.get("title") or "").strip(),
        "canal":       (info.get("uploader") or info.get("channel") or "").strip(),
        "vistas":      (
            info.get("concurrent_view_count", info.get("view_count"))
            if _tipo_desde_ytdlp(info) == deteccion.LIVE
            else info.get("view_count")
        ),
        "me_gusta":    info.get("like_count"),
        "comentarios": info.get("comment_count"),
        "fecha":       (info.get("upload_date") or "").strip(),   # YYYYMMDD
        "duracion":    info.get("duration"),                      # segundos
        "en_vivo":     bool(info.get("is_live")),
        "descripcion": (info.get("description") or "").strip(),
    }


def _info_video_con_modulo(video_id: str) -> dict:
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True,
            # Evita que una red lenta cuelgue indefinidamente la detección live/VOD.
            "socket_timeout": 20}
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(
            f"https://www.youtube.com/watch?v={video_id}",
            download=False, process=False)


def obtener_info_video(video_id: str, sesion_activa=None) -> tuple[str, str, dict]:
    """Devuelve (titulo, tipo, metadatos). tipo: live/upcoming/vod/desconocido.

    El módulo yt-dlp tarda 2,19 s y 1,69 s, frente a 5,28 s y 7,05 s del
    ejecutable medidos con el mismo vídeo. Ambos son robustos ante la página de
    consentimiento que YouTube sirve al scraping directo, y traen `title`,
    `live_status` y la metadata del panel de información (canal, vistas,
    descripción…). Si fallan los dos, se cae al scraping (que puede no funcionar
    y deja la metadata vacía, con solo el título si se pudo sacar).

    sesion_activa() (opcional) se consulta entre paso y paso: si el usuario
    desconectó mientras tanto, no tiene sentido encadenar el ejecutable y el
    scraping (hasta 20 s más) y el hilo Chat debe morir cuanto antes; si no,
    el cierre de la app destruye la ventana con el hilo aún en código nativo."""
    fallos = []
    cancelado = ("", deteccion.DESCONOCIDO, {})

    def _cancelada():
        return sesion_activa is not None and not sesion_activa()

    try:
        info = _info_video_con_modulo(video_id)
        if isinstance(info, dict):
            titulo = (info.get("title") or "").strip()
            tipo = _tipo_desde_ytdlp(info)
            if titulo or tipo != deteccion.DESCONOCIDO:
                return titulo, tipo, _metadatos_desde_ytdlp(info)
    except Exception as exc:
        logger.debug("obtener_info_video (yt-dlp módulo): %s", exc)
        fallos.append(exc)
    if _cancelada():
        return cancelado

    # El módulo evita arrancar y desempaquetar el ejecutable en cada conexión.
    try:
        info = ytdlp_bin.info_video(video_id)
        if isinstance(info, dict):
            titulo = (info.get("title") or "").strip()
            tipo = _tipo_desde_ytdlp(info)
            if titulo or tipo != deteccion.DESCONOCIDO:
                return titulo, tipo, _metadatos_desde_ytdlp(info)
    except Exception as exc:
        logger.debug("obtener_info_video (yt-dlp ejecutable): %s", exc)
        fallos.append(exc)
    if _cancelada():
        return cancelado

    html = _descargar_watch(video_id, al_fallar=fallos.append)
    titulo = _parsear_titulo(html)
    tipo = deteccion.clasificar_desde_html(html)
    if tipo == deteccion.DESCONOCIDO:
        tipo = _clasificar_por_api(video_id)
    metadatos = {"titulo": titulo}
    if not html and fallos:
        metadatos["fallo"] = avisos_red.mensaje_de_fallo(
            " ".join(str(fallo) for fallo in fallos))
    return titulo, tipo, metadatos


def _anunciar_fallo_video(metadatos: dict, call_after) -> None:
    fallo = (metadatos or {}).get("fallo")
    if fallo:
        from bellbird.ui.accesibilidad import anunciar
        call_after(anunciar, fallo)


def _resolver_live_chat_id(video_id: str) -> None:
    """Si hay API key, resuelve el id del chat en vivo y se lo pasa al GUI.

    Es totalmente opcional: cualquier fallo se ignora y la captura del chat
    (que va por pytchat, sin API) sigue funcionando igual.
    """
    lcid = ""
    propio = False
    hay_credenciales = consulta_fallo = hay_video = hay_directo = False
    try:
        from bellbird.youtube import credenciales
        from bellbird.capture import redaccion
        from bellbird.youtube import youtube_api
        hay_credenciales = (youtube_api.google_disponible()
                            and credenciales.hay_lectura())
        if hay_credenciales:
            try:
                cliente = youtube_api.ClienteYouTube(
                    credenciales.efectivas())
                datos = cliente.datos_chat_directo(video_id)
                hay_video = datos["hay_video"]
                hay_directo = datos["hay_directo"]
                lcid = datos["live_chat_id"]
                if credenciales.hay_sesion():
                    try:
                        canal_id = datos.get("canal_id", "") or ""
                        propio = bool(canal_id) and canal_id == cliente.id_canal_propio()
                    except Exception as exc:
                        logger.debug("resolver_live_chat_id (canal propio): %s", exc)
                        propio = False
            except Exception as exc:
                logger.debug("resolver_live_chat_id: %s", exc)
                consulta_fallo = True
        causa = redaccion.causa_sin_chat(
            hay_credenciales, consulta_fallo, hay_video, hay_directo, lcid)
        import wx
        from bellbird.ui import gui as _gm
        if _gm._gui_frame and _gm._gui_frame._alive:
            wx.CallAfter(_gm._gui_frame.set_live_chat_id, lcid, causa,
                         video_id, propio)
    except Exception as exc:
        logger.debug("resolver_live_chat_id: %s", exc)


# ── Estadísticas ─────────────────────────────────────────────────────────────

class Stats:
    def __init__(self):
        self._lock = threading.Lock()
        self.recibidos = self.leidos = self.filtrados = 0
        self.descartados = self.reconexiones = self.filtrados_nuevo = 0
        self.superchats = 0
        self.inicio = datetime.now()

    def inc(self, campo, n=1):
        with self._lock:
            setattr(self, campo, getattr(self, campo) + n)

    def reset(self):
        """Vuelve los contadores a cero: al desconectar empezamos de limpio,
        como si la app se acabara de abrir."""
        with self._lock:
            self.recibidos = self.leidos = self.filtrados = 0
            self.descartados = self.reconexiones = self.filtrados_nuevo = 0
            self.superchats = 0
            self.inicio = datetime.now()


# ── Cola y filtros ───────────────────────────────────────────────────────────

def encolar(cola, item, config, stats):
    if config["estrategia"] == "todas":
        cola.put(item); return
    max_q = config["tamanio_maximo"]
    n = 0
    while cola.qsize() >= max_q:
        try:    cola.get_nowait(); n += 1
        except queue.Empty: break
    if n: stats.inc("descartados", n)
    try:    cola.put_nowait(item)
    except queue.Full: stats.inc("descartados")


def permitido(autor: str, mensaje: str, config: dict) -> bool:
    al = autor.lower().strip()
    if any(u in al for u in config["usuarios_silenciados"]): return False
    if al in config.get("silenciados_ocultar", set()): return False
    ml = mensaje.lower()
    if any(p in ml for p in config["palabras_silenciadas"]): return False
    return True


def debe_leer_tts(autor: str, config: dict) -> bool:
    if config.get("silenciar_lectura", False):
        return False
    return autor.lower().strip() not in config.get("silenciados_runtime", set())


def procesar_entrante(autor, mensaje, tipo, monto, canal_id, cola, config, stats,
                      on_message=None, sesion_activa=None,
                      etiqueta_monto=N_("Super Chat"), rol=""):
    """Pipeline común de cada mensaje entrante (YouTube y TikTok): contadores,
    filtros, texto TTS, aviso a la GUI y encolado de lectura.

    etiqueta_monto: cómo llamar al mensaje con importe al leerlo («Super Chat»
    en YouTube, «Regalo» en TikTok). sesion_activa() evita que un hilo rezagado
    cuele lecturas de una sesión anterior; el descarte de GUI lo hace on_message.
    """
    stats.inc("recibidos")
    if tipo in (TIPO_SUPERCHAT, TIPO_STICKER): stats.inc("superchats")

    modo = avisos_tiktok.modo_de(config, tipo)
    if modo == "ocultar":
        stats.inc("filtrados")
        return

    if not permitido(autor, mensaje, config):
        stats.inc("filtrados"); return

    autor_visible = alias.visible(autor)
    ml = sanitizar(mensaje, config["limpiar_emojis"],
                   config["eliminar_urls"], config["max_longitud_mensaje"])
    if tipo == TIPO_TEXTO and not ml.strip():
        stats.inc("filtrados"); return

    umbral = config.get("umbral_solo_nombre", 0)
    if tipo == TIPO_SUPERCHAT and monto:
        # Traductores: {etiqueta} es «Super Chat» o «Regalo».
        tts_text = (_("{etiqueta} de {autor}: {monto}. {mensaje}") if ml
                    else _("{etiqueta} de {autor}: {monto}")).format(
            etiqueta=_(etiqueta_monto), autor=autor_visible, monto=monto, mensaje=ml)
    elif tipo == TIPO_MIEMBRO:
        tts_text = _("Nuevo miembro: {autor}").format(autor=autor_visible)
    elif tipo == TIPO_ENTRADA:
        tts_text = _("{autor} entró").format(autor=autor_visible)
    elif tipo == TIPO_SEGUIR:
        tts_text = _("{autor} sigue el canal").format(autor=autor_visible)
    elif tipo == TIPO_COMPARTIR:
        tts_text = _("{autor} compartió el directo").format(autor=autor_visible)
    elif tipo == TIPO_COFRE:
        tts_text = _("{autor} envió un cofre").format(autor=autor_visible)
    elif tipo == TIPO_ME_GUSTA:
        # Traductores: {n} es cuántos «me gusta» dieron.
        tts_text = (_("{autor} dio {n} me gusta").format(autor=autor_visible, n=monto)
                    if monto else _("{autor} dio me gusta").format(autor=autor_visible))
    elif umbral > 0 and cola.qsize() >= umbral:
        tts_text = sanitizar(autor_visible, config["limpiar_emojis"], False, 50) or _("Usuario")
    else:
        tts_text = construir_tts(autor_visible, ml or mensaje, config)

    hora = datetime.now().strftime('%H:%M:%S')
    if on_message: on_message(autor, mensaje, hora, tipo, monto, canal_id, rol=rol)

    if modo == "mostrar":
        return  # en la lista con su sonido, sin leer

    if debe_leer_tts(autor, config) and (sesion_activa is None or sesion_activa()):
        item = {"texto_tts": tts_text, "autor": autor_visible}
        # Importante: con ElevenLabs y «solo importantes» activado, esto decide
        # qué sale por la nube. Son los eventos con aporte y los roles de peso.
        if (tipo in (TIPO_SUPERCHAT, TIPO_STICKER, TIPO_MIEMBRO, TIPO_COFRE)
                or rol in (ROL_PROPIETARIO, ROL_MODERADOR)):
            item["importante"] = True
        # Multi-voz: los eventos (Super Chats, regalos, miembros, entradas) se
        # leen con otra voz si está activado; los mensajes normales, con la base.
        if config.get("multivoz") and tipo in (TIPO_SUPERCHAT, TIPO_STICKER, TIPO_MIEMBRO, TIPO_ENTRADA,
                                               TIPO_SEGUIR, TIPO_COMPARTIR, TIPO_COFRE):
            voz_ev = config.get("voz_eventos")
            if voz_ev:
                item["voz"] = voz_ev
        encolar(cola, item, config, stats)
        stats.inc("leidos")


# ── Captura de chat ──────────────────────────────────────────────────────────

_ERRORES_PERMANENTES = (
    "invalid video id", "private", "members only",
    "finished", "unavailable", "does not exist",
)


def _es_error_permanente(exc):
    return any(p in str(exc).lower() for p in _ERRORES_PERMANENTES)


def _directo_terminado(video_id) -> bool:
    """¿El directo ya terminó? True solo cuando yt-dlp lo ve como vídeo grabado.

    Un directo terminado deja a pytchat abriendo una conexión que a los
    segundos cae con «Chat data stream is empty». Reintentar eso no tiene fin,
    así que antes de contar el intento se consulta esto. Con «live»,
    «upcoming», «desconocido» o un fallo de la consulta devuelve False y la
    reconexión sigue como siempre."""
    try:
        _titulo, tipo, _metadatos = obtener_info_video(video_id)
    except Exception:
        return False
    return tipo == deteccion.VOD


def captura_con_reconexion(video_id, cola, config, parada, stats, on_message=None,
                           on_estado=None, sesion_activa=None):
    """on_estado(tipo, texto) informa al GUI de cambios de estado.
    sesion_activa() (opcional) dice si esta sesión sigue siendo la vigente: un
    hilo viejo que despierta tarde no debe encolar TTS de la sesión anterior."""
    intentos = 0
    conecto = [False]
    llego_conectado = [False]
    filtro = FiltroNuevos()

    def _estado(tipo, texto):
        # «leido» es interno: marca que la conexión leyó al menos una vuelta de
        # chat.get() sin error, y no se reenvía a la interfaz. Solo entonces la
        # conexión cuenta como buena y se reinician los intentos: con el
        # «conectado» de pytchat, un directo terminado reiniciaba el contador en
        # cada vuelta y el límite de intentos nunca se cumplía.
        if tipo == "leido":
            conecto[0] = True
            return
        if tipo == "conectado":
            if llego_conectado[0]:
                tipo, texto = "reconectado", _("Chat reconectado.")
            llego_conectado[0] = True
        elif tipo == "conectando" and llego_conectado[0]:
            return
        if on_estado:
            on_estado(tipo, texto)

    while not parada.is_set():
        conecto[0] = False
        err = _captura(video_id, cola, config, parada, stats, on_message, _estado,
                       sesion_activa, filtro)
        if conecto[0]: intentos = 0
        if parada.is_set(): break
        if not config["reconectar"]:
            if on_estado: on_estado("error",
                _("La conexión se cerró y la reconexión está desactivada."))
            parada.set(); break
        if err is not None and _es_error_permanente(err):
            msg = _mensaje_error_amigable(err)
            if on_estado: on_estado("error_permanente", msg)
            _snd.reproducir("error")
            parada.set(); break
        if _directo_terminado(video_id):
            if on_estado: on_estado("error_permanente", _("El directo terminó. Chat desconectado."))
            _snd.reproducir("fin_directo")
            parada.set(); break
        intentos += 1
        mi = config["max_intentos"]
        if mi > 0 and intentos >= mi:
            # Traductores: {n} puede ser 1.
            if on_estado: on_estado("error",
                _("Se agotaron los {n} intentos de reconexión.").format(n=mi))
            _snd.reproducir("error")
            parada.set(); break
        espera = espera_reconexion(intentos, config["espera_entre_intentos"])
        unidad = _("segundo") if espera == 1 else _("segundos")
        motivo = str(err) if err is not None else "la conexión se cerró sin error"
        logger.warning("Reconexión del chat video=%s, intento %s: %s", video_id, intentos, motivo)
        # Traductores: {segundos} puede ser 1; {unidad}, segundo o segundos; {total}, el máximo.
        if on_estado: on_estado("reintentando", (_("Se perdió la conexión con el chat. "
            "Reintentando en {segundos} {unidad} (intento {intento} de {total}).") if mi else _("Se"
            " perdió la conexión con el chat. Reintentando en {segundos} {unidad} (intento"
            " {intento}).")).format(segundos=espera, unidad=unidad, intento=intentos, total=mi))
        stats.inc("reconexiones")
        _snd.reproducir("conectando")
        parada.wait(timeout=espera)


def _cliente_pytchat():
    """Cliente httpx propio para pytchat: uno NUEVO en cada intento de
    conexión, en vez de dejar que pytchat use el suyo.

    `PytchatCore.__init__` (pytchat/core/pytchat.py) declara
    `client=httpx.Client(http2=True)` como valor por defecto del parámetro:
    en Python eso se evalúa UNA sola vez, al importar el módulo, así que si no
    le pasamos cliente, TODAS las conexiones del proceso —incluidas las
    reconexiones automáticas de captura_con_reconexion— comparten el mismo
    httpx.Client de toda la vida de la app. Además, con HTTP/2 y conexiones
    keep-alive hay un bug conocido de httpx/h2 (se ve en consola como
    `httpx.LocalProtocolError: Invalid input ConnectionInputs.RECV_PING in
    state ConnectionState.CLOSED`): si YouTube cierra una conexión inactiva y
    el cliente la reutiliza igual, revienta. Combinados, un intento fallido
    por ese bug deja el cliente compartido roto para SIEMPRE, y cada
    reconexión automática vuelve a pegarse con la misma conexión muerta —así
    es como el error de la consola exigía reconectar a mano.
    `client` es un parámetro documentado de PytchatCore (no hace falta tocar
    su código): pasando un httpx.Client nuevo por conexión, y en HTTP/1.1 (sin
    multiplexado, así que sin ese bug de h2), ninguna conexión rota sobrevive
    de un intento al siguiente."""
    import httpx
    return httpx.Client(http2=False)


def _captura(video_id, cola, config, parada, stats, on_message=None, on_estado=None,
             sesion_activa=None, filtro=None):
    # pytchat necesita un loop de asyncio en el hilo. Uno por intento y se
    # cierra al salir: si no, cada reconexión dejaba un loop (y su selector)
    # abiertos para siempre.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return _captura_en_loop(video_id, cola, config, parada, stats, on_message,
                                on_estado, sesion_activa, filtro)
    finally:
        try:    loop.close()
        except Exception as error: logger.debug("no se pudo cerrar el bucle: %s", error)
        asyncio.set_event_loop(None)


def _captura_en_loop(video_id, cola, config, parada, stats, on_message, on_estado,
                     sesion_activa, filtro=None):
    try:
        import pytchat
    except ImportError:
        if on_estado: on_estado("error_permanente",
            _("No se encontró la biblioteca pytchat. Ejecuta instalar.bat."))
        _snd.reproducir("error")
        parada.set(); return None

    if on_estado: on_estado("conectando", _("Conectando al directo…"))
    _snd.reproducir("conectando")

    cliente = _cliente_pytchat()
    try:
        chat = pytchat.create(video_id=video_id, interruptable=False, client=cliente)
    except Exception as exc:
        try:    cliente.close()
        except Exception as error: logger.debug("no se pudo cerrar el cliente del chat: %s", error)
        msg = _mensaje_error_amigable(exc)
        if on_estado: on_estado("error_conexion", msg)
        _snd.reproducir("error")
        return exc

    if on_estado: on_estado("conectado", _("Conectado. Esperando mensajes…"))
    _snd.reproducir("conectado")
    logger.info("Conectado al directo video=%s.", video_id)

    if filtro is None: filtro = FiltroNuevos()
    filtro.arrancar()
    leido = False
    err_con, MAX_ERR = 0, 5
    ultimo_error = None

    try:
        while chat.is_alive() and not parada.is_set():
            try:
                for c in chat.get().sync_items():
                    if parada.is_set(): break
                    if not filtro.es_nuevo(c):
                        stats.inc("filtrados_nuevo"); continue

                    autor_obj = getattr(c, "author", None)
                    autor    = _str(autor_obj and autor_obj.name, _("Usuario"))
                    canal_id = _str(autor_obj and getattr(autor_obj, "channelId", None), "")
                    rol      = rol_de_autor(autor_obj)
                    mensaje  = _str(getattr(c, "message", None), "")
                    tipo_raw = _str(getattr(c, "type", None), "textMessage")
                    tipo     = _TIPO_MAP.get(tipo_raw, None)
                    if tipo is None: continue

                    monto = ""
                    if tipo in (TIPO_SUPERCHAT, TIPO_STICKER):
                        monto = _str(getattr(c, "amountString", None), "")
                    logger.debug("YOUTUBE_EVENTO tipo=%s monto=%s", tipo, monto)
                    procesar_entrante(autor, mensaje, tipo, monto, canal_id, cola, config, stats,
                                      on_message=on_message,
                                      sesion_activa=sesion_activa, rol=rol)

                err_con = 0
                if not leido:
                    # Una vuelta de get() sin excepción: la conexión está viva
                    # de verdad. Se avisa una sola vez y como tipo interno, que
                    # captura_con_reconexion consume sin mostrarlo al usuario.
                    leido = True
                    if on_estado: on_estado("leido", _("Chat en lectura."))
            except Exception as exc:
                if parada.is_set(): break
                err_con += 1
                ultimo_error = exc
                logger.warning("Error ciclo chat (%d/%d): %s", err_con, MAX_ERR, exc)
                if err_con >= MAX_ERR:
                    if on_estado: on_estado("error_conexion", _("Demasiados errores consecutivos."))
                    break
            if not parada.is_set():
                time.sleep(0.1)
    except Exception as exc:
        if not parada.is_set():
            ultimo_error = exc
            logger.error("Error en captura: %s", exc)
    finally:
        # El cliente es de este intento (pytchat es síncrono aquí: nadie más
        # lo usa); cerrarlo evita ir dejando sockets por cada reconexión.
        try:    cliente.close()
        except Exception as error: logger.debug("no se pudo cerrar el cliente del chat: %s", error)
        if not parada.is_set():
            try:    chat.raise_for_status()
            except Exception as exc:
                ultimo_error = exc
    return ultimo_error


def _str(v, d):
    if v is None: return d
    r = str(v).strip()
    return r if r else d


def _mensaje_error_amigable(exc) -> str:
    t = str(exc).lower()
    if "invalid video id" in t:
        return _("El ID de vídeo no es válido. Revisa el enlace.")
    if "cannot find channel id" in t:
        return (_("YouTube todavía no muestra este vídeo. Pasa en los "
                  "primeros segundos de un directo y siempre con los "
                  "directos privados."))
    if "private" in t:
        return _("Este directo es privado. No se puede acceder.")
    if "members only" in t:
        return _("El chat está restringido a miembros del canal.")
    if "finished" in t or "unavailable" in t:
        return _("El directo ha terminado o no está disponible.")
    if "does not exist" in t:
        return _("El vídeo no existe. Revisa el enlace.")
    # Traductores: {error} es el detalle técnico.
    return _("No se pudo conectar: {error}").format(error=exc)


# ── Main ─────────────────────────────────────────────────────────────────────

def armar_callbacks_captura(cola, config, stats, parada):
    """Arma una conexión y devuelve sus dos callbacks asociados."""
    conexiones = conexion.Conexiones(cola, config, stats, parada, vista=VistaGui())
    return conexiones.conectar, conexiones.desconectar


def iniciar_interfaz(config, cola, stats, worker, parada, iniciar_gui_fn=None):
    """Arranca la GUI y cierra los sonidos al volver del bucle."""
    if iniciar_gui_fn is None:
        from bellbird.ui.gui import iniciar_gui as iniciar_gui_fn
    iniciar_captura_cb, detener_captura_cb = armar_callbacks_captura(
        cola, config, stats, parada)
    iniciar_gui_fn(
        config=config, cola=cola, stats=stats, worker=worker, parada=parada,
        iniciar_captura_cb=iniciar_captura_cb,
        detener_captura_cb=detener_captura_cb,
    )
    _snd.cerrar()


def main():
    # Autocomprobación del paquete: la corre construir.bat sobre el exe armado.
    # Va antes que todo, sin logging, sin mutex ni ventanas.
    if len(sys.argv) > 1 and sys.argv[1] == "--autocomprobar":
        from bellbird.core import autocomprobacion
        sys.exit(autocomprobacion.principal(sys.argv[2:]))
    # Modo instalador: corre dentro del exe nuevo mientras la app vieja
    # se cierra. Va primero que todo, sin logging, sin mutex ni ventanas.
    if len(sys.argv) > 1 and sys.argv[1] == "--instalar-actualizacion":
        from bellbird.core import instalador
        sys.exit(instalador.principal_instalador())
    # Aquí y no al importar el módulo: así los tests y el smoke test pueden
    # importar main sin crear el handler de ytchat.log (contaminaba el log real).
    try:
        resultado_migracion = migracion_datos.migrar(
            paths.carpeta_instalacion(), paths.carpeta_datos(), paths.datos_a_migrar(),
            paths.sounds_ini(), paths.pares_de_nombres_anteriores())
    except Exception:
        resultado_migracion = None
    configurar_logging()
    if resultado_migracion is not None:
        try:
            if resultado_migracion.movidos or resultado_migracion.copiados:
                logger.info(
                    "Migración de datos: movidos %s, copiados %s",
                    resultado_migracion.movidos, resultado_migracion.copiados)
            for nombre in resultado_migracion.conflictos:
                logger.warning(
                    "Migración de datos: %s ya existe en data, no se tocó nada",
                    nombre)
            for error in resultado_migracion.errores:
                logger.warning("Migración de datos: %s", error)
        except Exception as error:
            logger.debug("no se pudo informar el resultado de la migración: %s", error)
    diagnostico.instalar_capturadores(
        paths.log_fallos(), version=APP_VERSION)
    diagnostico.registrar_entorno_en_hilo(APP_VERSION)

    if not _verificar_instancia_unica(sys.argv):
        # Ya hay una instancia abierta. Intentamos informar al usuario.
        try:
            import ctypes
            MB_ICONINFORMATION = 0x40  # Bandera de Win32 para el icono informativo.
            MB_SETFOREGROUND = 0x00010000  # Bandera de Win32 para traer al frente.
            MB_TOPMOST = 0x00040000  # Bandera de Win32 para mantener arriba el aviso.
            ctypes.windll.user32.MessageBoxW(
                0,
                # Traductores: {app} es el nombre de la aplicación.
                (_("{app} ya se está ejecutando.\nCierra la otra ventana "
                   "antes de abrir una nueva.").format(app=APP_NAME)),
                APP_NAME, MB_ICONINFORMATION | MB_SETFOREGROUND | MB_TOPMOST
            )
        except Exception as error:
            logger.debug("no se pudo mostrar el aviso de instancia en curso: %s", error)
        sys.exit(0)

    config = cargar_configuracion()
    alias.usar(alias.cargar(paths.alias()))

    config.setdefault("silenciados_runtime", set())
    config.setdefault("silenciados_ocultar", set())

    sonidos_config = cargar_sonidos()
    try:    _snd.cargar(sonidos_config)
    except Exception as exc:
        logger.warning("No se pudo cargar sonidos: %s", exc)
    if config.get("silenciar_sonidos", False):
        _snd.silenciar_todo(True)

    cola   = ColaTTS()
    stats  = Stats()
    worker = TTSWorker(cola=cola, config=config)
    worker.start()
    if not worker.esperar_inicio(timeout=10.0):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                _("No se pudo iniciar el motor de voz.\n\n"
                  "Comprueba que tienes al menos una voz instalada en\n"
                  "Configuración → Hora e idioma → Voz."),
                APP_NAME,
                0x10  # MB_ICONERROR
            )
        except Exception as error:
            logger.debug("no se pudo mostrar el aviso del motor de voz: %s", error)
        _snd.reproducir("error")
        sys.exit(1)

    parada = threading.Event()

    try:
        import wx
        from bellbird.ui.gui import iniciar_gui
    except ImportError as exc:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                # Traductores: {detalle} es el error técnico.
                (_("wxPython no está instalado.\nEjecuta instalar.bat.\n\n{detalle}").format(
                    detalle=exc)),
                APP_NAME, 0x10
            )
        except Exception as error:
            logger.debug("no se pudo mostrar el aviso de wxPython ausente: %s", error)
        sys.exit(1)

    iniciar_interfaz(config, cola, stats, worker, parada, iniciar_gui_fn=iniciar_gui)
    sys.exit(0)


if __name__ == "__main__":
    main()
