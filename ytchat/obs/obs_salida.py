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


# Umbral compartido por los avisos de cuadros: al menos tantos cuadros y
# más de esta proporción con problema.
UMBRAL_CUADROS = 30
UMBRAL_PROPORCION = 0.05


def _porcentaje(diferencia_total, diferencia_perdidos):
    """Porcentaje entero de cuadros con problema, o None si no corresponde.

    Una diferencia negativa (contador reiniciado) o con pocos cuadros no
    avisa. Los dos `outputSkippedFrames` de OBS se llaman igual y son cosas
    distintas: el de GetStreamStatus es pérdida por red y el de GetStats,
    atraso al codificar. Cada uno se compara contra su propia muestra.
    """
    if diferencia_total < UMBRAL_CUADROS or diferencia_perdidos <= 0:
        return None
    proporcion = diferencia_perdidos / diferencia_total
    if proporcion <= UMBRAL_PROPORCION:
        return None
    return int(round(100 * proporcion))


def _diferencia(actual, anterior, clave) -> int:
    try:
        return int(actual.get(clave, 0)) - int(anterior.get(clave, 0))
    except (TypeError, ValueError):
        return 0


_FRASE_RECONEXION = "Se cortó la conexión con el servicio, OBS está reconectando."
_FRASE_VUELTA = "La conexión con el servicio volvió."


def _frase_red(porcentaje) -> str:
    return (f"Se están perdiendo cuadros: {porcentaje} por ciento. "
            "La red va lenta.")


def _frase_sobrecarga(porcentaje) -> str:
    return (f"OBS no da abasto: se pierde el {porcentaje} por ciento "
            "de los cuadros.")


def problemas_en_directo(anterior, actual, estadisticas_anterior=None,
                         estadisticas=None) -> list:
    """Avisos a dar entre dos muestras, cada uno con su tipo y su frase.

    El tipo lo usa el supervisor para no repetir por texto. `red` sale de
    GetStreamStatus; `sobrecarga`, de GetStats, y se salta si falta alguna de
    las dos muestras de estadísticas: es UN aviso con el mayor de los dos
    porcentajes que se calculan, codificación y dibujo. `reconexion` y
    `vuelta` salen del estado de reconexión de OBS.
    """
    anterior = anterior or {}
    actual = actual or {}
    avisos = []
    if bool(actual.get("outputReconnecting")):
        avisos.append(("reconexion", _FRASE_RECONEXION))
    elif bool(anterior.get("outputReconnecting")) and bool(
            actual.get("outputActive")):
        avisos.append(("vuelta", _FRASE_VUELTA))
    else:
        porcentaje = _porcentaje(
            _diferencia(actual, anterior, "outputTotalFrames"),
            _diferencia(actual, anterior, "outputSkippedFrames"))
        if porcentaje is not None:
            avisos.append(("red", _frase_red(porcentaje)))
    if estadisticas is not None and estadisticas_anterior is not None:
        porcentajes = []
        porcentaje = _porcentaje(
            _diferencia(estadisticas, estadisticas_anterior, "outputTotalFrames"),
            _diferencia(estadisticas, estadisticas_anterior, "outputSkippedFrames"))
        if porcentaje is not None:
            porcentajes.append(porcentaje)
        porcentaje = _porcentaje(
            _diferencia(estadisticas, estadisticas_anterior, "renderTotalFrames"),
            _diferencia(estadisticas, estadisticas_anterior, "renderSkippedFrames"))
        if porcentaje is not None:
            porcentajes.append(porcentaje)
        if porcentajes:
            avisos.append(("sobrecarga", _frase_sobrecarga(max(porcentajes))))
    return avisos
