"""Escuchar un resultado del buscador desde la música.

Razón: decidir qué hace «escuchar» sobre un resultado del buscador. Sin
controles: la página delega acá y este módulo no toca la lista, solo recibe
lo que la página ya resolvió.
"""

from __future__ import annotations

import wx

from guyrapu.core import diagnostico
from guyrapu.core.idioma import N_, _
from guyrapu.music.modelo import Tema
from guyrapu.ui.accesibilidad import anunciar
from guyrapu.voice import sound_player as _snd


logger = diagnostico.obtener_logger(__name__)

TEXTO_NO_ESCUCHABLE = N_("Este resultado no se puede escuchar.")


def _en_foco(lista, resultados):
    """El resultado de la fila enfocada, o None si no hay ninguna."""
    try:
        indice = lista.GetFocusedItem()
    except Exception:
        return None
    if 0 <= indice < len(resultados):
        return resultados[indice]
    return None


def _escuchable(resultado) -> bool:
    """Si ese resultado es un vídeo que no sea en directo ni programado."""
    return (resultado is not None
            and getattr(resultado, "tipo", None) == "video"
            and not getattr(resultado, "en_directo", False)
            and not getattr(resultado, "programado", False))


class EscuchaBuscador:
    """Qué hace «escuchar» sobre un resultado del buscador.

    `musica` es el control de música o None. Un vídeo se abre en la música
    con el modo «ahora»; si ese vídeo ya suena o está en pausa, se pausa o
    se reanuda como el atajo de la música.
    """

    def __init__(self, musica=None):
        self._musica = musica

    @property
    def hay_musica(self) -> bool:
        """Si hay control de música para el menú."""
        return self._musica is not None

    @property
    def agregar_musica(self):
        """Lo que agrega a la música, o None sin música."""
        if self._musica is None:
            return None
        return self._musica.agregar_enlace

    def alternar(self, resultado) -> None:
        """Escucha ese resultado, o pausa o reanuda si ya es el que suena.

        Arma el tema con lo que el resultado ya trae, sin leer el enlace.
        """
        if not _escuchable(resultado) or self._musica is None:
            self._sonar("error")
            anunciar(_(TEXTO_NO_ESCUCHABLE))
            return
        if self._musica.suena_enlace(resultado.url):
            self._musica.reproducir_o_pausar()
            return
        titulo = getattr(resultado, "titulo", "") or resultado.url
        self._musica.reproducir_ahora((Tema(resultado.url, titulo),))

    def al_teclear(self, event, lista, resultados) -> bool:
        """Espacio sobre la lista: escucha la fila enfocada. Dice si la usó.

        Espacio con Ctrl, Mayús o Alt no es escucha y se deja pasar, para
        que Ctrl+Espacio siga funcionando como siempre.
        """
        if (event.GetKeyCode() != wx.WXK_SPACE or event.ControlDown()
                or event.ShiftDown() or event.AltDown()):
            return False
        resultado = _en_foco(lista, resultados)
        if resultado is None:
            self._sonar("error")
            anunciar(_("Selecciona un resultado."))
            return True
        self.alternar(resultado)
        return True

    @staticmethod
    def _sonar(evento) -> None:
        try:
            _snd.reproducir(evento)
        except Exception as error:
            logger.debug("sin sonido: %s", error)
