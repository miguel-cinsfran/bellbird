"""Sesión de Restream: guarda los tokens y decide cuándo renovarlos.

Puro salvo lo inyectado: la carga, el guardado, la renovación y el reloj
entran por parámetro, así se prueba sin red y sin tocar disco. El renovador
lanza `RechazoDeConcesion` cuando Restream responde `invalid_grant`; cualquier
otra excepción cuenta como fallo de red.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from bellbird.core.idioma import _

# Margen con el que se renueva antes de que el token venza.
MARGEN_RENOVACION = 300.0
# Con menos de este margen, un fallo de red ya no deja usar el token viejo.
MARGEN_SIN_RED = 15.0
# Vigencia que se asume cuando la respuesta no trae vencimiento.
VIGENCIA_POR_DEFECTO = 3600.0


@dataclass(frozen=True, slots=True)
class Tokens:
    """Par de tokens de Restream con su vencimiento en epoch y sus permisos."""

    acceso: str = field(repr=False)
    renovacion: str = field(repr=False)
    vence: float
    permisos: str = ""

    def a_dict(self) -> dict:
        return {
            "acceso": self.acceso,
            "renovacion": self.renovacion,
            "vence": self.vence,
            "permisos": self.permisos,
        }

    @classmethod
    def desde_dict(cls, datos):
        """Devuelve los tokens guardados, o None si faltan datos esenciales."""
        if not isinstance(datos, dict):
            return None
        acceso = datos.get("acceso")
        vence = datos.get("vence")
        if not acceso or vence is None:
            return None
        try:
            vence = float(vence)
        except (TypeError, ValueError):
            return None
        return cls(
            acceso=str(acceso),
            renovacion=str(datos.get("renovacion") or ""),
            vence=vence,
            permisos=str(datos.get("permisos") or ""),
        )


def _numero(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def tokens_de_respuesta(datos, ahora):
    """Interpreta la respuesta JSON del servidor de tokens de Restream."""
    if not isinstance(datos, dict):
        datos = {}
    acceso = datos.get("access_token") or datos.get("accessToken")
    if not acceso:
        raise ValueError(
            _("La respuesta del servidor de tokens no trajo un token de acceso."))
    renovacion = datos.get("refresh_token") or datos.get("refreshToken") or ""
    permisos = datos.get("scope") or ""

    vence = _numero(datos.get("accessTokenExpiresEpoch"))
    if not vence or vence <= 0:
        segundos = _numero(datos.get("expires_in"))
        if not segundos or segundos <= 0:
            segundos = _numero(datos.get("accessTokenExpiresIn"))
        if not segundos or segundos <= 0:
            segundos = VIGENCIA_POR_DEFECTO
        vence = float(ahora) + segundos

    return Tokens(str(acceso), str(renovacion), float(vence), str(permisos))


class SesionVencida(Exception):
    """Restream rechazó la concesión: hay que volver a conectar la cuenta."""

    def __init__(self):
        super().__init__(
            _("La sesión de Restream venció. Vuelve a conectar la cuenta."))


class SinRed(Exception):
    """No se pudo renovar y al token ya no le queda margen para seguir."""

    def __init__(self):
        super().__init__(
            _("No se pudo renovar la sesión de Restream. Comprueba la conexión a internet."))


class RechazoDeConcesion(Exception):
    """El renovador la lanza cuando Restream responde `invalid_grant`."""


class Sesion:
    """Tokens guardados de Restream, con renovación segura entre hilos."""

    def __init__(self, cargar, guardar, renovar, reloj=time.time):
        self._guardar = guardar
        self._renovar = renovar
        self._reloj = reloj
        self._candado = threading.Lock()
        self._tokens = Tokens.desde_dict(cargar())

    def conectada(self) -> bool:
        return self._tokens is not None

    def establecer(self, tokens) -> None:
        """Guarda el par recién canjeado, por ejemplo al conectar la cuenta."""
        with self._candado:
            self._tokens = tokens
            self._guardar(tokens.a_dict())

    def borrar(self) -> None:
        with self._candado:
            self._olvidar()

    def _olvidar(self) -> None:
        self._tokens = None
        self._guardar(None)

    def token(self) -> str:
        """Devuelve el token de acceso vigente, renovándolo si hace falta."""
        with self._candado:
            if self._tokens is None:
                raise SesionVencida()

            ahora = self._reloj()
            if self._tokens.vence - ahora > MARGEN_RENOVACION:
                return self._tokens.acceso

            if not self._tokens.renovacion:
                if self._tokens.vence <= ahora:
                    self._olvidar()
                    raise SesionVencida()
                return self._tokens.acceso

            try:
                respuesta = self._renovar(self._tokens.renovacion)
            except RechazoDeConcesion:
                self._olvidar()
                raise SesionVencida() from None
            except Exception:
                ahora = self._reloj()
                if self._tokens.vence - ahora > MARGEN_SIN_RED:
                    return self._tokens.acceso
                raise SinRed() from None

            nuevos = tokens_de_respuesta(respuesta, self._reloj())
            self._tokens = nuevos
            self._guardar(nuevos.a_dict())
            return nuevos.acceso
