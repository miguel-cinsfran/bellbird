"""Gestor de descargas con yt-dlp (módulo puro, sin wx).

Frontera pura/plataforma: este módulo no importa `wx` ni el módulo de yt-dlp.

NO se acopla con las 2 llamadas yt-dlp existentes en `main.obtener_info_video`
ni en `reproductor._info_video`: este módulo hace sus PROPIAS llamadas a
el programa independiente, en su propio hilo.

Modos soportados: los nueve de `opciones_formato.FORMATOS`, con sus
argumentos en `argumentos_ytdlp.argumentos_de_formato`.
"""
from __future__ import annotations

import logging
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

from bellbird.core import diagnostico
from bellbird.core.config import obtener_opciones_descarga
from bellbird.core import paths
from bellbird.core.idioma import _
from bellbird.downloads import ffmpeg_bin
from bellbird.downloads import fila_descargas
from bellbird.downloads import ytdlp_bin
from bellbird.downloads.analisis_enlace import (
    TIEMPO_ESPERA_ANALISIS, analizar_url, _sin_ventana)
from bellbird.downloads.opciones_formato import SIMULTANEAS_DEFECTO
from bellbird.downloads.argumentos_ytdlp import (
    argumentos_descarga, carpeta_base, construir_outtmpl, recortar_url_registro)
from bellbird.downloads.motivo_error import motivo_de_error
from bellbird.downloads.proceso_ytdlp import (
    _matar_arbol, _vigilar_cancelacion)
from bellbird.downloads.progreso_ytdlp import (
    INTERVALO_PROGRESO_S, PREFIJO_RUTA_FINAL, debe_emitir_progreso,
    tratar_linea)
from bellbird.downloads.restos_descarga import (
    limpiar_restos_descarga, nombre_base_descarga)

logger = diagnostico.obtener_logger(__name__)

@dataclass
class ItemDescarga:
    """Una descarga encolada. El estado se va mutando desde el hilo de descarga."""
    id: str
    url: str
    tipo: str                # "video" | "playlist" | "error"
    estado: str = "en_cola"  # en_cola | descargando | completado | error | cancelado
    progreso: float = 0.0    # 0..100
    mensaje: str = ""
    nombre: str = ""
    carpeta: str = ""        # destino elegido al encolar (para el historial)
    rutas: list[str] = field(default_factory=list)
    indice: int = 0
    total: int = 0
    procesando: bool = False
    velocidad: float | None = None
    eta: int | None = None


# ── Helpers puros (testeables en Linux) ──────────────────────────────────────


def descargar(url: str, opciones: dict,
              progreso_cb: Callable, estado_cb: Callable,
              cancel_event: threading.Event, al_detalle=None) -> None:
    """Lanza la descarga en el HILO ACTUAL.

    Pensada para correr dentro de `threading.Thread(target=descargar, ...)` que
    crea `GestorDescargas.encolar`. El hilo SIEMPRE termina: las excepciones se
    convierten en `estado_cb("error" | "cancelado", mensaje)` y se hace
    `return`. NUNCA se re-lanza fuera del hilo.

    Callbacks:
      - progreso_cb(pct: float, velocidad, eta, nombre): se invoca desde el
        progress hook de yt-dlp cada vez que hay actualización de bytes.
      - estado_cb(estado: str, mensaje: str): transiciones de estado: primero
        "descargando", luego uno de "completado" | "parcial" | "cancelado" |
        "error".
      - al_detalle(cambios: dict): opcional; avisa la ruta de cada archivo
        terminado, el índice y el total de la lista, y si yt-dlp procesa.
    """
    ruta = ytdlp_bin.ruta_ytdlp()
    if ruta is None:
        estado_cb("error", _("yt-dlp no está instalado"))
        return

    if not tiene_ffmpeg():
        # Error CLARO (no el genérico de yt-dlp) para que el usuario ciego
        # sepa exactamente qué falta. La GUI ya hace 3-vías con este mensaje.
        estado_cb("error",
                   _("ffmpeg no encontrado. La descarga necesita ffmpeg para "
                     "unir audio y vídeo o extraer audio. Usa la versión "
                     "empaquetada o instala ffmpeg. En desarrollo, alcanza "
                     "con tener ffmpeg en el PATH."))
        return

    enumerar = bool(opciones.get("enumerar", False))
    carpeta = carpeta_base(opciones)
    al_detalle = al_detalle or (lambda _cambios: None)
    estado = {"ultimo_error": "", "ultimo_archivo": "", "ultimo_ts": None,
              "rutas": [], "indice": 0, "total": 0, "procesando": False}

    def cancelar(proceso) -> None:
        _matar_arbol(proceso)
        proceso.wait()
        borrados = limpiar_restos_descarga(carpeta, estado["ultimo_archivo"])
        if borrados:
            logger.info("descarga cancelada: borrados %d restos", len(borrados))
        estado_cb("cancelado", _("Descarga cancelada"))

    estado_cb("descargando", "")
    try:
        proceso = subprocess.Popen(
            [ruta, *argumentos_descarga(url, opciones, enumerar)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            encoding="utf-8", errors="replace",
            creationflags=_sin_ventana(),
        )
        try:
            from bellbird.core.subprocesos import vincular_a_la_app
            vincular_a_la_app(proceso)
        except Exception as error:
            logger.debug("no se pudo vincular la descarga a la app: %s", error)
        if cancel_event.is_set():
            cancelar(proceso)
            return
        diagnostico.crear_hilo(
            _vigilar_cancelacion, "Vigilante-cancelacion",
            args=(proceso, cancel_event),
        ).start()
        for linea in iter(proceso.stdout.readline, ""):
            if cancel_event.is_set():
                cancelar(proceso)
                return
            tratar_linea(linea, estado, progreso_cb, al_detalle)
        proceso.wait()
        if cancel_event.is_set():
            limpiar_restos_descarga(carpeta, estado["ultimo_archivo"])
            estado_cb("cancelado", _("Descarga cancelada"))
        elif proceso.returncode == 0:
            hechos = len(estado["rutas"])
            if estado["total"] > 1:
                estado_cb("completado",
                          _("{hechos} vídeos").format(hechos=hechos))
            else:
                estado_cb("completado", "")
        else:
            codigo = proceso.returncode
            motivo = (motivo_de_error(estado["ultimo_error"])
                      or _("yt-dlp terminó con código {codigo}").format(codigo=codigo))
            if estado["ultimo_error"]:
                logger.warning("yt-dlp terminó con código %s: %s",
                               codigo, estado["ultimo_error"])
            hechos = len(estado["rutas"])
            if hechos >= 1 and estado["total"] > 1:
                estado_cb("parcial", _("{hechos} de {total} vídeos").format(
                    hechos=hechos, total=estado["total"]))
            else:
                estado_cb("error", motivo)
    except OSError as exc:
        logger.warning("descargar falló: %s", exc)
        estado_cb("error", str(exc) or exc.__class__.__name__)
    except Exception as exc:
        logger.warning("descargar falló: %s", exc)
        estado_cb("error", str(exc) or exc.__class__.__name__)


def tiene_ffmpeg() -> bool:
    """¿Hay ffmpeg disponible? El mismo resolvedor que usa la descarga."""
    return ffmpeg_bin.ruta_ffmpeg() is not None


# ── Gestor de cola ───────────────────────────────────────────────────────────

# La velocidad y el tiempo restante cambian muy seguido: escribirlos en el
# ítem cada 500 ms haría hablar al lector sin parar.
INTERVALO_VELOCIDAD_S = 3.0

class GestorDescargas:
    """Cola de descargas. Cada ítem corre en su propio hilo (daemon).

    Los callbacks que recibe `encolar` llevan el `item_id` como primer
    argumento, así la capa de GUI puede actualizar la fila correspondiente
    de su `wx.ListCtrl` sin tener que mantener un mapping externo.
    """

    def __init__(self, opciones: Optional[dict] = None) -> None:
        self._opciones: dict = dict(opciones) if opciones else obtener_opciones_descarga()
        self._items: dict[str, ItemDescarga] = {}
        self._eventos: dict[str, threading.Event] = {}
        self._orden: list[str] = []
        self._suscriptores_fin: list[Callable] = []
        self._lock = threading.Lock()
        self._corriendo = 0
        self._empezados: set[str] = set()

    def set_opciones(self, op: dict) -> None:
        """Reemplaza las opciones para lo que se encole después."""
        with self._lock:
            self._opciones = dict(op)

    def suscribir_fin(self, callback: Callable) -> None:
        """Añade un aviso de estado sin duplicarlo.

        `callback(estado, mensaje, nombre, item)` corre en el HILO DE DESCARGA:
        quien toque wx debe pasar por wx.CallAfter. Recibe el ItemDescarga
        para que el historial se registre aunque el diálogo esté cerrado.
        """
        with self._lock:
            if callback not in self._suscriptores_fin:
                self._suscriptores_fin.append(callback)

    def _esperar_turno(self, item_id, ev) -> bool:
        # Espera el turno antes de analizar: el contador acota cuántos corren
        # y la fila impone el orden. Si cancelan, vuelve sin tomar el turno.
        while True:
            if ev.is_set():
                return False
            with self._lock:
                bloqueado = fila_descargas.bloqueado_por_anterior(
                    item_id, self._orden, self._empezados, self._items,
                    self._eventos)
                tope = self._opciones.get("simultaneas", SIMULTANEAS_DEFECTO)
                if not bloqueado and self._corriendo < tope:
                    self._corriendo += 1
                    self._empezados.add(item_id)
                    return True
            if bloqueado:
                ev.wait(0.02)
            else:
                ev.wait(0.2)

    def _avisar_estado(self, it, estado, mensaje, estado_cb) -> None:
        it.estado = estado
        it.mensaje = mensaje
        logger.info("descarga %s: estado %s", it.id, estado)
        try:
            estado_cb(it.id, estado, mensaje)
        except Exception as exc:
            logger.debug("estado_cb lanzó: %s", exc)
        nombre = it.nombre if it.nombre != it.url else ""
        with self._lock:
            suscriptores = list(self._suscriptores_fin)
        for suscriptor in suscriptores:
            try:
                suscriptor(estado, mensaje, nombre, it)
            except Exception as exc:
                logger.warning("suscriptor de descarga lanzó: %s", exc)
        if estado in ("completado", "parcial", "cancelado", "error"):
            logger.info("descarga %s terminó: %s", it.id, estado)

    def encolar(self, url: str, progreso_cb: Callable, estado_cb: Callable,
                creado_cb: Optional[Callable] = None) -> str:
        """Crea un ItemDescarga, lo deja en 'en_cola' y lanza su hilo.

        Como mucho las simultáneas elegidas corren a la vez; las demás esperan
        en 'en_cola', en el orden en que se encolaron, y se pueden cancelar
        mientras esperan.

        `progreso_cb(item_id, pct, velocidad, eta, nombre)` y
        `estado_cb(item_id, estado, mensaje)` reciben el id del ítem.
        """
        item_id = uuid.uuid4().hex[:12]
        with self._lock:
            opciones = dict(self._opciones)
        it = ItemDescarga(id=item_id, url=url, tipo="video", nombre=url,
                          carpeta=str(opciones.get("carpeta") or ""))
        ev = threading.Event()
        with self._lock:
            self._items[item_id] = it
            self._eventos[item_id] = ev
            self._orden.append(item_id)
        logger.info("descarga encolada: %s, vídeo %s", item_id,
                    recortar_url_registro(url))
        if creado_cb is not None:
            creado_cb(item_id)

        def _cb_estado(estado: str, mensaje: str = "") -> None:
            self._avisar_estado(it, estado, mensaje, estado_cb)

        ultimo_detalle_ts = [None]

        def _cb_progreso(pct: float, vel, eta, nombre: str) -> None:
            it.progreso = max(0.0, min(100.0, float(pct)))
            if nombre and not (it.tipo == "playlist" and it.nombre != it.url):
                it.nombre = nombre
            if isinstance(vel, (int, float)) or isinstance(eta, (int, float)):
                ahora = time.monotonic()
                if (ultimo_detalle_ts[0] is None
                        or ahora - ultimo_detalle_ts[0] >= INTERVALO_VELOCIDAD_S):
                    it.velocidad, it.eta = vel, eta
                    ultimo_detalle_ts[0] = ahora
            try:
                progreso_cb(item_id, it.progreso, vel, eta, it.nombre)
            except Exception as exc:
                logger.debug("progreso_cb lanzó: %s", exc)

        def _cb_detalle(cambios: dict) -> None:
            if "ruta" in cambios:
                it.rutas.append(cambios["ruta"])
            for clave in ("indice", "total", "procesando"):
                if clave in cambios:
                    setattr(it, clave, cambios[clave])

        def _run() -> None:
            # Doble red de seguridad: capturar lo que sea que se escape.
            tomado = False
            try:
                tomado = self._esperar_turno(item_id, ev)
                if not tomado:
                    _cb_estado("cancelado", _("Descarga cancelada"))
                    return
                try:
                    info = analizar_url(url)
                    it.tipo = info.get("tipo", "video")
                    it.total = int(info.get("cuenta") or 0)
                    titulo = info.get("titulo") or ""
                    if titulo:
                        _cb_progreso(it.progreso, "", "", titulo)
                    if ev.is_set():
                        # Cancelada durante el análisis: no lanzar yt-dlp para nada.
                        _cb_estado("cancelado", _("Descarga cancelada"))
                        return
                    if info.get("en_directo"):
                        _cb_estado("error", _("Un directo en curso no se puede descargar."))
                        return
                    logger.info("descarga %s: inicio", item_id)
                    opciones_descarga = dict(opciones)
                    opciones_descarga["es_lista"] = (it.tipo == "playlist")
                    descargar(url, opciones_descarga, _cb_progreso, _cb_estado, ev,
                              _cb_detalle)
                finally:
                    if tomado:
                        with self._lock:
                            self._corriendo -= 1
            except Exception as exc:
                logger.warning("hilo descarga: %s", exc)
                _cb_estado("error", str(exc) or exc.__class__.__name__)

        hilo = diagnostico.crear_hilo(_run, f"Descarga-{item_id}")
        hilo.start()
        return item_id

    def cancelar(self, item_id: str) -> None:
        """Marca el evento de cancelación para que termine el proceso."""
        ev = self._eventos.get(item_id)
        if ev is not None:
            ev.set()

    def olvidar(self, item_id: str) -> None:
        """Saca un ítem terminado de la cola. Si sigue activo no hace nada."""
        with self._lock:
            item = self._items.get(item_id)
            if item is None or item.estado not in ("completado", "parcial",
                                                   "cancelado", "error"):
                return
            self._items.pop(item_id, None)
            if item_id in self._orden:
                self._orden.remove(item_id)
            self._eventos.pop(item_id, None)
            self._empezados.discard(item_id)

    def obtener(self, item_id: str) -> Optional[ItemDescarga]:
        with self._lock:
            return self._items.get(item_id)

    def lista(self) -> list[ItemDescarga]:
        with self._lock:
            return [self._items[i] for i in self._orden if i in self._items]


_gestor_unico: Optional[GestorDescargas] = None
_lock_gestor_unico = threading.Lock()


def gestor() -> GestorDescargas:
    """Devuelve el gestor de descargas compartido por la aplicación."""
    global _gestor_unico
    with _lock_gestor_unico:
        if _gestor_unico is None:
            _gestor_unico = GestorDescargas()
        return _gestor_unico


def reiniciar_gestor() -> None:
    """Descarta el gestor compartido. Solo se usa en las pruebas."""
    global _gestor_unico
    with _lock_gestor_unico:
        _gestor_unico = None
