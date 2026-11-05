"""Las frases de la pestaña General del panel de OBS, sin wx.

Su única razón para cambiar es cómo se cuenta el perfil y el rendimiento del
equipo a partir de `GetStats`.
"""

from __future__ import annotations

from guyrapu.core.idioma import _
from guyrapu.music.pregunta_igualar import texto_tamano

_BYTES_POR_MB = 1024 * 1024


def _entero(valor):
    try:
        return int(round(float(valor)))
    except (TypeError, ValueError):
        return None


def lineas(perfil, estadisticas) -> list[str]:
    """Las frases de General, una por línea y en el orden del diseño.

    Si falta un dato, su línea no se escribe.
    """
    estadisticas = estadisticas or {}
    resultado = []
    if perfil:
        resultado.append(_("Conectado con OBS. Perfil: {perfil}.").format(
            perfil=perfil))
    cpu = _entero(estadisticas.get("cpuUsage"))
    if cpu is not None:
        resultado.append(_("Uso de CPU: {porcentaje} %.").format(
            porcentaje=cpu))
    omitidos = _entero(estadisticas.get("outputSkippedFrames"))
    totales = _entero(estadisticas.get("outputTotalFrames"))
    if omitidos is not None and totales is not None:
        resultado.append(_(
            "Fotogramas omitidos por retraso en la codificación: "
            "{n} de {total}.").format(n=omitidos, total=totales))
    perdidos = _entero(estadisticas.get("renderSkippedFrames"))
    totales_render = _entero(estadisticas.get("renderTotalFrames"))
    if perdidos is not None and totales_render is not None:
        resultado.append(_(
            "Fotogramas perdidos por retraso de procesamiento: "
            "{n} de {total}.").format(n=perdidos, total=totales_render))
    espacio = _entero(estadisticas.get("availableDiskSpace"))
    if espacio is not None:
        resultado.append(_("Espacio en disco disponible: {tamano}.").format(
            tamano=texto_tamano(espacio * _BYTES_POR_MB)))
    return resultado


def resumen(estado, perfil, estadisticas) -> list[str]:
    """El estado de General completo, sin repetir ningún dato.

    Primero el titular de la transmisión, después sus líneas y al final el
    perfil y el rendimiento del equipo.
    """
    resultado = []
    for linea in (estado.titular, *estado.lineas,
                  *lineas(perfil, estadisticas)):
        if linea and linea not in resultado:
            resultado.append(linea)
    return resultado
