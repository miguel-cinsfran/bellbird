"""La voz secundaria por evento: su voz, sus ajustes y su respaldo.

`VozSecundaria` guarda la voz que se usa en el motor principal para los
eventos en modo secundaria, con su velocidad y su volumen, y es dueña de su
instancia de `Respaldo` para cuando ElevenLabs cae a Windows. El worker le
pasa las voces del motor y los valores; la clase no lee atributos del worker.
"""

from __future__ import annotations

from guyrapu.core.ini_tipado import a_decimal, a_entero
from guyrapu.voice import escala_voz
from guyrapu.voice.respaldo_windows import Respaldo


class VozSecundaria:
    """Voz, velocidad, volumen y respaldo de los eventos secundarios."""

    def __init__(self, fabrica_motor, config, tono=50):
        self.voz = config.get("voz_secundaria") or ""
        self.velocidad = escala_voz.ajustar_velocidad(
            a_entero(config.get("velocidad_secundaria"),
                     escala_voz.VELOCIDAD_NORMAL), 0)
        self.volumen = max(0, min(100, int(round(
            a_decimal(config.get("volumen_secundaria"), 1.0) * 100))))
        self.tono = max(0, min(100, a_entero(tono, 50)))
        self.sonando = False
        self._respaldo_propio = config.get("voz_respaldo_secundaria") or ""
        self._respaldo = Respaldo(fabrica_motor, self._respaldo_propio)

    def indice(self, voces, secundaria):
        """Índice, velocidad y volumen si el mensaje pide la secundaria.

        Devuelve None para que el mensaje use la principal. También devuelve
        None si la voz secundaria está vacía o no existe en `voces`."""
        if not secundaria:
            return None
        idx = escala_voz.resolver_voz(self.voz, voces)
        if idx is None:
            return None
        return idx, self.velocidad, self.volumen

    def conseguir_respaldo(self, voz_principal="", tono=None):
        """Devuelve el motor de Windows de la secundaria, o None si falla."""
        if tono is not None:
            self.tono = max(0, min(100, a_entero(tono, self.tono)))
        if not self._respaldo_propio:
            self._respaldo.cambiar_voz(voz_principal)
        return self._respaldo.conseguir(
            self.velocidad, self.volumen, self.tono)

    def seguir_respaldo(self, voz) -> None:
        """Sigue la voz de respaldo principal si no tiene una propia."""
        if not self._respaldo_propio:
            self._respaldo.cambiar_voz(voz)

    def configurar(self, voz, velocidad, volumen, respaldo,
                   voz_principal="", tono=None) -> None:
        """Aplica en caliente la voz, la velocidad, el volumen y el respaldo."""
        self.voz = voz or ""
        self.velocidad = escala_voz.ajustar_velocidad(
            a_entero(velocidad, self.velocidad), 0)
        self.volumen = max(0, min(100, int(round(
            a_decimal(volumen, self.volumen / 100.0) * 100))))
        if tono is not None:
            self.tono = max(0, min(100, a_entero(tono, self.tono)))
        self._respaldo_propio = respaldo or ""
        self._respaldo.cambiar_voz(self._respaldo_propio or voz_principal)
        self._respaldo.fijar_ajustes(
            self.velocidad, self.volumen, self.tono)

    def cerrar(self) -> None:
        """Cierra el respaldo de Windows de la secundaria."""
        self._respaldo.cerrar()
