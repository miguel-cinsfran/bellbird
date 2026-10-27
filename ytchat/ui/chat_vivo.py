"""Cola y volcado agrupado del chat en vivo.

El ControladorChat guarda los mensajes que llegan, los vuelca a la lista en
lotes con un temporizador y reconstruye la vista al cambiar el filtro.
"""

from __future__ import annotations

import wx

from ytchat.core import diagnostico
from ytchat.core import sonidos_eventos
from ytchat.core.config import (
    TIPO_ME_GUSTA, TIPO_MIEMBRO, TIPO_STICKER, TIPO_SUPERCHAT,
)
from ytchat.ui.lista_chat import ListaChat, MensajeChat
from ytchat.voice import sound_player as _snd


# Ráfagas de mensajes del chat: en vez de un Append/Delete por mensaje (mucho
# repintado en el hilo de GUI mientras NVDA navega la lista), se agrupan y se
# vuelcan juntos cada tanto. Ver ControladorChat.encolar / volcar.
MS_VOLCADO_CHAT = 120


logger = diagnostico.obtener_logger(__name__)


class ControladorChat:
    """Estado y volcado del chat en vivo, separado de la ventana principal."""

    def __init__(self, lista, maximo, *, activo, autor_oculto,
                 formatear, al_superchat):
        self.lista = lista
        self.modelo = ListaChat(maximo)
        self.filtro = None
        self._pendientes: list[MensajeChat] = []
        self._timer = None
        self._activo = activo
        self._autor_oculto = autor_oculto
        self._formatear = formatear
        self._al_superchat = al_superchat

    def encolar(self, registro: MensajeChat) -> None:
        self._pendientes.append(registro)
        # Si el temporizador ya corre, NO reiniciarlo: con un chat activo
        # (mensajes cada menos de MS_VOLCADO_CHAT) reiniciar pospondría el
        # volcado indefinidamente y no aparecería nada hasta una pausa.
        if self._timer is None:
            self._timer = wx.CallLater(MS_VOLCADO_CHAT, self.volcar)

    def _procesar(self, registro: MensajeChat) -> bool:
        """Aplica UN mensaje ya desencolado al modelo y a la lista. Devuelve si
        quedó visible (se le hizo Append). Solo lo llama volcar."""
        if self._autor_oculto(registro.autor):
            return False

        if registro.tipo == TIPO_ME_GUSTA:
            # El me gusta solo suena: no toca ni el modelo ni la lista, para
            # no desalinear fila ↔ mensaje.
            _snd.reproducir(sonidos_eventos.sonido_de_mensaje(
                registro.tipo, registro.rol, registro.monto,
                registro.plataforma))
            return False

        # El modelo (lista_chat) recorta el historial y dice cuántas filas viejas
        # borrar al principio, para que fila y mensaje sigan alineados: si no,
        # pasados 500 mensajes, copiar o banear caerían sobre el mensaje
        # equivocado.
        visible = self.filtro is None or registro.tipo == self.filtro
        borrar = self.modelo.agregar(registro, visible)
        for _sin_uso in range(borrar):
            self.lista.Delete(0)

        if registro.tipo in (TIPO_SUPERCHAT, TIPO_STICKER):
            _snd.reproducir(sonidos_eventos.sonido_de_mensaje(
                registro.tipo, registro.rol, registro.monto,
                registro.plataforma))
            self._al_superchat(registro.monto)
        elif registro.tipo == TIPO_MIEMBRO:
            _snd.reproducir("nuevo_miembro")
        else:
            _snd.reproducir(sonidos_eventos.sonido_de_mensaje(registro.tipo,
                                                              registro.rol))

        if visible:
            self.lista.Append(self._formatear(
                registro.autor, registro.texto, registro.hora, registro.tipo, registro.monto))
        return visible

    def volcar(self) -> None:
        """Procesa TODOS los mensajes en espera de una vez: modelo y vista se
        mutan juntos aquí (nunca al encolar), así que fila↔mensaje se mantienen
        alineados igual que antes. Con más de un pendiente, Freeze/Thaw evita
        repintar fila a fila."""
        self._timer = None
        pendientes, self._pendientes = self._pendientes, []
        if not pendientes or not self._activo():
            return
        freeze = len(pendientes) > 1
        if freeze:
            self.lista.Freeze()
        hubo_visible = False
        try:
            for registro in pendientes:
                if self._procesar(registro):
                    hubo_visible = True
        finally:
            if freeze:
                self.lista.Thaw()
        # Un solo SetFirstItem al final (no uno por mensaje), y solo si el foco
        # no está en la lista (si el usuario está navegando, no le movemos la
        # vista) y algo se añadió de verdad.
        if hubo_visible and wx.Window.FindFocus() is not self.lista:
            self.lista.SetFirstItem(self.lista.GetCount() - 1)

    def volcar_ya(self) -> None:
        """Vuelca ya lo encolado, sin esperar el temporizador. Se usa antes de
        leer/reconstruir la lista desde el modelo (cambio de filtro) para que
        no falte lo más reciente todavía sin procesar."""
        if self._timer is not None:
            try:
                self._timer.Stop()
            except Exception as exc:
                logger.debug("No se pudo parar el temporizador del chat: %s", exc)
            self._timer = None
        self.volcar()

    def descartar(self) -> None:
        """Tira lo encolado sin procesarlo. Se usa donde hoy se limpia la lista
        entera (desconectar, cambiar de vídeo): esos mensajes pertenecen a la
        sesión que se está borrando."""
        if self._timer is not None:
            try:
                self._timer.Stop()
            except Exception as exc:
                logger.debug("No se pudo parar el temporizador del chat: %s", exc)
            self._timer = None
        self._pendientes.clear()

    def reconstruir(self) -> None:
        # Que lo que acaba de llegar (aún en cola, sin pasar por el modelo) no
        # se pierda del recuento/reconstrucción: se procesa YA con el estado
        # vigente antes de leer el modelo.
        self.volcar_ya()
        self.lista.Clear()
        visibles = self.modelo.reconstruir(
            lambda it: not self._autor_oculto(it.autor)
            and (self.filtro is None or it.tipo == self.filtro))
        for registro in visibles:
            self.lista.Append(self._formatear(
                registro.autor, registro.texto, registro.hora, registro.tipo, registro.monto))
