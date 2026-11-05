"""Cuándo dos pulsaciones del mismo atajo cuentan como seguidas.

Clase pura y sin wx: recibe el nombre del atajo y el instante de la
pulsación, y devuelve 0 la primera vez y 1 cuando la anterior fue del
mismo atajo y hace menos del intervalo. Después de devolver 1 la cuenta
vuelve a empezar, para que la pulsación siguiente sea otra vez la
primera. Una pulsación de otro atajo corta la racha del anterior.
"""

from __future__ import annotations

INTERVALO_SEGUIDAS = 0.5


class DoblePulsacion:
    """La racha de cada atajo, con el reloj que le pasan.

    Su única razón para cambiar es cuándo dos pulsaciones cuentan como
    seguidas.
    """

    def __init__(self, intervalo: float = INTERVALO_SEGUIDAS):
        self._intervalo = intervalo
        self._atajo = None
        self._momento = 0.0

    def contar(self, atajo: str, ahora: float) -> int:
        """0 si es la primera de la racha, 1 si es la segunda."""
        seguida = (atajo == self._atajo
                   and 0 <= ahora - self._momento < self._intervalo)
        if seguida:
            self._atajo = None
            return 1
        self._atajo = atajo
        self._momento = ahora
        return 0
