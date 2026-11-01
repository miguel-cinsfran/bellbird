"""Enlaces de YouTube: expandirlos en un hilo y sumarlos a la cola."""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.music import anuncios
from bellbird.music import enlaces


logger = diagnostico.obtener_logger(__name__)


class EnlacesMusica:
    """Enlaces de YouTube: expandirlos en un hilo y sumarlos a la cola."""

    def __init__(self):
        self._leyendo = set()

    def abrir_enlace(self, url, modo="final") -> None:
        """Expande un enlace y aplica el modo pedido con todos sus temas.

        La expansión bloquea y toca la red, así que corre aparte y vuelve por
        `wx.CallAfter`: con los temas aplica "ahora", "continuacion" o
        "final", y ante un `ErrorEnlace` anuncia su mensaje con el sonido de
        error. Mientras se lee, la dirección queda anotada para no pedirla dos
        veces.
        """
        if not enlaces.es_enlace_youtube(url):
            self._avisar(anuncios.aviso_enlace_no_youtube())
            return
        self._avisar(anuncios.aviso_leyendo_enlace())
        self._lanzar_enlace(url, modo)

    def agregar_enlace(self, url) -> None:
        """Expande un enlace de YouTube y suma sus temas al final de la cola."""
        self.abrir_enlace(url, "final")

    def leyendo_enlace(self, url) -> bool:
        """Si esa dirección ya se está leyendo."""
        return url in self._leyendo

    def _lanzar_enlace(self, url, modo) -> None:
        self._leyendo.add(url)
        try:
            diagnostico.crear_hilo(
                self._expandir_enlace, "musica-enlace",
                args=(url, modo)).start()
        except Exception:
            self._leyendo.discard(url)
            raise

    def _expandir_enlace(self, url, modo) -> None:
        try:
            temas = enlaces.expandir(url)
        except enlaces.ErrorEnlace as exc:
            wx.CallAfter(self._aviso_error_enlace, str(exc), url)
            return
        except Exception:
            logger.exception("No se pudo expandir el enlace de música")
            wx.CallAfter(self._aviso_error_enlace, _(enlaces.TEXTO_NO_SE_PUDO_LEER), url)
            return
        wx.CallAfter(self._aplicar_enlace, temas, modo, url)

    def _aplicar_enlace(self, temas, modo, url) -> None:
        self._leyendo.discard(url)
        if modo == "ahora":
            self.reproducir_ahora(temas)
        elif modo == "continuacion":
            self.poner_a_continuacion(temas)
        else:
            self.agregar_al_final(temas)

    def _aviso_error_enlace(self, mensaje, url) -> None:
        self._leyendo.discard(url)
        self._avisar(anuncios.aviso_error_enlace(mensaje))
        self._refrescar_ventana_abierta()
