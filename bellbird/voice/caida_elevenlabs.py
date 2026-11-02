"""Cuándo un mensaje de ElevenLabs cae a la voz de Windows y cuándo se avisa.

`CaidaElevenLabs` guarda el tope, «solo lo importante», la marca del último
fallo y las marcas de aviso. El worker le pasa los valores y los caracteres
usados; la clase devuelve la decisión y el aviso, sin conocer el motor, el
worker ni wx.
"""

from __future__ import annotations

import time

from bellbird.core.idioma import N_, _
from bellbird.core.ini_tipado import a_entero

# Tras un fallo de ElevenLabs no se reintenta la nube por este tiempo: si no,
# cada mensaje sin red esperaría el tiempo agotado del cliente.
_VENTANA_ERROR_ELEVENLABS = 60.0

_MSG_TOPE = N_("Se alcanzó el límite de caracteres de ElevenLabs de esta sesión. "
                "Se usa la voz de Windows.")


class CaidaElevenLabs:
    """Decide cuándo el mensaje va a Windows y qué aviso corresponde."""

    def __init__(self, tope=0, solo_importantes=False):
        self.tope = max(0, a_entero(tope, 0))
        self.solo_importantes = bool(solo_importantes)
        # Marca de tiempo del último fallo de ElevenLabs y estado de los avisos.
        self._error_ts = 0.0
        self._aviso_dado = False
        self._aviso_tope_dado = False

    def elegir(self, importante, caracteres, largo):
        """Devuelve (usar_respaldo, aviso) para el mensaje."""
        if self.solo_importantes and not importante:
            return True, ""
        if self.tope > 0 and caracteres + largo > self.tope:
            if not self._aviso_tope_dado:
                self._aviso_tope_dado = True
                return True, _(_MSG_TOPE)
            return True, ""
        if self.error_reciente():
            return True, ""
        return False, ""

    def error_reciente(self) -> bool:
        ts = self._error_ts
        return bool(ts) and (time.monotonic() - ts) < _VENTANA_ERROR_ELEVENLABS

    def fallo(self, detalle):
        """Anota el fallo y devuelve el aviso si toca, o None."""
        self._error_ts = time.monotonic()
        if self._aviso_dado:
            return None
        self._aviso_dado = True
        return _("{detalle} Se usa la voz de Windows.").format(detalle=detalle)

    def exito(self) -> None:
        """Un mensaje bien leído cierra la racha de fallos."""
        self._aviso_dado = False

    def configurar(self, tope, solo_importantes) -> None:
        """Aplica el tope y «solo lo importante» en caliente."""
        self.tope = max(0, a_entero(tope, self.tope))
        self.solo_importantes = bool(solo_importantes)
