"""Diagnóstico del flujo de un directo de TikTok.

Sin wx y sin estado: resume un enlace sin copiar su firma y pide al
servidor los primeros bytes para dejar constancia de lo que contestó.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request

from bellbird.core import diagnostico

logger = diagnostico.obtener_logger(__name__)

BYTES_SONDA = 2048
CABECERA_RANGO = "bytes=0-2047"


def resumen_url(url: str, ahora=None) -> str:
    if not url:
        return ""
    partes = urllib.parse.urlsplit(url)
    resumen = f"servidor={partes.netloc} ruta={partes.path}"
    expire = urllib.parse.parse_qs(partes.query).get("expire")
    if not expire:
        return resumen
    try:
        vencimiento = int(expire[0])
    except (TypeError, ValueError):
        return resumen
    if ahora is None:
        ahora = time.time()
    vence = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(vencimiento))
    quedan = int(vencimiento - float(ahora))
    return f"{resumen} vence={vence} quedan={quedan} s"


def mismo_flujo(url_a: str, url_b: str) -> bool:
    """Si las dos URL traen el mismo flujo: igual servidor y ruta.

    La consulta trae firma y vencimiento nuevos en cada conexión y no
    cuenta. Con una de las dos vacía, falso."""
    if not url_a or not url_b:
        return False
    a = urllib.parse.urlsplit(url_a)
    b = urllib.parse.urlsplit(url_b)
    return (a.netloc, a.path) == (b.netloc, b.path)


def sondear(url: str, abrir=None, plazo_s: float = 5) -> str:
    if abrir is None:
        abrir = urllib.request.urlopen
    peticion = urllib.request.Request(url, headers={"Range": CABECERA_RANGO})
    respuesta = None
    try:
        respuesta = abrir(peticion, timeout=plazo_s)
        return _resumen_http(respuesta, respuesta.read(BYTES_SONDA) or b"")
    except urllib.error.HTTPError as exc:
        return _resumen_http(exc, _leer_cuerpo(exc))
    except Exception as exc:
        return f"error={type(exc).__name__}: {exc}"
    finally:
        _cerrar(respuesta)


def sondear_en_hilo(url: str) -> None:
    def trabajo():
        resultado = sondear(url)
        logger.warning("TIKTOK_FLUJO_SONDA %s %s", resumen_url(url), resultado)

    hilo = diagnostico.crear_hilo(trabajo, "tiktok-sonda")
    hilo.start()


def _resumen_http(respuesta, cuerpo: bytes) -> str:
    codigo = (getattr(respuesta, "status", None)
              or getattr(respuesta, "code", None) or 0)
    return f"http={codigo} tipo={_tipo_contenido(respuesta)} bytes={len(cuerpo)}"


def _tipo_contenido(respuesta) -> str:
    cabeceras = getattr(respuesta, "headers", None)
    if cabeceras is None:
        return "desconocido"
    try:
        tipo = cabeceras.get("Content-Type")
    except Exception as exc:
        logger.debug("cabeceras del flujo de TikTok: %s", exc)
        tipo = None
    return tipo or "desconocido"


def _leer_cuerpo(respuesta) -> bytes:
    try:
        return respuesta.read(BYTES_SONDA) or b""
    except Exception as exc:
        logger.debug("cuerpo del error del flujo de TikTok: %s", exc)
        return b""


def _cerrar(respuesta) -> None:
    if respuesta is None:
        return
    try:
        respuesta.close()
    except Exception as exc:
        logger.debug("cerrar la respuesta del flujo de TikTok: %s", exc)
