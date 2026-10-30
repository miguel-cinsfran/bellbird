"""Fines de directo pedidos a YouTube y todavía sin confirmar.

Cuando OBS deja de transmitir, Bellbird pide a YouTube que finalice el directo.
Si la red falla, el pedido se anota aquí con su fecha y se reintenta: en un
hilo mientras la app siga abierta, y al volver a abrirla si se cerró antes de
la confirmación. La E/S va aparte de la lógica para poder probar el reintento
con un reloj y un dormir falsos.
"""

from __future__ import annotations

import threading
from datetime import datetime

from bellbird.core import archivos, config
from bellbird.core import diagnostico
from bellbird.core.idioma import _

logger = diagnostico.obtener_logger(__name__)

# Cada cuánto se reintenta el fin del directo y cuándo se deja de intentar.
INTERVALO_REINTENTO = 15.0
LIMITE_REINTENTO = 600.0


def leer(ruta) -> list[dict]:
    """Lista de pendientes del JSON.

    Un archivo que falta, está roto o no es una lista se lee como lista
    vacía, sin lanzar: no hay que perder la revisión por un archivo ajeno.
    Se descartan las entradas sin id.
    """
    datos = archivos.leer_json(ruta, [])
    if not isinstance(datos, list):
        return []
    return [entrada for entrada in datos
            if isinstance(entrada, dict) and entrada.get("id")]


def anotar(ruta, id_video, ahora=None) -> list[dict]:
    """Anota el id con la fecha en que se pidió, sin duplicar.

    Si el id ya está, devuelve la lista tal cual sin reescribir. Con un id
    vacío no toca el archivo.
    """
    id_video = (id_video or "").strip()
    pendientes = leer(ruta)
    if not id_video or any(e["id"] == id_video for e in pendientes):
        return pendientes
    momento = ahora or datetime.now()
    pendientes.append({"id": id_video,
                       "fecha": momento.isoformat(timespec="seconds")})
    archivos.escribir_json_atomico(ruta, pendientes, indent=1)
    return pendientes


def quitar(ruta, id_video) -> list[dict]:
    """Quita el id del archivo y devuelve la lista restante.

    Solo reescribe si el id estaba: no crea un archivo por una baja que no
    cambió nada.
    """
    id_video = (id_video or "").strip()
    original = leer(ruta)
    restantes = [e for e in original if e["id"] != id_video]
    if len(restantes) != len(original):
        archivos.escribir_json_atomico(ruta, restantes, indent=1)
    return restantes


def reintentar(intento, dormir, reloj, intervalo=INTERVALO_REINTENTO,
               limite=LIMITE_REINTENTO) -> bool:
    """Reintenta `intento()` cada `intervalo` hasta lograrlo o rendirse.

    El plazo corre desde la primera llamada, que es el fallo que disparó el
    reintento. `intento` lanza si el fin todavía no se confirmó. Cada fallo
    se registra. Devuelve True si algún intento salió bien.
    """
    inicio = reloj()
    while True:
        dormir(intervalo)
        try:
            intento()
        except Exception as error:
            logger.info("reintento del fin del directo falló: %s", error)
        else:
            return True
        if reloj() - inicio >= limite:
            return False


class CierreYoutube:
    """Pide a YouTube el fin del directo y lo reintenta si falla la red.

    Guarda la marca de una sola vez por emisión: `reiniciar` la baja al
    empezar una emisión nueva. `anunciar`, `dormir` y `reloj` son los del
    supervisor, para decir lo mismo y probar el reintento con dobles.
    """

    def __init__(self, finalizar, ruta_pendiente, anunciar, dormir, reloj):
        self._finalizar = finalizar
        self._ruta = ruta_pendiente
        self._anunciar = anunciar
        self._dormir = dormir
        self._reloj = reloj
        self._cerrojo = threading.Lock()
        self._hecho = False

    def reiniciar(self) -> None:
        with self._cerrojo:
            self._hecho = False

    def finalizar_si_toca(self, id_video) -> None:
        # Cierra el directo en YouTube una sola vez por emisión, solo con
        # id de vídeo (los directos de TikTok no tienen). El id se anota
        # antes de pedirlo: si la red falla, el pedido sobrevive al cierre
        # en el archivo de fines pendientes. Con la ruta en None no se toca
        # el disco y no se lanza reintento.
        gancho = self._finalizar
        if gancho is None or not id_video:
            return
        if not self._marcar():
            return
        self._anotar(id_video)
        try:
            gancho(id_video)
        except Exception as error:
            self._avisar_fallo(id_video, error)
        else:
            self._quitar(id_video)

    def _marcar(self) -> bool:
        with self._cerrojo:
            if self._hecho:
                return False
            self._hecho = True
            return True

    def _avisar_fallo(self, id_video, error) -> None:
        try:
            self._anunciar(
                _("YouTube no confirmó el fin del directo. Se reintentará durante 10 minutos."),
                "transmision_problema")
        except Exception as error_anuncio:
            logger.debug("no se pudo anunciar el fallo de cierre en YouTube: %s", error_anuncio)
        logger.warning("no se pudo finalizar la emisión %s: %s",
                       id_video, error)
        self._lanzar_reintento(id_video)

    def _anotar(self, id_video) -> None:
        if self._ruta is None:
            return
        try:
            anotar(self._ruta, id_video)
        except Exception as error:
            logger.debug("no se pudo anotar el fin pendiente: %s", error)

    def _quitar(self, id_video) -> None:
        if self._ruta is None:
            return
        try:
            quitar(self._ruta, id_video)
        except Exception as error:
            logger.debug("no se pudo quitar el fin pendiente: %s", error)

    def _lanzar_reintento(self, id_video) -> None:
        # Sin archivo no hay nada que sobreviva a un cierre de la app, así
        # que no se abre un reintento a ciegas: la ruta la pone quien usa
        # el supervisor en producción.
        if self._ruta is None:
            return
        try:
            diagnostico.crear_hilo(
                lambda: self._reintentar(id_video),
                "ReintentarFinDirecto").start()
        except Exception as error:
            logger.warning("no se pudo lanzar el reintento del fin: %s", error)

    def _reintentar(self, id_video) -> None:
        def intento():
            self._finalizar(id_video)

        if reintentar(intento, self._dormir, self._reloj):
            self._quitar(id_video)
            try:
                self._anunciar(_("Directo finalizado en YouTube."), "directo_finalizado")
            except Exception as error:
                logger.debug("no se pudo anunciar el directo finalizado: %s", error)
        else:
            try:
                frase = _("YouTube sigue sin confirmar el fin del directo. "
                          "Se intentará de nuevo al abrir {app}.")
                self._anunciar(frase.format(app=config.APP_NAME), "transmision_problema")
            except Exception as error:
                logger.debug("no se pudo anunciar el reintento del fin del directo: %s", error)
