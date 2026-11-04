"""Resumen de los tiempos de una corrida del banco de QA.

Recibe las anotaciones de las órdenes y la duración de cada escenario, y
devuelve las líneas de la sección TIEMPOS. No toca ventanas ni la aplicación.
"""

from __future__ import annotations


def lineas_tiempos(anotaciones, duraciones, cuantos: int = 10) -> list[str]:
    """Las líneas de la sección TIEMPOS de una corrida.

    `anotaciones` trae diccionarios con escenario, orden y segundos.
    `duraciones` trae pares (escenario, segundos) en el orden en que corrieron.
    """
    lineas = ["TIEMPOS"]
    ordenadas = sorted(anotaciones, key=lambda a: a["segundos"], reverse=True)

    lineas.append("  Pasos más lentos:")
    if not ordenadas:
        lineas.append("    (sin órdenes anotadas)")
    for puesto, anotacion in enumerate(ordenadas[:cuantos], 1):
        lineas.append("    %d. %s, %s: %.3f s"
                      % (puesto, anotacion["escenario"],
                         anotacion["orden"], anotacion["segundos"]))

    lineas.append("  Duración de cada escenario:")
    if not duraciones:
        lineas.append("    (sin escenarios)")
    for escenario, segundos in duraciones:
        lineas.append("    %s: %.3f s" % (escenario, segundos))
    return lineas
