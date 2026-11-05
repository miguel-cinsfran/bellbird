"""Enlaces de YouTube: expandirlos en un hilo y sumarlos a la cola."""

from __future__ import annotations

import wx

from guyrapu.core import diagnostico
from guyrapu.core.idioma import _
from guyrapu.music import anuncios
from guyrapu.music import enlaces
from guyrapu.music.transporte import toca_pausar


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

    def ceder_al_reproductor(self, url) -> None:
        """Deja la música fuera del camino al abrir ese vídeo en Bellbird.

        Si es el tema actual, se detiene y sale de la cola. Si suena otro,
        queda en pausa sin reanudarse. Sin tema activo no hace nada.
        """
        if not self.suena_enlace(url):
            estado = self.estado()
            if toca_pausar(estado) and not estado.pausado:
                self.reproducir_o_pausar()
            return
        indice = self.estado().posicion
        # Quitar el actual antes de detener haría sonar al siguiente.
        self.detener()
        self.quitar_de_cola(indice)

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
