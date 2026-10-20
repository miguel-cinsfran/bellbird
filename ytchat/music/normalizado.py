"""Volumen de música con la ganancia de sonoridad aplicada por tema.

Envuelve al adaptador real (libVLC) y corrige el volumen de cada canción
local ya medida, sin tocar lo que suena a mitad: la ganancia vale desde el
`cargar` siguiente. Lo no medido y los enlaces suenan con el volumen del
usuario, como siempre.
"""

from __future__ import annotations

from ytchat.core import diagnostico
from ytchat.music import sonoridad


logger = diagnostico.obtener_logger(__name__)


class Normalizado:
    """Adaptador que aplica la ganancia de `ganancia_de` a cada tema.

    `ganancia_de(tema)` la da el control y devuelve la corrección en dB
    (0.0 si el tema no está medido). El volumen del usuario nace del
    `volumen` del constructor y se guarda en cada llamada a `volumen`.
    """

    def __init__(self, adaptador, ganancia_de, volumen=100):
        self._adaptador = adaptador
        self._ganancia_de = ganancia_de
        self._volumen = volumen
        self._ganancia = 0.0
        self._activo = True

    def fijar_activo(self, activo) -> None:
        """Enciende o apaga la igualación desde el próximo tema.

        No toca lo que suena: solo cambia la ganancia que se aplicará en
        el siguiente `cargar`.
        """
        self._activo = bool(activo)

    def cargar(self, tema, ficha) -> None:
        """Aplica el volumen corregido y después carga el tema.

        El volumen va antes porque el adaptador real le pone a cada
        reproductor nuevo el último volumen que recibió. Con la igualación
        apagada, o si `ganancia_de` lanza, la ganancia es 0 y el tema igual
        se carga.
        """
        if self._activo:
            try:
                ganancia = self._ganancia_de(tema)
            except Exception as exc:
                logger.warning("Sin ganancia para %s: %s",
                               getattr(tema, "origen", tema), exc)
                ganancia = 0.0
        else:
            ganancia = 0.0
        try:
            self._ganancia = float(ganancia)
        except (TypeError, ValueError):
            self._ganancia = 0.0
        self._adaptador.volumen(
            sonoridad.volumen_efectivo(self._volumen, self._ganancia))
        self._adaptador.cargar(tema, ficha)

    def volumen(self, valor) -> None:
        """Guarda el volumen del usuario y aplica el efectivo con la ganancia.

        El silencio del coordinador llega como `volumen(0)` y da 0 con
        cualquier ganancia.
        """
        self._volumen = valor
        self._adaptador.volumen(
            sonoridad.volumen_efectivo(valor, self._ganancia))

    def __getattr__(self, nombre):
        """Todo lo demás va directo al adaptador real."""
        return getattr(self._adaptador, nombre)
