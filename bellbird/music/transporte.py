"""Silencio y saltos sobre el tema que está sonando."""

from __future__ import annotations

from dataclasses import dataclass

from bellbird.music.modelo import (
    ERROR_MOTOR, OK, SIN_TEMA, EstadoMusica, Resultado, Tema,
)


PASO_VOLUMEN = 10
VOLUMEN_MIN = 0
VOLUMEN_MAX = 100
VOLUMEN_INICIAL = 50

def nuevo_volumen(actual, paso, minimo=VOLUMEN_MIN, maximo=VOLUMEN_MAX) -> int:
    """Volumen nuevo tras sumar un paso, recortado a sus límites. Función pura."""
    try:
        base = int(actual)
    except (TypeError, ValueError):
        base = minimo
    return max(minimo, min(maximo, base + paso))


def toca_pausar(estado) -> bool:
    """¿«Reproducir o pausar» pausa o reanuda en vez de empezar una lista?

    Sí si el coordinador ya tiene un tema cargado y no terminó. Función pura.
    """
    return bool(estado is not None and estado.actual is not None and not estado.terminado)


@dataclass(frozen=True)
class ResultadoSalto:
    """Resultado de un salto, con la posición nueva para el anuncio."""

    ok: bool
    codigo: str
    estado: EstadoMusica
    posicion_ms: int | None = None
    tema: Tema | None = None


class TransporteMusica:
    """Silencio y saltos del coordinador, compartidos con la interfaz."""

    def fijar_silencio(self, activo: bool) -> Resultado:
        """Silencia o devuelve el sonido sin cambiar el volumen guardado."""
        with self._lock:
            nuevo = bool(activo)
            try:
                self._adaptador.volumen(0 if nuevo else self._volumen)
            except Exception:
                return Resultado(False, ERROR_MOTOR, self._estado())
            self._silenciado = nuevo
            return Resultado(True, OK, self._estado())

    @property
    def silenciado(self) -> bool:
        """Si la música está silenciada por el atajo o el menú."""
        return bool(getattr(self, "_silenciado", False))

    def saltar(self, delta_ms: int) -> ResultadoSalto:
        """Mueve la posición del tema actual, sin salir de su duración."""
        with self._lock:
            if self._posicion is None or self._terminado:
                return ResultadoSalto(False, SIN_TEMA, self._estado())
            tiempo = self._tiempo_actual()
            if tiempo is None:
                return ResultadoSalto(False, SIN_TEMA, self._estado())
            destino = max(0, tiempo + delta_ms)
            duracion = self._cola[self._posicion].duracion_ms
            if duracion > 0:
                destino = min(destino, max(0, duracion - 1000))
            try:
                self._adaptador.ir_a(destino)
            except Exception:
                return ResultadoSalto(False, ERROR_MOTOR, self._estado())
            return ResultadoSalto(True, OK, self._estado(), destino)
