"""Envoltorio de Prism para hablar con los motores de voz de Windows.

Prism unifica SAPI 5 y OneCore bajo una misma API. Este módulo aísla a la
aplicación de esa API: crea el motor pedido, traduce los porcentajes de la
app con `escala_voz` y no deja salir ningún error después del constructor.
Cambiar de motor o elegir mal una voz no debe tumbar el hilo de voz.
"""

from __future__ import annotations

from ytchat.core import diagnostico
from ytchat.voice import escala_voz

logger = diagnostico.obtener_logger(__name__)

MOTORES = ("sapi", "onecore", "elevenlabs")
NOMBRES = {
    "sapi": "Windows SAPI 5",
    "onecore": "Windows OneCore",
    "elevenlabs": "ElevenLabs, en la nube",
}

# Solo los motores de Prism tienen backend id. ElevenLabs tiene su propio
# MotorElevenLabs, así que la validación de `MotorPrism` va contra `_IDS` y no
# contra `MOTORES`: pedir «elevenlabs» desde Prism debe dar MotorNoDisponible.
_IDS = {"sapi": "SAPI", "onecore": "ONE_CORE"}


class MotorNoDisponible(Exception):
    """El motor pedido no se puede crear en esta máquina."""


class MotorPrism:
    """Un motor de Prism con la interfaz que usa la aplicación.

    NO es seguro entre hilos: la regla de Prism es que un backend lo crea y lo
    usa un solo hilo. La interfaz debe crear su propia instancia (por ejemplo
    con `listar_voces`) para no tocar la del hilo de voz.
    """

    def __init__(self, motor, fabrica_contexto=None):
        if motor not in _IDS:
            raise MotorNoDisponible(
                f"Motor de voz desconocido: {motor!r} "
                f"(válidos: {', '.join(_IDS)})")
        try:
            from prism import BackendId
            from prism.common import (
                PrismAlreadyPausedError,
                PrismNotPausedError,
            )
            # Importación perezosa: Prism puede no estar instalado y eso debe
            # llegar como MotorNoDisponible, no como ImportError al importar
            # este módulo.
            if fabrica_contexto is None:
                from prism import Context as fabrica_contexto
        except Exception as exc:
            raise MotorNoDisponible(
                f"No se pudo importar Prism para el motor "
                f"{NOMBRES[motor]}: {exc}") from exc
        try:
            self._ctx = fabrica_contexto()
            self._backend = self._ctx.create(getattr(BackendId, _IDS[motor]))
        except Exception as exc:
            raise MotorNoDisponible(
                f"No se pudo iniciar el motor {NOMBRES[motor]}: {exc}") from exc
        self._ya_pausado = PrismAlreadyPausedError
        self._no_pausado = PrismNotPausedError
        self.motor = motor
        self._cerrado = False

    def _vivo(self) -> bool:
        return not self._cerrado and getattr(self, "_backend", None) is not None

    def voces(self) -> list[str]:
        """Refresca y devuelve los nombres de las voces del motor."""
        if not self._vivo():
            return []
        try:
            self._backend.refresh_voices()
            return [self._backend.get_voice_name(i)
                    for i in range(self._backend.voices_count)]
        except Exception as exc:
            logger.warning("Listar voces de %s: %s", self.motor, exc)
            return []

    def elegir_voz(self, idx) -> bool:
        """Cambia la voz activa. False si el índice está fuera de rango o falla."""
        if not self._vivo():
            return False
        try:
            idx = int(idx)
            if not 0 <= idx < self._backend.voices_count:
                return False
            self._backend.voice = idx
            return True
        except Exception as exc:
            logger.warning("Elegir voz %s en %s: %s", idx, self.motor, exc)
            return False

    def hablar(self, texto) -> bool:
        """Lanza la frase sin interrumpir lo que suene. False si no habló."""
        if not self._vivo():
            return False
        limpio = (texto or "").replace("\x00", "")
        if not limpio:
            return False
        try:
            self._backend.speak(limpio, interrupt=False)
            return True
        except Exception as exc:
            logger.warning("Hablar en %s: %s", self.motor, exc)
            return False

    def hablando(self) -> bool:
        if not self._vivo():
            return False
        try:
            return bool(self._backend.speaking)
        except Exception as exc:
            logger.warning("Consultar estado en %s: %s", self.motor, exc)
            return False

    def parar(self):
        if not self._vivo():
            return
        try:
            self._backend.stop()
        except Exception as exc:
            logger.warning("Parar en %s: %s", self.motor, exc)

    def pausar(self):
        if not self._vivo():
            return
        try:
            self._backend.pause()
        except self._ya_pausado:
            pass
        except Exception as exc:
            logger.warning("Pausar en %s: %s", self.motor, exc)

    def reanudar(self):
        if not self._vivo():
            return
        try:
            self._backend.resume()
        except self._no_pausado:
            pass
        except Exception as exc:
            logger.warning("Reanudar en %s: %s", self.motor, exc)

    def fijar_velocidad(self, pct):
        if not self._vivo():
            return
        try:
            self._backend.rate = escala_voz.velocidad_a_prism(self.motor, pct)
        except Exception as exc:
            logger.warning("Velocidad en %s: %s", self.motor, exc)

    def fijar_volumen(self, pct):
        if not self._vivo():
            return
        try:
            self._backend.volume = escala_voz.porcentaje_a_prism(pct)
        except Exception as exc:
            logger.warning("Volumen en %s: %s", self.motor, exc)

    def fijar_tono(self, pct):
        if not self._vivo():
            return
        try:
            self._backend.pitch = escala_voz.porcentaje_a_prism(pct)
        except Exception as exc:
            logger.warning("Tono en %s: %s", self.motor, exc)

    def cerrar(self):
        """Para el motor y suelta el backend y el contexto.

        Después de cerrar, todo método es no-op y `hablando()` devuelve False.
        """
        if getattr(self, "_cerrado", True):
            return
        try:
            if self._backend is not None:
                self._backend.stop()
        except Exception as exc:
            logger.debug("Parar al cerrar %s: %s", self.motor, exc)
        self._backend = None
        self._ctx = None
        self._cerrado = True


def crear_motor(motor, clave_elevenlabs=None):
    """Crea el motor pedido. Lanza `MotorNoDisponible` si no se puede.

    Para ElevenLabs, la clave se lee de `credenciales` cuando no se pasa (el
    archivo es del usuario y nunca vive en config.ini). La importación de
    `motor_elevenlabs` es perezosa: quien no usa ElevenLabs no lo carga.
    """
    if motor == "elevenlabs":
        from ytchat.voice import motor_elevenlabs
        if clave_elevenlabs is None:
            from ytchat.youtube import credenciales
            clave_elevenlabs = credenciales.cargar().get("elevenlabs_clave", "")
        return motor_elevenlabs.MotorElevenLabs(clave_elevenlabs)
    return MotorPrism(motor)


def listar_voces(motor, fabrica_contexto=None) -> list[str]:
    """Devuelve las voces de un motor sin tocar el del hilo de voz.

    Crea una instancia propia y la cierra. Lista vacía si el motor no está
    disponible (para ElevenLabs, sin clave guardada también es vacía).
    """
    if motor == "elevenlabs":
        try:
            instancia = crear_motor("elevenlabs")
        except MotorNoDisponible:
            return []
        try:
            return list(instancia.voces())
        finally:
            try:
                instancia.cerrar()
            except Exception:
                pass
    try:
        instancia = MotorPrism(motor, fabrica_contexto)
    except MotorNoDisponible:
        return []
    try:
        return instancia.voces()
    finally:
        instancia.cerrar()
