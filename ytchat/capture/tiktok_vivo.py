"""Espera a que el directo de TikTok de un usuario sea visible.

Solo lectura, sin conectarse al chat: pregunta si el usuario está en vivo
con `TikTokLiveClient.is_live()`. Nadie lo llama todavía: lo usará la
ventana Transmisión para el destino TikTok vía Restream.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass

from ytchat.capture import tiktok_captura
from ytchat.core import diagnostico

logger = diagnostico.obtener_logger(__name__)

_USUARIO_RE = re.compile(r"[\w.]+", re.UNICODE)


@dataclass(frozen=True)
class ResultadoEspera:
    """Lo que vio `esperar_en_vivo` mientras consultaba.

    `en_vivo` dice si el directo apareció; `cuenta_sin_directos` dice si
    todas las consultas contestaron que la cuenta no tiene directos.
    Se evalúa como `en_vivo` en un `if`, para no romper lo que espera
    un bool.
    """

    en_vivo: bool
    cuenta_sin_directos: bool

    def __bool__(self):
        return bool(self.en_vivo)


def _es_usuario_inexistente(exc) -> bool:
    return type(exc).__name__ == "UserNotFoundError"


def esta_en_vivo(usuario) -> bool:
    """¿El usuario de TikTok está en directo ahora mismo?

    Crea su propio loop de asyncio. Si el usuario no existe lanza
    ValueError; otros errores de red devuelven False y se registran.
    """
    tiktok_captura._parchear_extended_user()
    try:
        from TikTokLive import TikTokLiveClient
    except Exception as exc:
        logger.debug("tiktok en vivo sin librería: %s", exc)
        return False

    async def _consultar():
        return await TikTokLiveClient(unique_id=(usuario or "").lower()).is_live()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return bool(loop.run_until_complete(_consultar()))
    except Exception as exc:
        if _es_usuario_inexistente(exc):
            raise ValueError(
                f"TikTok no tiene directos de la cuenta {usuario}: no "
                "existe, nunca hizo un directo o no tiene permiso para "
                "hacerlos.") from exc
        logger.debug("tiktok en vivo: %s", exc)
        return False
    finally:
        try:
            loop.close()
        except Exception:
            pass


def esperar_en_vivo(usuario, parada=None, cada=5.0, limite=90.0,
                    consultar=esta_en_vivo, dormir=time.sleep,
                    reloj=time.monotonic) -> ResultadoEspera:
    """Consulta hasta ver el directo, agotar el límite o la parada.

    Un ValueError de `consultar` cuenta como "todavía no" y sigue
    esperando: en el primer directo de una cuenta la API contesta
    "user_not_found" hasta que el directo arranca.
    """
    inicio = reloj()
    consultas = 0
    errores = 0
    while True:
        if parada is not None and parada.is_set():
            return ResultadoEspera(
                False, consultas > 0 and errores == consultas)
        try:
            visto = consultar(usuario)
        except ValueError:
            consultas += 1
            errores += 1
            visto = False
        else:
            consultas += 1
            if visto:
                return ResultadoEspera(True, False)
        if reloj() - inicio >= limite:
            return ResultadoEspera(
                False, consultas > 0 and errores == consultas)
        dormir(cada)


def usuario_tiktok(texto) -> str:
    """Usuario sin @ a partir de un handle o una URL de TikTok."""
    texto = (texto or "").strip()
    if not texto:
        return ""
    por_url = tiktok_captura.usuario_de_url(texto)
    if por_url:
        return por_url
    candidato = texto[1:] if texto.startswith("@") else texto
    if candidato and _USUARIO_RE.fullmatch(candidato):
        return candidato.lower()
    return ""


def url_directo(usuario) -> str:
    """URL del directo público de un usuario de TikTok."""
    return f"https://www.tiktok.com/@{usuario}/live"


# Reexportado para que las pruebas y la ventana no rebusquen el módulo.
__all__ = ["ResultadoEspera", "esta_en_vivo", "esperar_en_vivo",
           "usuario_tiktok", "url_directo"]
