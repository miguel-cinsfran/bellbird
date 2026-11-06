"""Pila de cambios de una fuente de OBS para deshacer de a uno.

Guarda la misma instantánea que el restablecimiento general y la reaplica
con el mismo código. Vive mientras el panel de OBS está abierto.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from guyrapu.obs import restablecimiento


_RESTAURADOR = restablecimiento.RegistroRestablecimiento()


@dataclass(frozen=True)
class Cambio:
    escena: str
    fuente: str
    accion: str
    datos: dict


class PilaDeshacer:
    """Los cambios hechos desde el panel, del más viejo al más nuevo."""

    def __init__(self):
        self._cambios = []

    @property
    def vacia(self) -> bool:
        return not self._cambios

    def guardar(self, gestor, escena, fuente, accion) -> None:
        if not fuente:
            return
        self._cambios.append(Cambio(
            escena=escena, fuente=fuente, accion=accion,
            datos=restablecimiento._instantanea(gestor, escena, fuente)))

    def deshacer(self, gestor):
        """Reaplica el último cambio y lo saca. Si OBS falla, lo conserva."""
        if not self._cambios:
            return None
        cambio = self._cambios[-1]
        _RESTAURADOR._restaurar_forma(
            gestor, cambio.escena, cambio.fuente, cambio.datos)
        if cambio.datos["capa"] is not None:
            gestor.mover_capa(
                cambio.escena, cambio.datos["capa"], fuente=cambio.fuente)
        self._cambios.pop()
        return cambio

    def descartar(self) -> None:
        if self._cambios:
            self._cambios.pop()

    def cambiar_nombre(self, antes, nuevo) -> None:
        """El nombre de una fuente es global: se corrige en toda la pila."""
        self._cambios = [
            replace(cambio, fuente=nuevo) if cambio.fuente == antes else cambio
            for cambio in self._cambios]

    def olvidar(self, escena, fuente) -> None:
        """Saca lo que ya no se puede deshacer en esa escena."""
        self._cambios = [
            cambio for cambio in self._cambios
            if (cambio.escena, cambio.fuente) != (escena, fuente)]
