"""Traducción de eventos de TikTok a eventos de la aplicación.

Cambia solo cuando cambia qué eventos escucha la aplicación o cómo los
traduce; la conexión y la reconexión viven en tiktok_captura.
"""

from __future__ import annotations

import time

from ytchat.capture.agrupar_me_gusta import AgrupadorMeGusta
from ytchat.capture.tiktok_captura import (
    _clase_suscripcion,
    autor_de_evento,
)
from ytchat.core.config import (
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
        autor, canal_id = autor_de_evento(evento)
        on_evento(autor, "", TIPO_COFRE, "", canal_id)

    return _on_envelope


def _emitir_vencidos(agrupador, on_evento, ahora):
    """Emite cada grupo de me gusta ya vencido como un aviso con su total."""
    for autor, canal_id, total in agrupador.vencidos(ahora):
        on_evento(autor, "", TIPO_ME_GUSTA, str(total), canal_id)


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
        on_evento(autor, f"Pregunta: {contenido}", TIPO_TEXTO, "", canal_id)

    return _on_question


def _al_pausa(on_estado, descartar):
    async def _on_pause(evento):
        if descartar(evento):
            return
        if on_estado:
            on_estado("directo_pausado",
                      "El directo de TikTok está en pausa.")

    return _on_pause


def _al_reanudacion(on_estado, descartar):
    async def _on_unpause(evento):
        if descartar(evento):
            return
        if on_estado:
            on_estado("directo_reanudado",
                      "El directo de TikTok continúa.")

    return _on_unpause


def _al_entrar(on_evento, descartar):
    async def _on_join(evento):
        if descartar(evento):
            return
        autor, canal_id = autor_de_evento(evento)
        on_evento(autor, "", TIPO_ENTRADA, "", canal_id)

    return _on_join


def _al_contar_espectadores(on_espectadores, agrupador=None, on_evento=None):
    async def _on_user_seq(evento):
        # El conteo llega seguido: también vacía los me gusta vencidos, para
        # que el último grupo no quede esperando a otro toque.
        if agrupador is not None and on_evento is not None:
            _emitir_vencidos(agrupador, on_evento, time.monotonic())
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
    ("LivePauseEvent", _al_pausa, "estado"),
    ("LiveUnpauseEvent", _al_reanudacion, "estado"),
]


def registrar_manejadores(client, modulo_eventos, *, on_evento,
                          on_espectadores, anunciar_entradas, descartar,
                          on_estado=None):
    """Registra los manejadores de eventos de TikTok en `client`."""
    agrupador = AgrupadorMeGusta()
    clase_comentario = modulo_eventos.CommentEvent
    clase_regalo = modulo_eventos.GiftEvent
    clase_entrada = modulo_eventos.JoinEvent
    clase_conteo = modulo_eventos.RoomUserSeqEvent
    clase_suscripcion = _clase_suscripcion(modulo_eventos)
    client.on(clase_comentario)(_al_comentar(on_evento, descartar))
    client.on(clase_regalo)(_al_regalo(on_evento, descartar))
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
    if anunciar_entradas:
        # Quién entra al directo. Solo si el usuario lo pidió: en directos
        # grandes son constantes y saturarían el TTS.
        client.on(clase_entrada)(_al_entrar(on_evento, descartar))
    client.on(clase_conteo)(_al_contar_espectadores(on_espectadores, agrupador, on_evento))
