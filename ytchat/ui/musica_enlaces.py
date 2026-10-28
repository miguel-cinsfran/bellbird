"""Enlaces de YouTube: expandirlos en un hilo y sumarlos a la cola."""

from __future__ import annotations

import wx

from ytchat.core import diagnostico
from ytchat.core.idioma import _
from ytchat.music import anuncios
from ytchat.music import enlaces


logger = diagnostico.obtener_logger(__name__)


class EnlacesMusica:
    """Enlaces de YouTube: expandirlos en un hilo y sumarlos a la cola."""

    def abrir_enlace(self, url, modo="final") -> None:
        """Expande un enlace y aplica el modo pedido con todos sus temas.

        La expansión bloquea y toca la red, así que corre aparte y vuelve por
        `wx.CallAfter`: con los temas aplica "ahora", "continuacion" o
        "final", y ante un `ErrorEnlace` anuncia su mensaje con el sonido de
        error.
        """
        if not enlaces.es_enlace_youtube(url):
            self._avisar(anuncios.aviso_enlace_no_youtube())
            return
        self._avisar(anuncios.aviso_leyendo_enlace())
        diagnostico.crear_hilo(
            self._expandir_enlace, "musica-enlace",
            args=(url, modo)).start()

    def agregar_enlace(self, url) -> None:
        """Expande un enlace de YouTube y suma sus temas al final de la cola."""
        self.abrir_enlace(url, "final")

    def _expandir_enlace(self, url, modo) -> None:
        try:
            temas = enlaces.expandir(url)
        except enlaces.ErrorEnlace as exc:
            wx.CallAfter(self._aviso_error_enlace, str(exc))
            return
        except Exception:
            logger.exception("No se pudo expandir el enlace de música")
            wx.CallAfter(self._aviso_error_enlace, _(enlaces.TEXTO_NO_SE_PUDO_LEER))
            return
        wx.CallAfter(self._aplicar_enlace, temas, modo)

    def _aplicar_enlace(self, temas, modo) -> None:
        if modo == "ahora":
            self.reproducir_ahora(temas)
        elif modo == "continuacion":
            self.poner_a_continuacion(temas)
        else:
            self.agregar_al_final(temas)

    def _aviso_error_enlace(self, mensaje) -> None:
        self._avisar(anuncios.aviso_error_enlace(mensaje))
        self._refrescar_ventana_abierta()
