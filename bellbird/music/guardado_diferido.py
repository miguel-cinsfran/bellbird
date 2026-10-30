"""Guardado diferido de lo último pedido, sin wx ni hilos (lógica pura).

Los atajos pueden llegar en ráfaga y no conviene escribir a disco en cada
paso. Cada pedido reemplaza al anterior y reinicia la espera: se ejecuta solo
la última función, un tiempo después del último pedido. `vaciar` ejecuta lo
pendiente en el acto, para no perder el cambio al cerrar.
"""

from __future__ import annotations

from bellbird.core import diagnostico

logger = diagnostico.obtener_logger(__name__)


class GuardadoDiferido:
    """Agrupa pedidos seguidos y ejecuta el último tras la espera."""

    def __init__(self, programar, retardo_ms: int = 1000):
        self._programar = programar
        self._retardo_ms = retardo_ms
        self._pendiente = None
        self._temporizador = None

    def pedir(self, funcion) -> None:
        """Reemplaza lo pendiente y reinicia la espera."""
        self._pendiente = funcion
        self._cancelar()
        self._temporizador = self._programar(self._retardo_ms, self._disparar)

    def vaciar(self) -> None:
        """Ejecuta ya lo pendiente, si hay, y cancela el temporizador."""
        self._cancelar()
        funcion = self._pendiente
        self._pendiente = None
        if funcion is not None:
            funcion()

    def _disparar(self) -> None:
        self._temporizador = None
        funcion = self._pendiente
        self._pendiente = None
        if funcion is not None:
            funcion()

    def _cancelar(self) -> None:
        temporizador = self._temporizador
        self._temporizador = None
        if temporizador is None:
            return
        try:
            temporizador.Stop()
        except Exception as error:
            logger.debug("no se pudo detener el temporizador pendiente: %s", error)
