"""Revisión al arranque de directos que quedaron al aire sin imagen.

Los directos se crean sin autoStop: si la persona cierra YTChat y después
OBS, el directo queda al aire sin imagen hasta que alguien lo finalice.
Al arrancar, este módulo revisa una sola vez si la cuenta tiene un
directo al aire atado a su clave mientras OBS no transmite, y pregunta
si finalizarlo. Nunca lo finaliza solo: la misma clave puede usarse
desde otro programa.
"""

from __future__ import annotations

import wx

from ytchat.core import diagnostico
from ytchat.obs import obs_activacion
from ytchat.obs.obs_panel import GestorPanelObs
from ytchat.ui.gui import anunciar
from ytchat.voice import sound_player as _snd
from ytchat.youtube import credenciales, emision, youtube_api

logger = diagnostico.obtener_logger(__name__)


def directos_sin_imagen(activas, id_flujo, obs_transmite) -> list[tuple]:
    """Pares (id, título) de las activas atadas a la clave, sin imagen.

    Vacía si OBS transmite o si no hay clave reutilizable: en el primer
    caso hay imagen, en el segundo no hay nada a lo que atar.
    """
    if obs_transmite or not id_flujo:
        return []
    return [(id_video, titulo) for id_video, atado, titulo in activas
            if atado == id_flujo]


def programar_revision(frame) -> None:
    """A los 15000 ms revisa en un hilo si quedó un directo al aire."""
    try:
        wx.CallLater(15000, _revisar_en_hilo, frame)
    except Exception as exc:
        logger.warning("revisión de directo huérfano: %s", exc)


def _revisar_en_hilo(frame) -> None:
    try:
        diagnostico.crear_hilo(
            lambda: _consultar(frame), "RevisarDirectoHuerfano").start()
    except Exception as exc:
        logger.warning("revisión de directo huérfano: %s", exc)


def _obs_transmite() -> bool:
    """True si OBS emite ahora mismo.

    Si OBS no corre, False. Si corre pero el websocket no responde, True
    por la duda: no se molesta a nadie preguntando.
    """
    if not obs_activacion.obs_esta_en_ejecucion():
        return False
    try:
        gestor = GestorPanelObs()
        try:
            gestor.conectar()
            return bool(
                gestor.estado_transmision().get("outputActive", False))
        finally:
            try:
                gestor.cerrar()
            except Exception:
                pass
    except Exception:
        return True


def _guardar_token_si_hay(cliente) -> None:
    try:
        nuevo = cliente.token_actualizado()
    except Exception:
        nuevo = None
    if nuevo:
        try:
            credenciales.guardar_campo("token", nuevo)
        except Exception:
            pass


def _consultar(frame) -> None:
    """Consulta en el hilo de trabajo y agenda la pregunta si hace falta.

    Sin sesión no pide nada a la API. No toca wx salvo `wx.CallAfter`:
    la ventana solo se toca en el hilo principal, desde `_preguntar`.
    """
    try:
        datos = credenciales.cargar()
        if not credenciales.hay_sesion(datos):
            return
        obs_transmite = _obs_transmite()
        cliente = youtube_api.ClienteYouTube(credenciales.efectivas(datos))
        try:
            flujo = cliente.flujo_reutilizable()
            id_flujo = flujo[0] if flujo else ""
            huerfanos = directos_sin_imagen(
                cliente.emisiones_activas(), id_flujo, obs_transmite)
        finally:
            _guardar_token_si_hay(cliente)
        if huerfanos:
            wx.CallAfter(_preguntar, frame, huerfanos)
    except Exception as exc:
        logger.warning("revisión de directo huérfano: %s", exc)


def _preguntar(frame, huerfanos) -> None:
    """Pregunta en el hilo de la ventana si se finaliza el directo."""
    try:
        if not getattr(frame, "_alive", False):
            return
        if frame._supervisar_transmision("activo"):
            return
        if len(huerfanos) == 1:
            texto = (f"Tu directo «{huerfanos[0][1]}» sigue al aire en "
                     "YouTube, pero OBS no está transmitiendo, así que "
                     "quienes lo miran no ven nada. ¿Finalizarlo?")
        else:
            texto = (f"Tienes {len(huerfanos)} directos al aire en YouTube "
                     "sin imagen, porque OBS no está transmitiendo. "
                     "¿Finalizarlos?")
        dialogo = wx.MessageDialog(
            frame, texto, "Directo sin imagen", wx.YES_NO | wx.NO_DEFAULT)
        try:
            dialogo.SetYesNoLabels("&Finalizar directo", "&Dejarlo al aire")
            dejar = dialogo.ShowModal() != wx.ID_YES
        finally:
            dialogo.Destroy()
        if dejar:
            anunciar("El directo sigue al aire.")
            return
        diagnostico.crear_hilo(
            lambda: _finalizar(frame, huerfanos),
            "FinalizarDirectoHuerfano").start()
    except Exception as exc:
        logger.warning("pregunta de directo huérfano: %s", exc)


def _finalizar(frame, huerfanos) -> None:
    """Finaliza cada huérfano y anuncia el resultado en la ventana."""
    try:
        datos = credenciales.cargar()
        cliente = youtube_api.ClienteYouTube(credenciales.efectivas(datos))
        try:
            for id_video, _titulo in huerfanos:
                emision.finalizar_en_youtube(cliente, id_video)
        finally:
            _guardar_token_si_hay(cliente)
    except Exception as exc:
        logger.warning("fin de directo huérfano: %s", exc)
        wx.CallAfter(_anunciar_fallo, frame)
    else:
        wx.CallAfter(_anunciar_fin, frame, len(huerfanos))


def _anunciar_fin(frame, cuantos) -> None:
    if not getattr(frame, "_alive", False):
        return
    _snd.reproducir("desconectado")
    if cuantos == 1:
        anunciar("Directo finalizado en YouTube.")
    else:
        anunciar("Directos finalizados en YouTube.")


def _anunciar_fallo(frame) -> None:
    if not getattr(frame, "_alive", False):
        return
    _snd.reproducir("error")
    anunciar("YouTube no confirmó el fin del directo. "
            "Finalízalo en YouTube Studio.")
