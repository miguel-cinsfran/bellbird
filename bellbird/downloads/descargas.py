"""Gestor de descargas con yt-dlp (módulo puro, sin wx).

Frontera pura/plataforma: este módulo no importa `wx` ni el módulo de yt-dlp.

NO se acopla con las 2 llamadas yt-dlp existentes en `main.obtener_info_video`
ni en `reproductor._info_video`: este módulo hace sus PROPIAS llamadas a
el programa independiente, en su propio hilo.

Modos soportados:
  - mp4  : bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best
  - webm : bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best
  - mp3  : bestaudio/best + conversión a mp3
  - m4a  : bestaudio/best + conversión a m4a
"""
from __future__ import annotations

import logging
import json
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

from bellbird.core import diagnostico
from bellbird.core.config import obtener_opciones_descarga
from bellbird.core import paths
from bellbird.core.idioma import _
from bellbird.downloads import ffmpeg_bin
from bellbird.downloads import fila_descargas
from bellbird.downloads import ytdlp_bin
from bellbird.downloads.argumentos_ytdlp import argumentos_descarga, construir_outtmpl, formato_a_ydl
from bellbird.downloads.motivo_error import motivo_de_error
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

# Tope del análisis previo de la URL: sin él, una red caída dejaba el ítem
# «en cola» para siempre.
TIEMPO_ESPERA_ANALISIS = 60


def _matar_arbol(proceso) -> None:
    """Mata a yt-dlp Y a su ffmpeg hijo. En Windows kill() solo mata al
    padre: el ffmpeg que estaba uniendo audio y vídeo seguía vivo y escribiendo
    en la carpeta. taskkill /T baja el árbol entero; kill() queda de red."""
    pid = getattr(proceso, "pid", None)
    if os.name == "nt" and isinstance(pid, int):
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)],
                           capture_output=True, timeout=10, check=False,
                           creationflags=_sin_ventana())
        except Exception as exc:
            logger.debug("taskkill: %s", exc)
    try:
        proceso.kill()
    except Exception as exc:
        logger.debug("kill: %s", exc)


def _vigilar_cancelacion(proceso, cancel_event, intervalo=0.2) -> bool:
    while proceso.poll() is None:
        if cancel_event.wait(intervalo):
            _matar_arbol(proceso)
            return True
    return False


def recortar_url_registro(url: str) -> str:
    """Devuelve el identificador de vídeo sin parámetros para el registro."""
    partes = urlparse(url)
    consulta = parse_qs(partes.query)
    if consulta.get("v"):
        return consulta["v"][0]
    segmentos = [segmento for segmento in partes.path.split("/") if segmento]
    if partes.netloc.lower().endswith("youtu.be") and segmentos:
        return segmentos[0]
    if len(segmentos) >= 2 and segmentos[0] in ("shorts", "embed", "live"):
        return segmentos[1]
    return segmentos[-1] if segmentos else "sin identificador"

def analizar_url(url: str) -> dict:
    """Inspecciona una URL y devuelve tipo / id / título / cuenta.

    Pide los datos al programa independiente. Si no está disponible, devuelve
    el mismo error que se informaba cuando faltaba el módulo de Python.
    """
    ruta = ytdlp_bin.ruta_ytdlp()
    if ruta is None:
        return {"tipo": "error", "id": "", "titulo": "", "cuenta": 0,
                "mensaje": _("yt-dlp no está instalado")}
    # -J (un único JSON) y --flat-playlist: --dump-json emitía un JSON por
    # entrada en las playlists y json.loads fallaba con «Extra data».
    try:
        resultado = subprocess.run(
            [ruta, "-J", "--flat-playlist", "--quiet", "--no-warnings",
             "--skip-download", "--no-playlist", "--socket-timeout", "20", url],
            capture_output=True, text=True, creationflags=_sin_ventana(),
            check=False, timeout=TIEMPO_ESPERA_ANALISIS,
        )
        if resultado.returncode:
            return {"tipo": "error", "id": "", "titulo": "", "cuenta": 0,
                    "mensaje": resultado.stderr.strip() or _("yt-dlp falló")}
        info = json.loads(resultado.stdout)
    except (OSError, subprocess.SubprocessError, TypeError, ValueError) as exc:
        logger.warning("analizar_url falló: %s", exc)
        return {"tipo": "error", "id": "", "titulo": "", "cuenta": 0,
                "mensaje": str(exc)}
    if not info:
        return {"tipo": "error", "id": "", "titulo": "", "cuenta": 0,
                "mensaje": _("Enlace vacío")}
    tipo = info.get("_type")
    if tipo == "playlist" or "entries" in info:
        return {"tipo": "playlist",
                "id": info.get("id", ""),
                "titulo": info.get("title", ""),
                "cuenta": len(info.get("entries") or [])}
    return {"tipo": "video",
            "id": info.get("id", ""),
            "titulo": info.get("title", ""),
            "cuenta": 1}


def _sin_ventana() -> int:
    """Evita una ventana de consola en Windows al ejecutar yt-dlp."""
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


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
    carpeta = Path(construir_outtmpl(opciones, enumerar)).parent
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


def frase_aviso_descarga(estado: str, mensaje: str, nombre: str) -> str:
    """Devuelve el aviso accesible de un fin de descarga."""
    if estado == "completado":
        if mensaje:
            return _("Descarga completada: {nombre}, {mensaje}").format(
                nombre=nombre, mensaje=mensaje)
        return (_("Descarga completada: {nombre}").format(nombre=nombre)
                if nombre else _("Descarga completada"))
    if estado == "parcial":
        return _("Descarga con errores: {nombre}, {mensaje}").format(
            nombre=nombre, mensaje=mensaje)
    if estado == "error":
        return (_("Error en la descarga: {mensaje}").format(mensaje=mensaje) if mensaje else _("Error en la descarga"))
    if estado == "cancelado":
        return _("Descarga cancelada")
    return ""


# ── Gestor de cola ───────────────────────────────────────────────────────────

# Como mucho dos descargas corren a la vez: la PC que usa la app tiene
# cuatro núcleos y 7,83 GiB, y diez yt-dlp a la vez la dejan sin resto.
DESCARGAS_SIMULTANEAS = 2
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
        self._turnos = threading.Semaphore(DESCARGAS_SIMULTANEAS)
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
        # Espera el turno antes de analizar: el semáforo acota cuántos corren
        # y la fila impone el orden. Si cancelan, vuelve sin tomar el turno.
        while True:
            if ev.is_set():
                return False
            with self._lock:
                bloqueado = fila_descargas.bloqueado_por_anterior(
                    item_id, self._orden, self._empezados, self._items,
                    self._eventos)
            if not bloqueado:
                if self._turnos.acquire(timeout=0.2):
                    with self._lock:
                        self._empezados.add(item_id)
                    return True
            else:
                ev.wait(0.02)

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

        Como mucho DESCARGAS_SIMULTANEAS corren a la vez; las demás esperan
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
                    logger.info("descarga %s: inicio", item_id)
                    descargar(url, opciones, _cb_progreso, _cb_estado, ev,
                              _cb_detalle)
                finally:
                    if tomado:
                        self._turnos.release()
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
