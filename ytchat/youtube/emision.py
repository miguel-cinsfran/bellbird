"""Emisión de YouTube: cuerpo del directo y paso que lo deja listo.

Puro salvo lo inyectado: el cliente de YouTube y el de OBS entran por
parámetro, así se prueba con dobles sin tocar la API real.
"""

from __future__ import annotations

import time
from datetime import datetime

from ytchat.core import diagnostico
from ytchat.obs import obs_cliente
from ytchat.obs import obs_destinos
from ytchat.youtube import youtube_api

logger = diagnostico.obtener_logger(__name__)

PRIVACIDADES = ("public", "unlisted", "private")
ETIQUETAS_PRIVACIDAD = {"public": "Público", "unlisted": "No listado",
                        "private": "Privado"}
PRIVACIDAD_INICIAL = "unlisted"


class EmisionError(Exception):
    """Fallo listo para anunciar tal cual."""


def cuerpo_emision(titulo, descripcion, privacidad, inicio_iso) -> dict:
    """Arma el cuerpo de liveBroadcasts.insert para el directo."""
    titulo = (titulo or "").strip()
    if not titulo:
        raise EmisionError("Falta el título del directo.")
    titulo = titulo[:100]
    descripcion = (descripcion or "").strip()[:5000]
    if privacidad not in PRIVACIDADES:
        raise ValueError(f"Privacidad inválida: {privacidad}.")
    return {"snippet": {"title": titulo, "description": descripcion,
                        "scheduledStartTime": inicio_iso},
            "status": {"privacyStatus": privacidad,
                       "selfDeclaredMadeForKids": False},
            "contentDetails": {"enableAutoStart": True,
                               "enableAutoStop": True}}


def titulo_por_defecto(ahora: datetime) -> str:
    """Título con la fecha del día para el directo."""
    return f"Directo del {ahora:%d/%m/%Y}"


def url_video(id_video: str) -> str:
    """URL pública del vídeo a partir de su id."""
    return "https://www.youtube.com/watch?v=" + id_video


def preparar_en_youtube(cliente_yt, cliente_obs, cuerpo, parada=None,
                        preparar_destino=obs_destinos.preparar_destino,
                        guardar_token=None) -> str:
    """Crea la emisión, la vincula y carga servidor y clave en OBS.

    Devuelve el id del vídeo. Si vincular o preparar fallan, borra la
    emisión para no dejar directos huérfanos y relanza el error original.
    """
    try:
        flujo = cliente_yt.flujo_reutilizable()
        if flujo is None:
            raise EmisionError(
                "La cuenta de YouTube no tiene una clave de emisión "
                "reutilizable. Se crea en YouTube Studio, en Emitir en "
                "directo.")
        id_flujo, servidor, clave = flujo
        id_video = cliente_yt.crear_emision(cuerpo)
        try:
            cliente_yt.vincular_emision(id_video, id_flujo)
            preparar_destino(
                cliente_obs, obs_destinos.Destino("YouTube", servidor, clave),
                parada=parada)
        except Exception:
            try:
                cliente_yt.borrar_emision(id_video)
            except Exception as fallo_borrado:
                logger.debug("no se pudo borrar la emisión %s: %s",
                             id_video, fallo_borrado)
            raise
        return id_video
    except EmisionError:
        raise
    except obs_cliente.ObsError:
        raise
    except Exception as exc:
        raise EmisionError(
            youtube_api.mensaje_error_api(exc)) from exc
    finally:
        if guardar_token is not None:
            try:
                nuevo = cliente_yt.token_actualizado()
            except Exception:
                nuevo = None
            if nuevo:
                guardar_token(nuevo)


def ganchos_youtube(cliente_yt, cuerpo, guardar_token):
    """Devuelve (preparar_emision, esperar_emision) para el supervisor.

    Adapta `preparar_en_youtube` y `esperar_en_vivo` a las firmas que
    espera `SupervisorTransmision`, con el cliente y el cuerpo ya fijos.
    """
    def preparar_emision(cliente_obs, parada):
        return preparar_en_youtube(
            cliente_yt, cliente_obs, cuerpo, parada=parada,
            guardar_token=guardar_token)

    def esperar_emision(id_video, parada, limite=120.0):
        return esperar_en_vivo(
            cliente_yt.estado_emision, id_video, parada, limite=limite)

    return preparar_emision, esperar_emision


def esperar_en_vivo(consultar_estado, id_video, parada=None, cada=5.0,
                    limite=120.0, dormir=time.sleep,
                    reloj=time.monotonic) -> bool:
    """Consulta el estado hasta ver "live", agotar el límite o la parada."""
    inicio = reloj()
    while True:
        if parada is not None and parada.is_set():
            return False
        try:
            estado = consultar_estado(id_video)
        except Exception:
            estado = ""
        if estado == "live":
            return True
        if reloj() - inicio >= limite:
            return False
        dormir(cada)
