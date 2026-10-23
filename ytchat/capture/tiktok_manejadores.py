"""Traducción de eventos de TikTok a eventos de la aplicación.

Cambia solo cuando cambia qué eventos escucha la aplicación o cómo los
traduce; la conexión y la reconexión viven en tiktok_captura.
"""

from __future__ import annotations

import time

from ytchat.capture.tiktok_captura import (
    _clase_suscripcion,
    autor_de_evento,
    debe_pasar_me_gusta,
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


def _al_me_gusta(on_evento, descartar, ultimo_me_gusta):
    async def _on_like(evento):
        if descartar(evento):
            return
        ahora = time.monotonic()
        if not debe_pasar_me_gusta(ultimo_me_gusta[0], ahora):
            return
        ultimo_me_gusta[0] = ahora
        autor, canal_id = autor_de_evento(evento)
        on_evento(autor, "", TIPO_ME_GUSTA, "", canal_id)

    return _on_like


def _al_entrar(on_evento, descartar):
    async def _on_join(evento):
        if descartar(evento):
            return
        autor, canal_id = autor_de_evento(evento)
        on_evento(autor, "", TIPO_ENTRADA, "", canal_id)

    return _on_join


def _al_contar_espectadores(on_espectadores):
    async def _on_user_seq(evento):
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


def registrar_manejadores(client, modulo_eventos, *, on_evento,
                          on_espectadores, anunciar_entradas, descartar):
    """Registra los manejadores de eventos de TikTok en `client`."""
    ultimo_me_gusta = [None]
    clase_comentario = modulo_eventos.CommentEvent
    clase_regalo = modulo_eventos.GiftEvent
    clase_entrada = modulo_eventos.JoinEvent
    clase_conteo = modulo_eventos.RoomUserSeqEvent
    clase_suscripcion = _clase_suscripcion(modulo_eventos)
    # Seguir, compartir, cofre y me gusta existen en la TikTokLive instalada;
    # si en otra versión falta alguna clase, ese manejador no se registra.
    clase_seguir = getattr(modulo_eventos, "FollowEvent", None)
    clase_compartir = getattr(modulo_eventos, "ShareEvent", None)
    clase_cofre = getattr(modulo_eventos, "EnvelopeEvent", None)
    clase_me_gusta = getattr(modulo_eventos, "LikeEvent", None)
    client.on(clase_comentario)(_al_comentar(on_evento, descartar))
    client.on(clase_regalo)(_al_regalo(on_evento, descartar))
    if clase_suscripcion is not None:
        client.on(clase_suscripcion)(_al_suscribir(on_evento, descartar))
    if clase_seguir is not None:
        client.on(clase_seguir)(_al_seguir(on_evento, descartar))
    if clase_compartir is not None:
        client.on(clase_compartir)(_al_compartir(on_evento, descartar))
    if clase_cofre is not None:
        client.on(clase_cofre)(_al_cofre(on_evento, descartar))
    if clase_me_gusta is not None:
        # Los me gusta llegan de a montones: como mucho UNO cada 3 s por
        # sesión, para no saturar el sonido (ver debe_pasar_me_gusta).
        client.on(clase_me_gusta)(
            _al_me_gusta(on_evento, descartar, ultimo_me_gusta))
    if anunciar_entradas:
        # Quién entra al directo. Solo si el usuario lo pidió: en directos
        # grandes son constantes y saturarían el TTS.
        client.on(clase_entrada)(_al_entrar(on_evento, descartar))
    client.on(clase_conteo)(_al_contar_espectadores(on_espectadores))
