"""Captura del chat de TikTok LIVE (fase 1: solo lectura, sin login).

Usa la librería no oficial TikTokLive (el «pytchat de TikTok»): se conecta a
cualquier directo público con el @usuario del streamer y entrega comentarios,
regalos y suscripciones en tiempo real. La firma de la conexión pasa por el
servidor de Euler Stream (tier gratuito, de sobra para uso personal). No hay
API oficial de TikTok para esto; los riesgos y la decisión de no implementar
escritura/moderación están en INFORME_TIKTOK.md.

Diseño espejo de la captura de YouTube en main.py:
  - `usuario_de_url()` es lógica pura (testeable sin la librería).
  - `capturar_con_reconexion()` bloquea en un hilo propio y reporta por
    callbacks: `on_info(dict)` al conectar (título, espectadores, el flujo de
    TikTok (FLV, o HLS si no hay FLV) que reproduce libVLC tal cual),
    `on_evento(...)` por cada mensaje y
    `on_estado(tipo, texto)` para la GUI. El filtrado, el TTS y la cola los
    decide quien llama (main), igual que con pytchat.
  - Todo degrada tras guardas: sin TikTokLive instalado, `disponible()` es
    False y la app avisa sin romperse.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import re
import sys
import time

from bellbird.capture.tiktok_reconexion import (desenlace, texto_agotado,
    texto_reintento)
from bellbird.core import avisos_tiktok
from bellbird.core import diagnostico
from bellbird.core import paths
from bellbird.core.config import (TIPO_TEXTO, TIPO_SUPERCHAT, TIPO_MIEMBRO, TIPO_ENTRADA,
    TIPO_SEGUIR, TIPO_COMPARTIR, TIPO_COFRE, TIPO_ME_GUSTA)
from bellbird.core.idioma import _

logger = diagnostico.obtener_logger(__name__)

# tiktok.com/@usuario[/live]. Los usuarios de TikTok llevan letras, números,
# guion bajo y punto. No se aceptan "@usuario" sueltos (chocarían con los
# handles de YouTube); hace falta la URL con dominio.
_URL_RE = re.compile(
    r"(?<![\w.-])(?:https?://)?(?:(?:www|m)\.)?tiktok\.com/@([\w.]+)(?:/live)?(?:[/?#]|$)",
    re.IGNORECASE)


def usuario_de_url(entrada: str) -> str:
    """@usuario si la entrada es una URL de TikTok; cadena vacía si no lo es."""
    m = _URL_RE.search((entrada or "").strip())
    return m.group(1).lower() if m else ""


def _parchear_extended_user() -> None:
    """Arregla un choque entre TikTokLive 6.6.5 y betterproto 2.0.0b7.

    `ExtendedUser.from_user` hace `ExtendedUser(**user.to_pydict())`, y en esta
    betterproto `to_pydict()` devuelve claves camelCase (p. ej. «nickName») que
    el constructor no acepta → lanza TypeError (que el fallback de la librería
    NO captura, solo AttributeError). Resultado: leer `evento.user` revienta y se
    pierden comentarios/regalos según qué campos traiga cada usuario.

    Lo reemplazamos por una copia campo a campo en snake_case (lo que la propia
    librería ya hace como respaldo). Idempotente y con guardas: si la librería
    cambia, no rompe nada.
    """
    try:
        from TikTokLive.proto.custom_proto import ExtendedUser
    except Exception:
        return
    if getattr(ExtendedUser, "_from_user_parcheado", False):
        return

    def _from_user(cls, user, **kwargs):
        if isinstance(user, cls):
            return user
        datos = {}
        for campo in user.__class__.__dataclass_fields__:
            try:
                datos[campo] = getattr(user, campo)
            except AttributeError as exc:
                bajo = f"_{campo}"
                datos[campo] = (getattr(user, bajo, None)
                                if "is set to None" in str(exc) else None)
        return cls(**datos)

    try:
        ExtendedUser.from_user = classmethod(_from_user)
        ExtendedUser._from_user_parcheado = True
    except Exception as exc:
        logger.debug("no se pudo parchear ExtendedUser: %s", exc)


def disponible() -> bool:
    """¿Está instalada TikTokLive? Sin importarla, para no frenar el arranque."""
    if getattr(sys, "frozen", False):
        return (paths.carpeta_interna() / "TikTokLive").is_dir()
    try:
        return importlib.util.find_spec("TikTokLive") is not None
    except Exception:
        return False


# ── Sesión de captura ─────────────────────────────────────────────────────────

def _mejor_flujo(stream: dict) -> str:
    """URL de vídeo del directo. Se PREFIERE el FLV: el HLS de TikTok suele dar
    timeout en el reproductor y el FLV sobre HTTP va directo y trae audio. HD
    antes que SD; si no hay FLV, se cae al HLS o al RTMP como último recurso."""
    flv = stream.get("flv_pull_url") or {}
    if isinstance(flv, dict):
        for clave in ("FULL_HD1", "ORIGION", "HD1", "SD2", "SD1"):
            if flv.get(clave):
                return flv[clave].strip()
        for v in flv.values():          # cualquier calidad presente
            if v:
                return str(v).strip()
    return (stream.get("hls_pull_url") or stream.get("rtmp_pull_url") or "").strip()


def _g(obj, nombre_attr) -> str:
    """getattr a prueba de betterproto: sus alias no siempre existen y pueden
    lanzar en vez de devolver el defecto; devolvemos "" ante cualquier fallo."""
    try:    return str(getattr(obj, nombre_attr, "") or "")
    except Exception: return ""


def autor_de_evento(evento) -> tuple[str, str]:
    """(nombre, id) del autor de un evento de TikTok, sin usar el wrapper
    `.user` cuando se puede (crashea con betterproto 2.0.0b7).

    En eventos reales el usuario llega como `User` plano: el nombre está en el
    campo REAL `nick_name`, no en el alias `nickname` (que es de ExtendedUser).
    Probamos ambos y varios respaldos. Para comentarios está `user_info` (proto
    crudo); regalos/suscripciones caen a `.user` (ya sin crash por el parche).
    Nunca lanza: mejor «Usuario» que perder el evento.
    """
    u = getattr(evento, "user_info", None)
    if u is None:
        try:    u = evento.user
        except Exception as exc:
            logger.debug("autor: no se pudo leer user: %s", exc)
            u = None
    if u is None:
        return "Usuario", ""
    nombre = (_g(u, "nick_name") or _g(u, "nickname") or _g(u, "unique_id")
              or _g(u, "username") or _g(u, "display_id") or "Usuario").strip()
    canal_id = (_g(u, "id") or _g(u, "unique_id") or _g(u, "username"))
    return (nombre or "Usuario"), canal_id


def _info_de_sala(client) -> dict:
    """Metadatos de la sala en el formato del panel de información + la URL del
    flujo de vídeo del directo (clave interna `_url_flujo`, la consume el
    reproductor)."""
    info = client.room_info or {}
    stream = info.get("stream_url") or {}
    owner = info.get("owner") or {}
    return {
        "titulo":      (info.get("title") or "").strip(),
        "canal":       (owner.get("nickname") or "").strip(),
        "vistas":      info.get("user_count"),   # espectadores actuales
        "en_vivo":     True,
        "_url_flujo":  _mejor_flujo(stream),
    }


def es_previo_a_conexion(creado_ms, conectado_s, margen_s=5.0) -> bool:
    """¿El evento se creó más de `margen_s` antes de conectar? Ante la duda
    (sin hora, hora 0 o todavía sin conectar) es Falso: se lee."""
    try:
        if isinstance(creado_ms, bool):
            return False
        if not isinstance(creado_ms, (int, float)):
            return False
        if creado_ms <= 0:
            return False
        if conectado_s is None or isinstance(conectado_s, bool):
            return False
        return (creado_ms / 1000) < (float(conectado_s) - float(margen_s))
    except Exception:
        return False


def _creado_ms(evento):
    """ms de creación del evento (`common.create_time`); 0 si no se puede leer."""
    try:
        return getattr(getattr(evento, "common", None), "create_time", 0)
    except Exception:
        return 0


def es_historico(evento) -> bool:
    """¿TikTok lo marcó como mensaje viejo (`is_history` del sobre)? El cliente
    de la librería no copia esa marca a los eventos, así que la anota el
    envoltorio de `_envolver_marcador_historico`. Ante la duda, es Falso."""
    try:
        return bool(getattr(evento, "_ytchat_historico", False))
    except Exception:
        return False


def debe_pasar_me_gusta(ultimo, ahora, intervalo=3.0) -> bool:
    """¿Este me gusta puede pasar? Como mucho UNO cada `intervalo` segundos:
    los me gusta llegan de a montones y saturarían el sonido. `ultimo` es el
    `time.monotonic()` del último que pasó, o None si aún no pasó ninguno.
    Ante la duda, pasa."""
    try:
        if ultimo is None:
            return True
        return (float(ahora) - float(ultimo)) >= float(intervalo)
    except (TypeError, ValueError):
        return True


def _marcar_historicos(sobre, eventos):
    """Anota `_ytchat_historico` en cada evento si el sobre trae `is_history`
    y devuelve los eventos tal cual, sin cambiar el retorno del método."""
    try:
        historico = bool(getattr(sobre, "is_history", False))
    except Exception:
        historico = False
    if historico and eventos:
        for ev in eventos:
            try:
                ev._ytchat_historico = True
            except Exception as error:
                logger.debug("no se pudo anotar la marca de histórico en el evento: %s", error)
    return eventos


def _envolver_marcador_historico(client) -> None:
    """Envuelve `client._parse_webcast_response_message` para copiar la marca
    `is_history` del sobre a cada evento devuelto (ver `es_historico`).

    Respeta si el método es síncrono o asíncrono y su valor de retorno. Si el
    método no existe o el envoltorio falla, solo se registra y la captura
    sigue con el margen de 5 s de siempre."""
    original = getattr(client, "_parse_webcast_response_message", None)
    if original is None:
        logger.debug("sin marcador is_history: el cliente no trae "
                     "_parse_webcast_response_message")
        return
    try:
        if asyncio.iscoroutinefunction(original):
            async def _envuelto(*args, **kwargs):
                eventos = await original(*args, **kwargs)
                try:
                    sobre = kwargs.get("webcast_response_message")
                    if sobre is None and len(args) >= 2:
                        sobre = args[1]
                    return _marcar_historicos(sobre, eventos)
                except Exception as exc:
                    logger.debug("marcador is_history: %s", exc)
                    return eventos
        else:
            def _envuelto(*args, **kwargs):
                eventos = original(*args, **kwargs)
                try:
                    sobre = kwargs.get("webcast_response_message")
                    if sobre is None and len(args) >= 2:
                        sobre = args[1]
                    return _marcar_historicos(sobre, eventos)
                except Exception as exc:
                    logger.debug("marcador is_history: %s", exc)
                    return eventos
        client._parse_webcast_response_message = _envuelto
    except Exception as exc:
        logger.debug("no se pudo envolver _parse_webcast_response_message: %s", exc)


async def _vigilar_parada(client, parada) -> None:
    """Convierte el Event de parada (mundo de hilos) en un disconnect (asyncio)."""
    try:
        while not parada.is_set():
            await asyncio.sleep(0.3)
        await client.disconnect()
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.debug("vigilar_parada: %s", exc)


def _clase_suscripcion(modulo_eventos):
    """Clase del evento de suscripción según la TikTokLive instalada.

    En 6.6.5 y anteriores es `SubscribeEvent`; en 6.6.6 desapareció y el
    aviso de suscripción es `SubNotifyEvent`. Si no hay ninguna, None y
    quien llama simplemente no registra ese manejador, sin error."""
    for nombre in ("SubscribeEvent", "SubNotifyEvent"):
        clase = getattr(modulo_eventos, nombre, None)
        if clase is not None:
            return clase
    return None


def _registrar_manejadores(client, modulo_eventos, on_evento, on_estado,
                           on_info, on_espectadores, anunciar_entradas,
                           hora_conexion):
    """Manejadores de una sesión: conexión, filtrado de previos y cierre.
    `hora_conexion` es la lista compartida entre `_on_connect` y
    `descartar`."""
    from bellbird.capture import tiktok_manejadores
    ConnectEvent = modulo_eventos.ConnectEvent
    LiveEndEvent = modulo_eventos.LiveEndEvent
    DisconnectEvent = modulo_eventos.DisconnectEvent

    @client.on(ConnectEvent)
    async def _on_connect(evento):
        hora_conexion[0] = time.time()
        try:
            if on_info:
                on_info(_info_de_sala(client))
        except Exception as exc:
            logger.debug("info de sala: %s", exc)
        if on_estado:
            # Traductores: estado que se anuncia y se muestra en la barra de estado al conectar.
            on_estado("conectado", _("Conectado al directo de TikTok."))

    def descartar(evento) -> bool:
        return es_historico(evento) or es_previo_a_conexion(
            _creado_ms(evento), hora_conexion[0])

    tiktok_manejadores.registrar_manejadores(
        client, modulo_eventos, on_evento=on_evento,
        on_espectadores=on_espectadores, anunciar_entradas=anunciar_entradas,
        descartar=descartar, on_estado=on_estado)

    @client.on(LiveEndEvent)
    async def _on_live_end(evento):
        # El directo acabó: desconectamos para que connect() retorne y anuncie
        # el fin el bucle UNA sola vez; si no, saldría por duplicado y
        # reintentaría.
        try:    await client.disconnect()
        except Exception as exc:
            logger.debug("disconnect en LiveEnd: %s", exc)

    @client.on(DisconnectEvent)
    async def _on_disconnect(evento):
        pass  # el cierre ordenado lo gestiona quien llama


def _correr_cliente(client, parada):
    """Corre el cliente en su loop hasta que se desconecte. Devuelve la
    excepción de conexión si la hubo, o None si terminó con normalidad."""
    error = None

    async def _correr():
        vigia = asyncio.create_task(_vigilar_parada(client, parada))
        try:
            # Sin los eventos iniciales: al entrar se leen los mensajes
            # anteriores a la conexion, también en cada reconexion. El
            # ConnectEvent sigue llegando, así que _on_connect no se toca.
            await client.connect(fetch_room_info=True,
                                 process_connect_events=False)
        finally:
            vigia.cancel()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_correr())
    except Exception as exc:
        error = exc
        logger.debug("sesión TikTok: %s", exc)
    finally:
        # Drenar lo pendiente (cierre del websocket, keepalives) antes de
        # cerrar el loop; si no, asyncio escupe «Task was destroyed but it
        # is pending» al terminar cada sesión.
        try:
            pendientes = asyncio.all_tasks(loop)
            for t in pendientes:
                t.cancel()
            if pendientes:
                loop.run_until_complete(
                    asyncio.gather(*pendientes, return_exceptions=True))
        except Exception as error:
            logger.debug("no se pudo cancelar las tareas al detener: %s", error)
        try:    loop.close()
        except Exception as error: logger.debug("no se pudo cerrar el bucle al detener: %s", error)
    return error


def _sesion(usuario, parada, on_evento, on_estado, on_info, on_espectadores,
            anunciar_entradas=False):
    """Una conexión completa (bloquea hasta desconectar). Devuelve la excepción
    de conexión si la hubo, o None si terminó con normalidad.

    Lo que falle al preparar la sesión (imports y creación del cliente) no
    sale como excepción: se devuelve como el error de la sesión, igual que
    el de conexión, para que el bucle lo informe en vez de matar el hilo."""
    try:
        _parchear_extended_user()   # antes de tocar ningún evento (ver la función)
        from TikTokLive import TikTokLiveClient
        from TikTokLive.events import (ConnectEvent, CommentEvent, GiftEvent,
                                       DisconnectEvent, LiveEndEvent,
                                       RoomUserSeqEvent, JoinEvent)
        from TikTokLive import events as modulo_eventos
        client = TikTokLiveClient(unique_id=usuario)
        _envolver_marcador_historico(client)
    except Exception as exc:
        logger.debug("preparación TikTok: %s", exc)
        return exc
    hora_conexion: list = [None]
    _registrar_manejadores(client, modulo_eventos, on_evento, on_estado,
                           on_info, on_espectadores, anunciar_entradas,
                           hora_conexion)
    return _correr_cliente(client, parada)


def _sesion_protegida(usuario, parada, on_evento, on_estado, on_info,
                       on_espectadores, config):
    """Una sesión que nunca mata el hilo: lo inesperado vuelve como error
    de conexión y sigue la misma política de reintentos."""
    try:
        return _sesion(usuario, parada, on_evento, on_estado, on_info,
                       on_espectadores,
                       anunciar_entradas=avisos_tiktok.modo_de(config, TIPO_ENTRADA) != "ocultar")
    except Exception as exc:
        # Nada de lo que salga de _sesion puede matar el hilo: se trata
        # como un error de conexión y sigue la misma política de reintentos.
        logger.debug("sesión TikTok inesperada: %s", exc)
        return exc


def capturar_con_reconexion(usuario, config, parada, on_evento,
                            on_estado=None, on_info=None,
                            on_espectadores=None, offline_pasajero=False) -> None:
    """Bucle de captura con reintentos, mismo contrato de estados que YouTube.
    Bloquea: llamar desde un hilo aparte. offline_pasajero reintenta el «no
    está en directo» antes de la primera conexión. on_espectadores(n, total)
    recibe los de ahora y los que pasaron."""
    if not disponible():
        if on_estado:
            # Traductores: error permanente que se anuncia y se muestra en la barra de estado.
            on_estado("error_permanente",
                      _("Falta la biblioteca TikTokLive. Ejecuta instalar.bat."))
        parada.set()
        return

    intentos = 0
    conecto = [False, False]

    def _estado(tipo, texto):
        # Se intercepta «conectado» para contar solo los fallos SEGUIDOS: un
        # directo largo con microcortes sueltos no debe agotar max_intentos.
        if tipo == "conectado":
            conecto[0] = conecto[1] = True
        if on_estado:
            on_estado(tipo, texto)

    while not parada.is_set():
        # Traductores: estado que se anuncia y se muestra en la barra de estado al conectar. {usuario} es el usuario de TikTok.
        _estado("conectando", _("Conectando al directo de TikTok de @{usuario}…").format(usuario=usuario))
        conecto[0] = False
        err = _sesion_protegida(usuario, parada, on_evento, _estado, on_info,
                                on_espectadores, config)
        if conecto[0]:
            intentos = 0
        fin = desenlace(err, parado=parada.is_set(),
                        conecto_alguna=conecto[1],
                        offline_pasajero=offline_pasajero,
                        reconectar=config.get("reconectar", True))
        if fin is not None:
            if fin[0] is not None:
                _estado(*fin)
            parada.set()
            break
        intentos += 1
        mi = config.get("max_intentos", 0)
        if mi > 0 and intentos >= mi:
            _estado("error", texto_agotado(mi))
            parada.set()
            break
        espera = config.get("espera_entre_intentos", 10)
        _estado("reintentando", texto_reintento(espera, intentos, mi))
        parada.wait(timeout=espera)
