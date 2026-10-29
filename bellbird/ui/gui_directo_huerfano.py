"""Revisión al arranque de directos que quedaron al aire sin imagen.

Los directos se crean sin autoStop: si la persona cierra Bellbird y después
OBS, el directo queda al aire sin imagen hasta que alguien lo finalice.
Al arrancar, este módulo revisa una sola vez si la cuenta tiene un
directo al aire atado a su clave mientras OBS no transmite, y pregunta
si finalizarlo. Nunca lo finaliza solo: la misma clave puede usarse
desde otro programa.
"""

from __future__ import annotations

import time

import wx

from bellbird.core import config
from bellbird.core import diagnostico
from bellbird.core import paths
from bellbird.core.idioma import _
from bellbird.obs import obs_activacion
from bellbird.obs.obs_panel import GestorPanelObs
from bellbird.ui.accesibilidad import anunciar
from bellbird.voice import sound_player as _snd
from bellbird.youtube import credenciales, emision, fin_pendiente, youtube_api

logger = diagnostico.obtener_logger(__name__)


def directos_sin_imagen(activas, id_flujo, obs_transmite,
                        excluir=None) -> list[tuple]:
    """Pares (id, título) de las activas atadas a la clave, sin imagen.

    Vacía si OBS transmite o si no hay clave reutilizable: en el primer
    caso hay imagen, en el segundo no hay nada a lo que atar. Los ids en
    `excluir` ya están en camino de terminarse y no se preguntan.
    """
    if obs_transmite or not id_flujo:
        return []
    excluidos = set(excluir or ())
    return [(id_video, titulo) for id_video, atado, titulo in activas
            if atado == id_flujo and id_video not in excluidos]


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


def _obs_transmite() -> tuple[bool, str]:
    """(transmite, motivo) del estado de OBS ahora mismo.

    Si OBS no corre, (False, ...). Si corre pero el websocket no responde,
    (True, ...) por la duda: no se molesta a nadie preguntando.
    """
    if not obs_activacion.obs_esta_en_ejecucion():
        return False, "OBS no está en ejecución"
    try:
        gestor = GestorPanelObs()
        try:
            gestor.conectar()
            activo = bool(
                gestor.estado_transmision().get("outputActive", False))
        finally:
            try:
                gestor.cerrar()
            except Exception:
                pass
    except Exception:
        return True, "el websocket de OBS no respondió"
    if activo:
        return True, "OBS está transmitiendo"
    return False, "OBS está abierto y no transmite"


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


def _quitar_pendiente(ruta, id_video) -> None:
    try:
        fin_pendiente.quitar(ruta, id_video)
    except Exception as exc:
        logger.warning("fin pendiente: no se pudo quitar %s: %s",
                       id_video, exc)


def _terminar_pendientes(frame, cliente) -> list[str]:
    """Finaliza los directos con fin pendiente antes de buscar huérfanos.

    Devuelve sus ids para excluirlos de la pregunta: ya están en camino de
    terminarse, preguntar por ellos sería pedir dos veces lo mismo.
    """
    ruta = paths.fin_pendiente()
    pendientes = fin_pendiente.leer(ruta)
    ids = [entrada["id"] for entrada in pendientes]
    avisado = False
    for id_video in ids:
        try:
            emision.finalizar_en_youtube(cliente, id_video)
        except Exception as exc:
            logger.info("fin pendiente: %s no se confirmó (%s), "
                        "se reintenta", id_video, exc)
            if not avisado:
                wx.CallAfter(_anunciar_reintento_pendiente, frame)
                avisado = True
            _reintentar_en_hilo(frame, id_video, ruta)
        else:
            _quitar_pendiente(ruta, id_video)
            wx.CallAfter(_anunciar_fin_pendiente, frame)
    return ids


def _consultar(frame) -> None:
    """Consulta en el hilo de trabajo y agenda la pregunta si hace falta.

    Sin sesión no pide nada a la API. No toca wx salvo `wx.CallAfter`:
    la ventana solo se toca en el hilo principal, desde `_preguntar`.
    Cada salida sin pregunta deja en el registro qué encontró.
    """
    try:
        datos = credenciales.cargar()
        if not credenciales.hay_sesion(datos):
            logger.info("revisión de directo huérfano: sin sesión, "
                        "no se revisa")
            return
        cliente = youtube_api.ClienteYouTube(credenciales.efectivas(datos))
        try:
            pendientes = _terminar_pendientes(frame, cliente)
            obs_transmite, motivo_obs = _obs_transmite()
            logger.info("revisión de directo huérfano: %s", motivo_obs)
            activas = cliente.emisiones_activas()
            flujo = cliente.flujo_reutilizable()
            id_flujo = flujo[0] if flujo else ""
            if id_flujo:
                logger.info(
                    "revisión de directo huérfano: clave reutilizable %s, "
                    "%d directos activos %s", id_flujo, len(activas),
                    [(id_video, atado) for id_video, atado, _t in activas])
            else:
                logger.info(
                    "revisión de directo huérfano: sin clave reutilizable, "
                    "%d directos activos %s", len(activas),
                    [(id_video, atado) for id_video, atado, _t in activas])
            huerfanos = directos_sin_imagen(
                activas, id_flujo, obs_transmite, excluir=pendientes)
        finally:
            _guardar_token_si_hay(cliente)
        if huerfanos:
            logger.info("revisión de directo huérfano: se pregunta por %s",
                        [id_video for id_video, _t in huerfanos])
            wx.CallAfter(_preguntar, frame, huerfanos)
    except Exception as exc:
        logger.warning("revisión de directo huérfano: %s", exc)


def _preguntar(frame, huerfanos) -> None:
    """Pregunta en el hilo de la ventana si se finaliza el directo."""
    try:
        if not getattr(frame, "_alive", False):
            logger.info("revisión de directo huérfano: la ventana se cerró, no se pregunta")
            return
        if frame._supervisar_transmision("activo"):
            logger.info("revisión de directo huérfano: hay una transmisión "
                        "propia activa, no se pregunta")
            return
        if len(huerfanos) == 1:
            texto = (_("Tu directo «{titulo}» sigue al aire en "
                       "YouTube, pero OBS no está transmitiendo. "
                       "Quienes lo miran no ven nada. ¿Finalizarlo?").format(
                           titulo=huerfanos[0][1]))
        else:
            texto = (_("Tienes {cuantos} directos al aire en YouTube "
                       "sin imagen, porque OBS no está transmitiendo. "
                       "¿Finalizarlos?").format(cuantos=len(huerfanos)))
        dialogo = wx.MessageDialog(
            frame, texto, _("Directo sin imagen"), wx.YES_NO | wx.NO_DEFAULT)
        try:
            dialogo.SetYesNoLabels(_("&Finalizar directo"), _("&Dejarlo al aire"))
            dejar = dialogo.ShowModal() != wx.ID_YES
        finally:
            dialogo.Destroy()
        if dejar:
            logger.info("revisión de directo huérfano: el usuario dejó %d "
                        "directos al aire", len(huerfanos))
            anunciar(_("El directo sigue al aire."))
            return
        logger.info("revisión de directo huérfano: el usuario pidió finalizar "
                    "%d directos", len(huerfanos))
        diagnostico.crear_hilo(
            lambda: _finalizar(frame, huerfanos),
            "FinalizarDirectoHuerfano").start()
    except Exception as exc:
        logger.warning("pregunta de directo huérfano: %s", exc)


def _reintentar_en_hilo(frame, id_video, ruta) -> None:
    try:
        diagnostico.crear_hilo(
            lambda: _reintentar_pendiente(frame, id_video, ruta),
            "ReintentarFinDirecto").start()
    except Exception as exc:
        logger.warning("reintento de fin pendiente: %s", exc)


def _reintentar_pendiente(frame, id_video, ruta) -> None:
    """Reintenta el fin de un pendiente y anuncia el resultado."""
    try:
        datos = credenciales.cargar()
        cliente = youtube_api.ClienteYouTube(credenciales.efectivas(datos))
        try:
            exito = fin_pendiente.reintentar(
                lambda: emision.finalizar_en_youtube(cliente, id_video),
                time.sleep, time.monotonic)
        finally:
            _guardar_token_si_hay(cliente)
    except Exception as exc:
        logger.warning("reintento de fin pendiente: %s", exc)
        return
    if exito:
        _quitar_pendiente(ruta, id_video)
        wx.CallAfter(_anunciar_fin_pendiente, frame)
    else:
        wx.CallAfter(_anunciar_fallo_pendiente, frame)


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
        anunciar(_("Directo finalizado en YouTube."))
    else:
        anunciar(_("Directos finalizados en YouTube."))


def _anunciar_fallo(frame) -> None:
    if not getattr(frame, "_alive", False):
        return
    _snd.reproducir("error")
    anunciar(_("YouTube no confirmó el fin del directo. Finalízalo en YouTube Studio."))


def _anunciar_fin_pendiente(frame) -> None:
    if not getattr(frame, "_alive", False):
        return
    _snd.reproducir("directo_finalizado")
    anunciar(_("Directo finalizado en YouTube."))


def _anunciar_fallo_pendiente(frame) -> None:
    if not getattr(frame, "_alive", False):
        return
    _snd.reproducir("transmision_problema")
    anunciar(_("YouTube sigue sin confirmar el fin del directo. "
              "Se intentará de nuevo al abrir {app}.").format(
                  app=config.APP_NAME))


def _anunciar_reintento_pendiente(frame) -> None:
    if not getattr(frame, "_alive", False):
        return
    _snd.reproducir("transmision_problema")
    anunciar(_("YouTube no confirmó el fin del directo. Se reintentará durante 10 minutos."))
