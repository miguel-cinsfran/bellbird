"""Vigilancia de la salida de OBS: confirmar que manda datos.

Puro salvo `esperar_salida`, que muestrea `GetStreamStatus` con un cliente
con `pedir(tipo, datos=None, parada=None)` como `obs_destinos`. Nadie lo
llama todavía: lo usará la ventana Transmisión.
"""

from __future__ import annotations

import time


def evaluar_inicio(muestras) -> str:
    """Veredicto sobre una lista de dicts de `GetStreamStatus`.

    "enviando" si `outputActive` y `outputBytes` creció entre dos muestras
    seguidas; "reconectando" si la última tiene `outputReconnecting`;
    "sin_salida" si ninguna tiene `outputActive`; "esperando" en otro caso.
    """
    muestras = list(muestras or [])
    for previa, actual in zip(muestras, muestras[1:]):
        try:
            if actual.get("outputActive") and float(
                    actual.get("outputBytes", 0)) > float(
                    previa.get("outputBytes", 0)):
                return "enviando"
        except (TypeError, ValueError):
            continue
    if muestras and bool(muestras[-1].get("outputReconnecting")):
        return "reconectando"
    if not any(bool(muestra.get("outputActive")) for muestra in muestras):
        return "sin_salida"
    return "esperando"


def esperar_salida(cliente, parada=None, limite=20.0, intervalo=1.0,
                   dormir=time.sleep, reloj=time.monotonic) -> str:
    """Muestrea hasta que OBS confirma que envía o se agota el límite."""
    inicio = reloj()
    muestras = []
    veredicto = "sin_salida"
    while True:
        if parada is not None and parada.is_set():
            return veredicto
        respuesta = cliente.pedir("GetStreamStatus", parada=parada)
        datos = respuesta.get("responseData", {}) or {}
        muestras.append(dict(datos))
        veredicto = evaluar_inicio(muestras)
        if veredicto == "enviando":
            return veredicto
        if reloj() - inicio >= limite:
            return veredicto
        dormir(intervalo)


def frase_salida(veredicto, destino) -> str:
    """Frase audible para el veredicto de la salida."""
    servicio = {"TikTok": "Restream", "YouTube": "YouTube"}.get(destino,
                                                                 destino)
    if veredicto == "enviando":
        return f"OBS está enviando la señal a {servicio}."
    if veredicto == "reconectando":
        return (f"OBS no logra conectar con {servicio} y está reintentando. "
                "Revisa internet.")
    if veredicto == "sin_salida":
        return "OBS no empezó a transmitir."
    return "OBS todavía no confirma que la señal salga."


def problema_en_directo(anterior, actual) -> str | None:
    """¿Pasó algo malo entre dos muestras de `GetStreamStatus`?

    `outputCongestion` no se usa: no siempre existe.
    """
    anterior = anterior or {}
    actual = actual or {}
    if bool(actual.get("outputReconnecting")):
        return "Se cortó la conexión con el servicio, OBS está reconectando."
    try:
        diferencia_total = int(actual.get("outputTotalFrames", 0)) - int(
            anterior.get("outputTotalFrames", 0))
        diferencia_perdidos = int(actual.get("outputSkippedFrames", 0)) - int(
            anterior.get("outputSkippedFrames", 0))
    except (TypeError, ValueError):
        return None
    if (diferencia_total >= 30 and diferencia_perdidos > 0
            and diferencia_perdidos / diferencia_total > 0.05):
        porcentaje = int(round(100 * diferencia_perdidos / diferencia_total))
        return (f"Se están perdiendo cuadros: {porcentaje} por ciento. "
                "La red va lenta.")
    return None
