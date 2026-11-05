"""La voz de Windows que reemplaza a ElevenLabs cuando la nube no va.

`Respaldo` es dueño de su motor SAPI, de su voz y de sus ajustes. El motor se
crea la primera vez que hace falta, con la fábrica que recibe, y se cierra al
terminar. No crea hilos ni toca wx: el worker le pasa valores y llama métodos.
"""

from __future__ import annotations

from guyrapu.core import diagnostico
from guyrapu.voice import escala_voz
from guyrapu.voice import motores

logger = diagnostico.obtener_logger(__name__)


class Respaldo:
    """Un motor SAPI perezoso con su voz, velocidad, volumen y tono."""

    def __init__(self, fabrica_motor, voz="", velocidad=50, volumen=100,
                 tono=50):
        self._fabrica_motor = fabrica_motor
        self.voz = voz or ""
        self.velocidad = velocidad
        self.volumen = volumen
        self.tono = tono
        self.motor = None

    def conseguir(self, velocidad=None, volumen=None, tono=None):
        """Crea el motor si falta y lo devuelve. None si no se pudo crear.

        Los valores que llegan se guardan y se aplican solo al crear el motor;
        después, los ajustes se cambian con `fijar_ajustes`."""
        if self.motor is not None:
            return self.motor
        if velocidad is not None:
            self.velocidad = velocidad
        if volumen is not None:
            self.volumen = volumen
        if tono is not None:
            self.tono = tono
        motor = self._crear()
        if motor is None:
            return None
        self.motor = motor
        self._aplicar()
        return motor

    def cambiar_voz(self, voz) -> None:
        """Guarda la voz nueva y la aplica si el motor ya existe."""
        nueva = voz or ""
        if nueva == self.voz:
            return
        self.voz = nueva
        if self.motor is not None:
            self._elegir_voz()

    def fijar_ajustes(self, velocidad, volumen, tono) -> None:
        """Guarda velocidad, volumen y tono, y los aplica si hay motor."""
        self.velocidad = velocidad
        self.volumen = volumen
        self.tono = tono
        if self.motor is not None:
            self._aplicar_ajustes()

    def cerrar(self) -> None:
        """Cierra el motor si se creó y olvida la instancia."""
        if self.motor is not None:
            self.motor.cerrar()
            self.motor = None

    def _crear(self):
        try:
            motor = self._fabrica_motor("sapi")
        except motores.MotorNoDisponible as exc:
            logger.warning("No se pudo crear la voz de respaldo (%s).", exc)
            return None
        if not list(motor.voces()):
            motor.cerrar()
            logger.warning("La voz de respaldo no tiene voces instaladas.")
            return None
        return motor

    def _aplicar(self) -> None:
        self._elegir_voz()
        self._aplicar_ajustes()

    def _elegir_voz(self) -> None:
        idx = escala_voz.resolver_voz(self.voz, list(self.motor.voces()))
        self.motor.elegir_voz(0 if idx is None else idx)

    def _aplicar_ajustes(self) -> None:
        self.motor.fijar_velocidad(self.velocidad)
        self.motor.fijar_volumen(self.volumen)
        self.motor.fijar_tono(self.tono)
