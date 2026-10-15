"""Anuncio corto al ajustar un valor varias veces seguidas (lógica pura, sin wx).

Quien ajusta algo repetidamente ya sabe qué está tocando: la primera vez se
dice el nombre y el valor, y si se vuelve a ajustar el MISMO control antes de
que pase la ventana se dice solo el valor. Si se ajusta OTRO control, vuelve
a decirse el nombre.

La instancia compartida `COMPARTIDO` cubre la ventana principal y el
reproductor, para que el cambio de un control a otro se note entre ambos. El
tono de la voz, cuando exista, va por el mismo camino: su control propio en
`COMPARTIDO`.
"""

from __future__ import annotations

import time


class AnuncioAjuste:
    """Recuerda el último control ajustado y su hora, y elige la frase."""

    def __init__(self, ventana: float = 60.0, reloj=time.monotonic):
        self._ventana = ventana
        self._reloj = reloj
        self._ultimo: str | None = None
        self._hora: float = 0.0

    def frase(self, control: str, completa: str, corta: str) -> str:
        """Devuelve `completa` si es otro control o pasó la ventana, si no `corta`.

        Siempre registra `control` y la hora actual."""
        ahora = self._reloj()
        if self._ultimo == control and ahora - self._hora <= self._ventana:
            elegida = corta
        else:
            elegida = completa
        self._ultimo = control
        self._hora = ahora
        return elegida

    def registrar(self, control: str) -> None:
        """Solo registra `control` y la hora, sin devolver frase.

        Para ajustes que no se anuncian (el deslizador ya lo lee NVDA), así
        un ajuste posterior por otro camino dice solo el valor."""
        self._ultimo = control
        self._hora = self._reloj()


COMPARTIDO = AnuncioAjuste()
