"""Mensajes recientes del chat con atajos que valen en cualquier programa.

`Ctrl+Mayús+1` a `Ctrl+Mayús+0` leen con el lector los diez últimos mensajes
de la lista del chat: 1 el último, 0 el décimo desde el final. De fábrica
valen solo dentro de la app; la casilla de Preferencias, Lectura, los hace
valer en cualquier programa, como los atajos de música. No lee atributos
privados de nadie: la lista se recorre con `GetCount` y `GetString`.
"""

from __future__ import annotations

import wx

from ytchat.core import atajos as _atajos_fijos
from ytchat.core import diagnostico
from ytchat.music import anuncios
from ytchat.ui import atajos_globales
from ytchat.ui.atajos_globales import combinacion_ctrl_mayus
from ytchat.ui.lista_chat import texto_reciente
from ytchat.voice import sound_player as _snd


logger = diagnostico.obtener_logger(__name__)

# Acciones fijas de recientes, en orden: el índice da el id desde BASE_IDS.
ORDEN = (
    "chat_reciente_1",
    "chat_reciente_2",
    "chat_reciente_3",
    "chat_reciente_4",
    "chat_reciente_5",
    "chat_reciente_6",
    "chat_reciente_7",
    "chat_reciente_8",
    "chat_reciente_9",
    "chat_reciente_10",
)

# Base de los ids propios para `RegisterHotKey`, lejos de los de música.
BASE_IDS = 0xB100

TEXTO_ACTIVOS = "Mensajes recientes del chat en cualquier programa"
TEXTO_SOLO = "Mensajes recientes del chat solo en YTChat"


class LecturaRecientes:
    """Lee un mensaje reciente por su posición y maneja sus atajos globales.

    `ventana` es el frame, `lista` es `lb_chat` y `config` el dict de
    configuración. Nunca lanza: registrar o soltar puede fallar (otro
    programa tiene la combinación, la ventana se cerró) y se informa con
    el anuncio de fallo, no con excepciones.
    """

    def __init__(self, ventana, lista, config) -> None:
        self._ventana = ventana
        self._lista = lista
        self._config = config
        self._acciones = {accion: (lambda n=n: self.leer(n))
                          for n, accion in enumerate(ORDEN, start=1)}
        self._globales = atajos_globales.AtajosGlobales(
            ventana, self._acciones, orden=ORDEN, base_ids=BASE_IDS,
            traducir=combinacion_ctrl_mayus)
        self._globales_atajos = None
        if bool(config.get("lectura_atajos_globales", False)):
            # Después de que la ventana exista: el registro es del sistema
            # y pide el bucle de eventos.
            try:
                wx.CallAfter(self.activar_arranque)
            except Exception:
                logger.debug("No se pudieron activar los atajos de recientes")

    def leer(self, n: int) -> None:
        """Anuncia el mensaje `n` desde el final de la lista del chat."""
        from ytchat.ui import gui as _gui
        filas = [self._lista.GetString(i)
                 for i in range(self._lista.GetCount())]
        _gui.anunciar(texto_reciente(filas, n))

    def _textos(self) -> dict:
        """Los atajos efectivos de recientes, acción → texto guardado."""
        return {accion: _atajos_fijos.ATAJOS_FIJOS_DEFAULTS[accion]
                for accion in ORDEN}

    def activar_arranque(self) -> None:
        """Activa los globales al arrancar: calla salvo que algo falle."""
        try:
            textos = self._textos()
            fallidos = self._globales.activar(textos)
        except Exception:
            logger.exception("No se pudieron activar los atajos de recientes")
            return
        self._globales_atajos = textos
        if fallidos:
            self._avisar(anuncios.aviso_atajos_globales_fallo(fallidos))

    def aplicar_preferencias(self) -> None:
        """Activa o desactiva los globales según la preferencia.

        Al activar desde Preferencias se anuncia (y el fallo, con error);
        al desactivar, también. Nunca lanza.
        """
        try:
            if bool(self._config.get("lectura_atajos_globales", False)):
                textos = self._textos()
                if self._globales.activos and textos == self._globales_atajos:
                    return
                fallidos = self._globales.activar(textos)
                self._globales_atajos = dict(textos)
                if fallidos:
                    self._avisar(anuncios.aviso_atajos_globales_fallo(fallidos))
                else:
                    self._avisar(anuncios.Aviso(TEXTO_ACTIVOS))
            elif self._globales.activos:
                self._globales.desactivar()
                self._globales_atajos = None
                self._avisar(anuncios.Aviso(TEXTO_SOLO))
        except Exception:
            logger.exception("No se pudieron aplicar los atajos de recientes")

    def cerrar(self) -> None:
        """Suelta los atajos. Nunca lanza."""
        try:
            self._globales.desactivar()
        except Exception:
            logger.debug("No se pudieron soltar los atajos de recientes")

    def _avisar(self, aviso) -> None:
        if aviso is None:
            return
        if aviso.sonido:
            try:
                _snd.reproducir(aviso.sonido)
            except Exception:
                logger.debug("No se pudo reproducir el sonido %s", aviso.sonido)
        if aviso.texto:
            from ytchat.ui import gui as _gui
            _gui.anunciar(aviso.texto)
