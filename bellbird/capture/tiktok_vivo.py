"""Espera a que el directo de TikTok de un usuario sea visible.

Solo lectura, sin conectarse al chat: pregunta si el usuario está en vivo
con `TikTokLiveClient.is_live()`. Lo usa el supervisor de la transmisión
para el destino TikTok vía Restream.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass

from bellbird.capture import tiktok_captura
from bellbird.capture.tiktok_errores import ESPERA_LIMITE, es_limite
from bellbird.core import diagnostico
from bellbird.core.idioma import _

logger = diagnostico.obtener_logger(__name__)

_USUARIO_RE = re.compile(r"[\w.]+", re.UNICODE)


class LimiteTikTok(Exception):
    """TikTok frenó las consultas seguidas: hay que esperar y reintentar."""


@dataclass(frozen=True)
class ResultadoEspera:
    """Lo que vio `esperar_en_vivo` mientras consultaba.

    `en_vivo` dice si el directo apareció; `cuenta_sin_directos` dice si
    todas las consultas contestaron que la cuenta no tiene directos;
    `limitado` dice si la última consulta fue un límite y el directo no
    apareció. Se evalúa como `en_vivo` en un `if`, para no romper lo que
    espera un bool.
    """

    en_vivo: bool
    cuenta_sin_directos: bool
    limitado: bool = False

    def __bool__(self):
        return bool(self.en_vivo)


def _es_usuario_inexistente(exc) -> bool:
    return type(exc).__name__ == "UserNotFoundError"


async def _consultar_en_vivo(usuario):
    """`is_live` del usuario, en minúsculas como pide TikTokLive."""
    from TikTokLive import TikTokLiveClient
    return await TikTokLiveClient(unique_id=(usuario or "").lower()).is_live()


def _fallo_en_vivo(exc, usuario):
    """Excepción a lanzar por un fallo de `is_live`, o None si es ruido."""
    if es_limite(exc):
        return LimiteTikTok()
    if _es_usuario_inexistente(exc):
        return ValueError(
            f"TikTok no tiene directos de la cuenta {usuario}: no "
            "existe, nunca hizo un directo o no tiene permiso para "
            "hacerlos.")
    return None


def esta_en_vivo(usuario) -> bool:
    """¿El usuario de TikTok está en directo ahora mismo?

    Crea su propio loop de asyncio. Si el usuario no existe lanza
    ValueError; otros errores de red devuelven False y se registran.
    """
    tiktok_captura._parchear_extended_user()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return bool(loop.run_until_complete(_consultar_en_vivo(usuario)))
    except Exception as exc:
        fallo = _fallo_en_vivo(exc, usuario)
        if fallo is not None:
            raise fallo from exc
        logger.debug("tiktok en vivo: %s", exc)
        return False
    finally:
        try:
            loop.close()
        except Exception as error:
            logger.debug("no se pudo cerrar el bucle: %s", error)


def _clasificar_consulta(consultar, usuario):
    """Una consulta: (visto, limite, error).

    `visto` dice si el directo apareció; `limite` si TikTok frenó la
    consulta; `error` si la cuenta no tiene directos.
    """
    try:
        return (bool(consultar(usuario)), False, False)
    except LimiteTikTok:
        # El límite no cuenta como «no está» ni como «cuenta sin
        # directos»: suma consulta sin sumar error, así una mezcla no
        # marca cuenta sin directos.
        return (False, True, False)
    except ValueError:
        return (False, False, True)


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
    ultimo_limite = False
    while True:
        if parada is not None and parada.is_set():
            return ResultadoEspera(
                False, consultas > 0 and errores == consultas, ultimo_limite)
        visto, es_lim, es_err = _clasificar_consulta(consultar, usuario)
        consultas += 1
        errores += es_err
        ultimo_limite = es_lim
        if visto:
            return ResultadoEspera(True, False)
        if reloj() - inicio >= limite:
            return ResultadoEspera(
                False, consultas > 0 and errores == consultas, ultimo_limite)
        if ultimo_limite:
            dormir(min(ESPERA_LIMITE, max(0.0, limite - (reloj() - inicio))))
        else:
            dormir(cada)


def aviso_espera(resultado, usuario) -> tuple:
    """Frase y sonido cuando el directo no apareció tras esperar.

    El límite manda sobre «cuenta sin directos»: si TikTok frenó las
    consultas, no se sabe si la cuenta tiene directos o no.
    """
    if getattr(resultado, "limitado", False):
        # Traductores: aviso que se anuncia al transmitir a TikTok.
        return (_("OBS está transmitiendo, pero TikTok está limitando las "
                  "consultas y no se pudo comprobar el directo. Vuelve a "
                  "comprobarlo en un minuto."), "tiktok_limitado")
    if getattr(resultado, "cuenta_sin_directos", False):
        # Traductores: aviso que se anuncia al transmitir a TikTok. {usuario} es el usuario de TikTok.
        return (_("OBS está transmitiendo, pero TikTok todavía no muestra "
                  "ningún directo de {usuario}. Revisa que en Restream esté "
                  "activado TikTok.").format(usuario=usuario),
                "transmision_problema")
    # Traductores: aviso que se anuncia al transmitir a TikTok.
    return (_("OBS está transmitiendo, pero TikTok todavía no muestra el directo."),
            "transmision_problema")


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
__all__ = ["LimiteTikTok", "ResultadoEspera", "aviso_espera", "esta_en_vivo",
           "esperar_en_vivo", "usuario_tiktok", "url_directo"]
