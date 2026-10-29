"""Envío real de pedidos de IA por httpx, sin reintentos.

Lo llama un hilo, no el de la interfaz. Sin HTTP/2: hay un defecto
conocido de httpx con h2, comentado en `main.py:552`.
"""

import httpx

from bellbird.ai import protocolos


def _publicar(cliente, pedido, clave, tiempo_espera):
    try:
        respuesta = cliente.post(
            pedido.url, headers=pedido.cabeceras, json=pedido.cuerpo,
            timeout=tiempo_espera)
    except httpx.TimeoutException as error:
        raise protocolos.ErrorIA(
            protocolos.TIEMPO_AGOTADO, str(error)[:300]) from error
    except httpx.TransportError as error:
        raise protocolos.ErrorIA(
            protocolos.SIN_RED, str(error)[:300]) from error
    try:
        return protocolos.leer_respuesta(
            pedido.protocolo, respuesta.status_code, respuesta.text)
    except protocolos.ErrorIA as error:
        if clave and error.detalle and clave in error.detalle:
            error.detalle = error.detalle.replace(clave, "<clave>")
            error.args = (f"{error.tipo}: {error.detalle}",)
        raise


def enviar(pedido, clave, tiempo_espera, cliente=None):
    if cliente is None:
        with httpx.Client() as propio:
            return _publicar(propio, pedido, clave, tiempo_espera)
    return _publicar(cliente, pedido, clave, tiempo_espera)
