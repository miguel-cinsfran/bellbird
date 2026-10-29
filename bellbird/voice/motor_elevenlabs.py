"""Motor de voz que sintetiza y reproduce con ElevenLabs.

Misma interfaz que `MotorPrism` para que el worker no note la diferencia. La
síntesis es un POST que bloquea el hilo del worker (dueño del motor, está bien
así) y devuelve un WAV; se guarda en la carpeta temporal del audio y se
reproduce con MCI, igual que `sound_player`, con un alias propio por frase.

Todo MCI y todo archivo se usan y se borran desde el mismo hilo que creó el
motor: MCI no es seguro entre hilos. `hablar` NO atrapa `ElevenLabsError`: lo
deja salir para que el worker decida el respaldo. Cualquier otro fallo de
reproducción devuelve False.
"""

from __future__ import annotations

import itertools
import os
import sys
from pathlib import Path

from bellbird.core import diagnostico
from bellbird.core import paths
from bellbird.core.idioma import N_, _
from bellbird.voice import escala_voz
from bellbird.voice import elevenlabs
from bellbird.voice.motores import MotorNoDisponible

logger = diagnostico.obtener_logger(__name__)

_winmm = None
_backend_ok = False

_alias_prefijo = "ytcel"
_alias_contador = itertools.count(1)
_archivo_contador = itertools.count(1)

_ERROR_SIN_CLAVE = N_("Falta la clave de ElevenLabs.")
_ERROR_SIN_VOCES = N_("ElevenLabs no devolvió ninguna voz.")


def _init_backend() -> None:
    global _winmm, _backend_ok
    if _backend_ok or sys.platform != "win32":
        return
    try:
        import ctypes
        _winmm = ctypes.WinDLL("winmm.dll")
        _winmm.mciSendStringW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p,
        ]
        _winmm.mciSendStringW.restype = ctypes.c_uint
        _backend_ok = True
    except Exception as exc:
        logger.warning("motor_elevenlabs: winmm.dll no disponible (%s).", exc)


def _mci(cmd: str) -> int:
    return int(_winmm.mciSendStringW(cmd, None, 0, None))


def _mci_consulta(cmd: str) -> str:
    """Comando MCI con respuesta (p. ej. `status x mode`). "" si falla."""
    import ctypes
    buf = ctypes.create_unicode_buffer(128)
    rc = int(_winmm.mciSendStringW(cmd, buf, len(buf), None))
    return buf.value.strip() if rc == 0 else ""


class MotorElevenLabs:
    """Motor de voz de ElevenLabs con la interfaz de `MotorPrism`."""

    motor = "elevenlabs"

    def __init__(self, clave, cliente=None):
        if not clave:
            raise MotorNoDisponible(_(_ERROR_SIN_CLAVE))
        self._cliente = (cliente if cliente is not None
                         else elevenlabs.ClienteElevenLabs(clave))
        try:
            self._pares = list(self._cliente.voces())
        except Exception as exc:
            raise MotorNoDisponible(str(exc)) from exc
        if not self._pares:
            raise MotorNoDisponible(_(_ERROR_SIN_VOCES))
        self._nombres = [nombre for _id, nombre in self._pares]
        self._idx = 0
        self._velocidad = escala_voz.VELOCIDAD_NORMAL
        self._volumen = 100
        self._alias = None
        self._ruta = None
        self._caracteres = 0
        self._cerrado = False

    # ── Interfaz de motor ────────────────────────────────────────────────────

    def voces(self) -> list[str]:
        return list(self._nombres)

    def elegir_voz(self, idx) -> bool:
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            return False
        if not 0 <= idx < len(self._pares):
            return False
        self._idx = idx
        return True

    def hablar(self, texto) -> bool:
        """Sintetiza la frase y la reproduce. Bloquea hasta dejarla sonando."""
        if self._cerrado:
            return False
        limpio = (texto or "").replace("\x00", "")
        if not limpio.strip():
            return False
        voice_id = self._pares[self._idx][0]
        # Si esto lanza ElevenLabsError, NO se atrapa: lo decide el worker.
        wav = self._cliente.sintetizar(limpio, voice_id, self._velocidad)
        self._caracteres += len(limpio)
        try:
            carpeta = paths.audio_temporal()
            ruta = carpeta / (
                f"{_alias_prefijo}_{os.getpid()}_{next(_archivo_contador)}.wav")
            ruta.write_bytes(wav)
        except Exception as exc:
            logger.warning("motor_elevenlabs: no se pudo escribir el audio: %s", exc)
            return False
        if not self._reproducir(ruta):
            try:
                ruta.unlink()
            except Exception:
                pass
            return False
        return True

    def hablando(self) -> bool:
        if not self._alias:
            return False
        modo = _mci_consulta(f"status {self._alias} mode")
        if modo.lower() == "playing":
            return True
        # Terminó (o MCI no contesta): se cierra el alias y se borra el archivo.
        self._cerrar_alias()
        return False

    def parar(self) -> None:
        if self._alias:
            try:
                _mci(f"stop {self._alias}")
            except Exception as exc:
                logger.debug("motor_elevenlabs: %s", exc)
        self._cerrar_alias()

    def pausar(self) -> None:
        if self._alias:
            try:
                _mci(f"pause {self._alias}")
            except Exception as exc:
                logger.debug("motor_elevenlabs: %s", exc)

    def reanudar(self) -> None:
        if self._alias:
            try:
                _mci(f"resume {self._alias}")
            except Exception as exc:
                logger.debug("motor_elevenlabs: %s", exc)

    def fijar_velocidad(self, pct) -> None:
        try:
            self._velocidad = max(0, min(100, int(pct)))
        except (TypeError, ValueError):
            pass

    def fijar_volumen(self, pct) -> None:
        try:
            self._volumen = max(0, min(100, int(pct)))
        except (TypeError, ValueError):
            pass

    def fijar_tono(self, pct) -> None:
        # ElevenLabs no tiene tono: no-op para cumplir la interfaz.
        return

    def cerrar(self) -> None:
        if self._cerrado:
            return
        self.parar()
        self._cerrado = True

    def caracteres_usados(self) -> int:
        """Caracteres sintetizados con éxito desde que se creó (sesión)."""
        return self._caracteres

    # ── MCI ──────────────────────────────────────────────────────────────────

    def _volumen_mci(self) -> int:
        return max(0, min(1000, int(self._volumen) * 10))

    def _reproducir(self, ruta) -> bool:
        _init_backend()
        if not _backend_ok:
            return False
        self._cerrar_alias()
        alias = f"{_alias_prefijo}{next(_alias_contador)}"
        ruta_abs = str(Path(ruta).resolve())
        try:
            # Comillas alrededor de la ruta porque puede contener espacios o
            # acentos que MCI interpretaría como separadores de argumentos.
            if _mci(f'open "{ruta_abs}" type waveaudio alias {alias}') != 0:
                return False
            _mci(f"setaudio {alias} volume to {self._volumen_mci()}")
            if _mci(f"play {alias}") != 0:
                _mci(f"close {alias}")
                return False
        except Exception as exc:
            logger.debug("motor_elevenlabs: %s", exc)
            try:
                _mci(f"close {alias}")
            except Exception:
                pass
            return False
        self._alias = alias
        self._ruta = Path(ruta)
        return True

    def _cerrar_alias(self) -> None:
        alias, ruta = self._alias, self._ruta
        self._alias = None
        self._ruta = None
        if alias:
            try:
                _mci(f"close {alias}")
            except Exception:
                pass
        if ruta is not None:
            try:
                Path(ruta).unlink()
            except Exception:
                pass
