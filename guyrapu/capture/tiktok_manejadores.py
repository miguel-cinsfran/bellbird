"""Traducción de eventos de TikTok a eventos de la aplicación.

Cambia solo cuando cambia qué eventos escucha la aplicación o cómo los
traduce; la conexión y la reconexión viven en tiktok_captura.
"""

from __future__ import annotations

import time

from guyrapu.capture.agrupar_entradas import (
    AgrupadorEntradas,
    nombres_del_grupo,
)
from guyrapu.capture.agrupar_me_gusta import AgrupadorMeGusta
from guyrapu.capture.filtro_autores import entra_en_grupo
from guyrapu.capture import tiktok_encuestas
from guyrapu.capture import tiktok_metas
from guyrapu.capture import tiktok_batallas
from guyrapu.capture.tiktok_captura import (
    _clase_suscripcion,
    autor_de_evento,
)
from guyrapu.core.idioma import _
from guyrapu.core.config import (
    TIPO_COFRE,
    TIPO_COMPARTIR,
    TIPO_ENTRADA,
    TIPO_ME_GUSTA,
    TIPO_MIEMBRO,
    TIPO_SEGUIR,
    TIPO_SUPERCHAT,
    TIPO_TEXTO,
)


def _al_comentar(on_evento, descartar):
    async def _on_comment(evento):
        if descartar(evento):
            return
        autor, canal_id = autor_de_evento(evento)
        on_evento(autor, (evento.comment or "").strip(), TIPO_TEXTO, "", canal_id)

    return _on_comment


def _al_regalo(on_evento, descartar):
    async def _on_gift(evento):
        if descartar(evento):
            return
        # Los regalos «en racha» disparan un evento por repetición: solo se
        # anuncia el final de la racha, con el total, para no inundar el TTS.
        if getattr(evento, "streaking", False):
            return
        autor, canal_id = autor_de_evento(evento)
        gift = getattr(evento, "gift", None)
        nombre = (getattr(gift, "name", "") or "regalo").strip()
        diamantes = int(getattr(gift, "diamond_count", 0) or 0)
        repes = max(1, int(getattr(evento, "repeat_count", 1) or 1))
        total = diamantes * repes
        detalle = f"{nombre} x{repes}" if repes > 1 else nombre
        monto = f"{total} diamantes" if total else ""
        on_evento(autor, detalle, TIPO_SUPERCHAT, monto, canal_id)

    return _on_gift


def _al_suscribir(on_evento, descartar):
    async def _on_subscribe(evento):
        if descartar(evento):
            return
        autor, canal_id = autor_de_evento(evento)
        on_evento(autor, "", TIPO_MIEMBRO, "", canal_id)

    return _on_subscribe


def _al_seguir(on_evento, descartar):
    async def _on_follow(evento):
        if descartar(evento):
            return
        autor, canal_id = autor_de_evento(evento)
        on_evento(autor, "", TIPO_SEGUIR, "", canal_id)

    return _on_follow


def _al_compartir(on_evento, descartar):
    async def _on_share(evento):
        if descartar(evento):
            return
        autor, canal_id = autor_de_evento(evento)
        on_evento(autor, "", TIPO_COMPARTIR, "", canal_id)

    return _on_share


def _al_cofre(on_evento, descartar):
    async def _on_envelope(evento):
        if descartar(evento):
            return
        info = getattr(evento, "envelope_info", None)
        nombre = (getattr(info, "send_user_name", "") or "").strip()
        canal_id = str(getattr(info, "send_user_id", "") or "").strip()
        if not nombre or not canal_id:
            autor, ident = autor_de_evento(evento)
            nombre = nombre or autor
            canal_id = canal_id or ident
        on_evento(nombre, "", TIPO_COFRE, "", canal_id)

    return _on_envelope


def _emitir_vencidos(agrupador, on_evento, ahora):
    """Emite cada grupo de me gusta ya vencido como un aviso con su total."""
    for autor, canal_id, total in agrupador.vencidos(ahora):
        on_evento(autor, "", TIPO_ME_GUSTA, str(total), canal_id)


def _emitir_entradas_vencidas(agrupador, on_evento, ahora):
    """Emite el grupo de entradas vencido, con todos sus nombres."""
    personas = agrupador.vencido(ahora)
    if not personas:
        return
    if len(personas) == 1:
        autor, canal_id = personas[0]
        on_evento(autor, "", TIPO_ENTRADA, "", canal_id)
        return
    nombres = nombres_del_grupo([autor for autor, _canal in personas])
    on_evento(nombres, "", TIPO_ENTRADA, str(len(personas)), "")


def _al_me_gusta(on_evento, descartar, agrupador):
    async def _on_like(evento):
        if descartar(evento):
            return
        autor, canal_id = autor_de_evento(evento)
        ahora = time.monotonic()
        agrupador.sumar(autor, canal_id, getattr(evento, "count", None),
                        ahora)
        _emitir_vencidos(agrupador, on_evento, ahora)

    return _on_like


def _al_sticker(on_evento, descartar):
    async def _on_emote(evento):
        if descartar(evento):
            return
        try:
            lista = getattr(evento, "emote_list", None) or []
            cuantos = len(lista)
        except TypeError:
            cuantos = 0
        texto = "sticker" if cuantos <= 1 else f"{cuantos} stickers"
        autor, canal_id = autor_de_evento(evento)
        on_evento(autor, texto, TIPO_TEXTO, "", canal_id)

    return _on_emote


def _al_pregunta(on_evento, descartar):
    async def _on_question(evento):
        if descartar(evento):
            return
        datos = getattr(evento, "data", None)
        if datos is None:
            return
        contenido = (getattr(datos, "content", "") or "").strip()
        if not contenido:
            return
        autor, canal_id = autor_de_evento(datos)
        # Traductores: texto del chat de TikTok que se anuncia. {contenido} es la pregunta.
        on_evento(autor, _("Pregunta: {contenido}").format(contenido=contenido), TIPO_TEXTO, "", canal_id)

    return _on_question


def _al_encuesta(on_evento, descartar):
    async def _on_poll(evento):
        if descartar(evento):
            return
        tiktok_encuestas.procesar(evento, on_evento)

    return _on_poll


def _al_meta(on_evento, descartar):
    async def _on_goal(evento):
        if descartar(evento):
            return
        tiktok_metas.procesar(evento, on_evento)

    return _on_goal


def _al_batalla(on_evento, descartar):
    async def _on_battle(evento):
        if descartar(evento):
            return
        tiktok_batallas.procesar(evento, on_evento)

    return _on_battle


def _al_armies(on_evento, descartar):
    async def _on_armies(evento):
        if descartar(evento):
            return
        tiktok_batallas.procesar_armies(evento)

    return _on_armies


def _al_pausa(on_estado, descartar):
    async def _on_pause(evento):
        if descartar(evento):
            return
        if on_estado:
            # Traductores: estado que se anuncia y se muestra en la barra de estado.
            on_estado("directo_pausado",
                      _("El directo de TikTok está en pausa."))

    return _on_pause


def _al_reanudacion(on_estado, descartar):
    async def _on_unpause(evento):
        if descartar(evento):
            return
        if on_estado:
            # Traductores: estado que se anuncia y se muestra en la barra de estado.
            on_estado("directo_reanudado",
                      _("El directo de TikTok continúa."))

    return _on_unpause


def _al_entrar(on_evento, descartar, agrupador, config):
    async def _on_join(evento):
        if descartar(evento):
            return
        autor, canal_id = autor_de_evento(evento)
        if not entra_en_grupo(autor, config):
            return
        ahora = time.monotonic()
        agrupador.sumar(autor, canal_id, ahora)
        _emitir_entradas_vencidas(agrupador, on_evento, ahora)

    return _on_join


def _al_contar_espectadores(on_espectadores, agrupador=None, on_evento=None,
                            agrupador_entradas=None):
    async def _on_user_seq(evento):
        # El conteo llega seguido: también vacía los grupos vencidos, para
        # que el último no quede esperando a otro toque.
        ahora = time.monotonic()
        if agrupador is not None and on_evento is not None:
            _emitir_vencidos(agrupador, on_evento, ahora)
        if agrupador_entradas is not None and on_evento is not None:
            _emitir_entradas_vencidas(agrupador_entradas, on_evento, ahora)
        # Conteo de espectadores EN VIVO (se actualiza cada pocos segundos).
        if not on_espectadores:
            return
        try:
            ahora = int(getattr(evento, "total", None))
        except (TypeError, ValueError):
            return
        try:
            total = int(getattr(evento, "total_user", None))
        except (TypeError, ValueError):
            total = None
        on_espectadores(ahora, total)

    return _on_user_seq


# Seguir, compartir, cofre y me gusta existen en la TikTokLive instalada;
# si en otra versión falta alguna clase, ese manejador no se registra.
_EVENTOS_OPCIONALES = [
    ("FollowEvent", _al_seguir, "evento"),
    ("ShareEvent", _al_compartir, "evento"),
    ("EnvelopeEvent", _al_cofre, "evento"),
    # Los me gusta llegan de a montones: se agrupan por persona y cada
    # grupo sale con su total al vencer la ventana (ver AgrupadorMeGusta).
    ("LikeEvent", _al_me_gusta, "megusta"),
    ("EmoteChatEvent", _al_sticker, "evento"),
    ("QuestionNewEvent", _al_pregunta, "evento"),
    ("PollEvent", _al_encuesta, "evento"),
    ("GoalUpdateEvent", _al_meta, "evento"),
    ("LinkMicBattleEvent", _al_batalla, "evento"),
    ("LinkMicArmiesEvent", _al_armies, "evento"),
    ("LivePauseEvent", _al_pausa, "estado"),
    ("LiveUnpauseEvent", _al_reanudacion, "estado"),
]


def _segundos_me_gusta(config) -> int:
    """Segundos de agrupación de los me gusta, con el borde de la config."""
    if not (config or {}).get("tiktok_agrupar_me_gusta", True):
        return 0
    return _segundos_entre_uno_y_ciento_veinte(
        (config or {}).get("tiktok_segundos_me_gusta", 10))


def _segundos_entradas(config) -> int:
    """Segundos de agrupación de las entradas, con el borde de la config."""
    if not (config or {}).get("tiktok_agrupar_entradas", True):
        return 0
    return _segundos_entre_uno_y_ciento_veinte(
        (config or {}).get("tiktok_segundos_entradas", 10))


def _segundos_entre_uno_y_ciento_veinte(valor) -> int:
    try:
        segundos = int(valor)
    except (TypeError, ValueError):
        return 10
    return max(1, min(120, segundos))


def _reiniciar_registros() -> None:
    """Olvida encuestas, metas y batallas de una conexión anterior."""
    tiktok_encuestas.reiniciar()
    tiktok_metas.reiniciar()
    tiktok_batallas.reiniciar()


def registrar_manejadores(client, modulo_eventos, *, on_evento,
                          on_espectadores, config, descartar,
                          on_estado=None):
    """Registra los manejadores de eventos de TikTok en `client`."""
    _reiniciar_registros()
    agrupador = AgrupadorMeGusta(ventana=lambda: _segundos_me_gusta(config))
    agrupador_entradas = AgrupadorEntradas(
        ventana=lambda: _segundos_entradas(config))
    clase_suscripcion = _clase_suscripcion(modulo_eventos)
    client.on(modulo_eventos.CommentEvent)(
        _al_comentar(on_evento, descartar))
    client.on(modulo_eventos.GiftEvent)(_al_regalo(on_evento, descartar))
    if clase_suscripcion is not None:
        client.on(clase_suscripcion)(_al_suscribir(on_evento, descartar))
    for nombre, fabrica, modo in _EVENTOS_OPCIONALES:
        clase = getattr(modulo_eventos, nombre, None)
        if clase is None:
            continue
        if modo == "estado":
            if on_estado is None:
                continue
            client.on(clase)(fabrica(on_estado, descartar))
        elif modo == "megusta":
            client.on(clase)(fabrica(on_evento, descartar, agrupador))
        else:
            client.on(clase)(fabrica(on_evento, descartar))
    client.on(modulo_eventos.JoinEvent)(
        _al_entrar(on_evento, descartar, agrupador_entradas, config))
    client.on(modulo_eventos.RoomUserSeqEvent)(_al_contar_espectadores(
        on_espectadores, agrupador, on_evento, agrupador_entradas))
