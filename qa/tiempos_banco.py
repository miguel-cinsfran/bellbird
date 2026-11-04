"""Resumen de los tiempos de una corrida del banco de QA.

Recibe las anotaciones de las órdenes y la duración de cada escenario, y
devuelve las líneas de la sección TIEMPOS. No toca ventanas ni la aplicación.
"""

from __future__ import annotations


def _cubierto(intervalos) -> float:
    """Segundos que suman los intervalos, sin contar dos veces los solapados."""
    total = 0.0
    inicio = fin = None
    for desde, hasta in sorted(intervalos):
        if fin is None or desde > fin:
            if fin is not None:
                total += fin - inicio
            inicio, fin = desde, hasta
        else:
            fin = max(fin, hasta)
    if fin is not None:
        total += fin - inicio
    return total


def _sin_medir(anotaciones, escenario: str, segundos: float) -> float:
    """Lo que la duración no cubren las anotaciones de ese escenario."""
    intervalos = [(a["inicio"], a["inicio"] + a["segundos"])
                  for a in anotaciones
                  if a["escenario"] == escenario and "inicio" in a]
    return max(0.0, segundos - _cubierto(intervalos))


def lineas_tiempos(anotaciones, duraciones, cuantos: int = 10) -> list[str]:
    """Las líneas de la sección TIEMPOS de una corrida.

    `anotaciones` trae diccionarios con escenario, orden, segundos e inicio,
    y un tipo opcional: orden, uia o tab. `duraciones` trae pares
    (escenario, segundos) en el orden en que corrieron.
    """
    lineas = ["TIEMPOS"]
    ordenadas = sorted(anotaciones, key=lambda a: a["segundos"], reverse=True)

    lineas.append("  Pasos más lentos:")
    if not ordenadas:
        lineas.append("    (sin órdenes anotadas)")
    for puesto, anotacion in enumerate(ordenadas[:cuantos], 1):
        lineas.append("    %d. %s, %s [%s]: %.3f s"
                      % (puesto, anotacion["escenario"],
                         anotacion["orden"], anotacion.get("tipo", "orden"),
                         anotacion["segundos"]))

    lineas.append("  Duración de cada escenario:")
    if not duraciones:
        lineas.append("    (sin escenarios)")
    for escenario, segundos in duraciones:
        lineas.append("    %s: %.3f s, sin medir %.1f s"
                      % (escenario, segundos,
                         _sin_medir(anotaciones, escenario, segundos)))
    return lineas
