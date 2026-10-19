"""Modelo de datos del reproductor de música, sin texto para el usuario."""

from __future__ import annotations

from dataclasses import dataclass


OK = "ok"
COLA_VACIA = "cola_vacia"
SIN_TEMA = "sin_tema"
FIN_LISTA = "fin_lista"
INICIO_LISTA = "inicio_lista"
VOLUMEN_INVALIDO = "volumen_invalido"
ERROR_MOTOR = "error_motor"
TEMA_FALLIDO = "tema_fallido"
AVANZO = "avanzo"
REINICIADO = "reiniciado"


@dataclass(frozen=True)
class Tema:
    """Un tema de la biblioteca local o, a futuro, de una dirección web."""

    origen: str
    titulo: str
    artista: str = ""
    album: str = ""

    @property
    def es_enlace(self) -> bool:
        """True si el origen es una dirección web http o https."""
        return self.origen.lower().startswith(("http://", "https://"))


@dataclass(frozen=True)
class EstadoMusica:
    """Fotografía inmutable del estado del reproductor."""

    cola: tuple[Tema, ...]
    posicion: int | None
    pausado: bool
    terminado: bool
    volumen: int
    aleatorio: bool
    repetir: str = "no"

    @property
    def actual(self) -> Tema | None:
        """El tema que ocupa la posición actual, o None si no hay ninguno."""
        if self.posicion is None:
            return None
        return self.cola[self.posicion]


@dataclass(frozen=True)
class Resultado:
    """Resultado de una operación del coordinador."""

    ok: bool
    codigo: str
    estado: EstadoMusica
    tema: Tema | None = None
