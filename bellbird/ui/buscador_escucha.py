"""Escucha previa de un resultado con anuncios, sonidos y pausa de la música.

Razón: conectar la escucha con los anuncios, los sonidos y la pausa de
la música. Sin controles: la página delega acá y este módulo no toca la
lista, solo recibe lo que la página ya resolvió.
"""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import N_, _
from bellbird.music.escucha import Escucha
from bellbird.ui.accesibilidad import anunciar
from bellbird.voice import sound_player as _snd


logger = diagnostico.obtener_logger(__name__)

TEXTO_NO_ESCUCHABLE = N_("Este resultado no se puede escuchar.")
TEXTO_CARGANDO = N_("Cargando vista previa de audio")
TEXTO_PAUSA = N_("En pausa")
TEXTO_REANUDADA = N_("Reproduciendo")


def _en_foco(lista, resultados):
    """El resultado de la fila enfocada, o None si no hay ninguna."""
    try:
        indice = lista.GetFocusedItem()
    except Exception:
        return None
    if 0 <= indice < len(resultados):
        return resultados[indice]
    return None


class EscuchaBuscador:
    """La escucha previa de la página del buscador, con su pausa de música.

    `musica` es el control de música o None. La `Escucha` se crea la
    primera vez que hace falta, con sus ajustes, y todo aviso suyo pasa
    por `wx.CallAfter` para tocar la GUI en su hilo.
    """

    def __init__(self, musica=None):
        self._musica = musica
        self._escucha = None
        self._pauso = False
        self._invalida = False

    @property
    def hay_musica(self) -> bool:
        """Si hay control de música para pausar y para el menú."""
        return self._musica is not None

    @property
    def agregar_musica(self):
        """Lo que agrega a la música, o None sin música."""
        if self._musica is None:
            return None
        return self._musica.agregar_enlace

    @property
    def url(self):
        """La URL que se está escuchando, o None si no hay ninguna."""
        if self._escucha is None:
            return None
        return self._escucha.url

    def alternar(self, resultado) -> None:
        """Escucha ese resultado, o lo pausa si ya sonaba.

        Solo vale un vídeo que no sea en directo ni programado. Al
        empezar pausa la música y recuerda si pausó; pasar de un
        resultado a otro no la reanuda en el medio.
        """
        if (resultado is None or getattr(resultado, "tipo", None) != "video"
                or getattr(resultado, "en_directo", False)
                or getattr(resultado, "programado", False)):
            self._sonar("error")
            anunciar(_(TEXTO_NO_ESCUCHABLE))
            return
        escucha = self._asegurar()
        if escucha.url != resultado.url and not self._pauso:
            self._pausar_musica()
        escucha.alternar(resultado.url)

    def detener(self) -> None:
        """Detiene la escucha y reanuda la música, si la pausó.

        Repetirlo no hace nada.
        """
        if self._escucha is not None:
            try:
                self._escucha.detener()
            except Exception as error:
                logger.debug("no se pudo detener la escucha: %s", error)
        self._reanudar_musica()

    def invalidar(self) -> None:
        """La página se destruyó: los avisos que lleguen se ignoran."""
        self._invalida = True

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

    def seguir_foco(self, lista, resultados) -> None:
        """Si la fila enfocada ya no es la que suena, detiene la escucha."""
        if self._escucha is None or self._escucha.url is None:
            return
        enfocado = _en_foco(lista, resultados)
        if enfocado is not None and enfocado.url != self._escucha.url:
            self.detener()

    def al_cambiar(self, event) -> None:
        """Cambiar de pestaña detiene la escucha y deja seguir el evento."""
        self.detener()
        event.Skip()

    def al_destruir(self, event) -> None:
        """La página se destruyó: invalida y deja seguir el evento."""
        self._invalida = True
        event.Skip()

    def _asegurar(self):
        """La escucha, creada con los ajustes de la música si la hay."""
        if self._escucha is None:
            if self._musica is not None:
                dispositivo, volumen = self._musica.ajustes_escucha()
            else:
                dispositivo, volumen = None, 100
            self._escucha = Escucha(
                self._avisar, dispositivo=dispositivo, volumen=volumen)
        return self._escucha

    def _avisar(self, evento, detalle="") -> None:
        wx.CallAfter(self._al_avisar, evento, detalle)

    def _al_avisar(self, evento, detalle="") -> None:
        if self._invalida:
            return
        if evento == "cargando":
            self._sonar("escucha_cargando")
            anunciar(_(TEXTO_CARGANDO))
        elif evento == "pausa":
            anunciar(_(TEXTO_PAUSA))
        elif evento == "reanudada":
            anunciar(_(TEXTO_REANUDADA))
        elif evento == "fin":
            self._reanudar_musica()
        elif evento == "fallo":
            self._sonar("escucha_fallida")
            anunciar(detalle)
            self._reanudar_musica()

    def _pausar_musica(self) -> None:
        try:
            self._pauso = bool(self._musica.pausar_para_escuchar())
        except Exception as error:
            logger.debug("no se pudo pausar la música: %s", error)
            self._pauso = False

    def _reanudar_musica(self) -> None:
        if not self._pauso:
            return
        self._pauso = False
        try:
            self._musica.reanudar_tras_escuchar()
        except Exception as error:
            logger.debug("no se pudo reanudar la música: %s", error)

    @staticmethod
    def _sonar(evento) -> None:
        try:
            _snd.reproducir(evento)
        except Exception as error:
            logger.debug("sin sonido: %s", error)
