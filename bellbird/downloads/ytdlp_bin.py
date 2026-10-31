"""Localiza el ejecutable independiente de yt-dlp: versión, información y descargas."""

import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from bellbird.core import diagnostico
from bellbird.downloads import ffmpeg_bin
from bellbird.core import paths
from bellbird.player.esclavo_audio import TAMANIO_MINIMO
from bellbird.downloads.progreso_ytdlp import PLANTILLA, analizar_linea_progreso


TIEMPO_ESPERA = 30
LIMITE_CACHE = "300K"
# Limita la caché para no ahogar la reproducción que usa la misma conexión.
# diagnostico importa este módulo para consultar la versión de yt-dlp.
if hasattr(diagnostico, "obtener_logger"):
    logger = diagnostico.obtener_logger(__name__)
else:
    logger = logging.getLogger(f"bellbird.{__name__}")


def _ruta_actualizada() -> Path:
    return paths.ytdlp_actualizado()


def _ruta_del_paquete() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    return paths.ytdlp_empaquetado()


def ruta_ytdlp() -> str | None:
    """Devuelve la copia más reciente entre la actualizada (en data) y la
    que viaja junto al ejecutable.

    Gana la de fecha de modificación más nueva: si el usuario instala un
    paquete nuevo, su yt-dlp puede ser posterior a la copia que actualizó
    hace meses, y antes esa copia vieja ganaba siempre. A igual fecha se
    mantiene la actualizada.
    """
    candidatas = [ruta for ruta in (_ruta_actualizada(), _ruta_del_paquete())
                  if ruta is not None and ruta.is_file()]
    if not candidatas:
        return None

    def fecha(ruta: Path) -> float:
        try:
            return ruta.stat().st_mtime
        except OSError:
            return 0.0

    return str(max(candidatas, key=fecha))


def argumentos_comunes() -> list[str]:
    """Lo que cada llamada al programa suma tras su ruta.

    Ignora la configuración personal y, si hay deno empaquetado, lo
    declara como motor de JavaScript con su ruta absoluta.
    """
    comunes = ["--ignore-config"]
    deno = paths.deno_empaquetado()
    try:
        hay_deno = deno.is_file()
    except OSError:
        hay_deno = False
    if hay_deno:
        comunes.extend(["--js-runtimes", f"deno:{deno}"])
    return comunes


def version_ytdlp(ruta: str | os.PathLike) -> str:
    """Lee la versión de un ejecutable sin abrir una ventana de consola."""
    try:
        resultado = subprocess.run(
            [str(ruta), "--version"],
            capture_output=True,
            text=True,
            timeout=TIEMPO_ESPERA,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if resultado.returncode:
        return ""
    return resultado.stdout.strip()


def info_video(video_id: str) -> dict | None:
    """Datos del vídeo pedidos al programa. None si no se pudo."""
    ruta = ruta_ytdlp()
    if ruta is None:
        return None
    try:
        resultado = subprocess.run(
            [ruta, *argumentos_comunes(), "--dump-json", "--quiet",
             "--no-warnings", "--skip-download", "--no-playlist",
             "--socket-timeout", "20",
             f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True,
            text=True,
            timeout=TIEMPO_ESPERA,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        if resultado.returncode:
            return None
        datos = json.loads(resultado.stdout)
        return datos if isinstance(datos, dict) else None
    except (OSError, subprocess.SubprocessError, TypeError, ValueError):
        return None


def _argumentos_audio(ruta: str, destino: Path, video_id: str) -> list:
    return [ruta, *argumentos_comunes(), "-f", "ba", "-o", str(destino),
            "--no-playlist", "--no-warnings", "--newline",
            "--progress-template", PLANTILLA,
            f"https://www.youtube.com/watch?v={video_id}"]


def _lanzar_audio(argumentos: list):
    proceso = subprocess.Popen(
        argumentos,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        from bellbird.core.subprocesos import vincular_a_la_app
        vincular_a_la_app(proceso)
    except Exception as error:
        logger.debug("no se pudo vincular yt-dlp a la app: %s", error)
    return proceso


def _volcar_salida(proceso, cola) -> None:
    try:
        flujo = proceso.stdout
        if flujo is None:
            cola.put(None)
            return
        for linea in flujo:
            cola.put(linea)
        cola.put(None)
    except Exception:
        try:
            cola.put(None)
        except Exception as error:
            logger.debug("no se pudo avisar el fin de la salida de yt-dlp: %s", error)


def _bombear_progreso(proceso, aviso_progreso, inicio, tope_segundos) -> bool:
    """Vacía la salida de yt-dlp hasta el fin del flujo.

    Verdadero si se agotó el flujo; falso si se superó el tope y el
    proceso ya quedó terminado.
    """
    import queue
    import threading
    cola: queue.Queue = queue.Queue()
    hilo = threading.Thread(target=_volcar_salida, args=(proceso, cola), daemon=True)
    hilo.start()
    while True:
        transcurrido = time.monotonic() - inicio
        if transcurrido > tope_segundos:
            try:
                from bellbird.core.subprocesos import terminar_arbol
                terminar_arbol(proceso)
            except Exception as error:
                logger.debug("no se pudo terminar yt-dlp por tope: %s", error)
            try:
                proceso.wait(timeout=5)
            except Exception as error:
                logger.debug("no se pudo esperar el cierre de yt-dlp: %s", error)
            return False
        restante = tope_segundos - transcurrido
        espera = restante if restante < 0.2 else 0.2
        if espera <= 0:
            espera = 0.05
        try:
            linea = cola.get(timeout=espera)
        except queue.Empty:
            if proceso.poll() is not None:
                # El proceso terminó pero el lector aún no entregó el centinela;
                # se espera un poco más sin volver a bloquear indefinidamente.
                # Si el hilo ya no vive y la cola está vacía, se sale.
                if not hilo.is_alive() and cola.empty():
                    break
            continue
        if linea is None:
            break
        datos = analizar_linea_progreso(linea)
        if datos is not None and aviso_progreso is not None:
            aviso_progreso(int(datos["pct"]))
    return True


def _esperar_cierre(proceso, inicio, tope_segundos) -> bool:
    """Espera al proceso tras el fin del flujo. Falso si hay que cortarlo
    por tope."""
    # Salida normal por fin de flujo: esperar al proceso sin colgarse
    # más allá del tope.
    while True:
        if proceso.poll() is not None:
            break
        if time.monotonic() - inicio > tope_segundos:
            try:
                from bellbird.core.subprocesos import terminar_arbol
                terminar_arbol(proceso)
            except Exception as error:
                logger.debug("no se pudo terminar yt-dlp por tope: %s", error)
            try:
                proceso.wait(timeout=5)
            except Exception as error:
                logger.debug("no se pudo esperar el cierre de yt-dlp: %s", error)
            return False
        time.sleep(0.05)
    return True


def _codigo_salida(proceso):
    try:
        codigo = proceso.wait(timeout=5)
    except Exception:
        codigo = getattr(proceso, "returncode", None)
    if codigo is None:
        codigo = getattr(proceso, "returncode", 0) or 0
    return codigo


def descargar_audio(video_id: str, destino: Path, aviso_progreso=None,
                    tope_segundos: int = 600) -> bool:
    """Descarga la mejor pista de audio a la caché interna."""
    # A 6,6 megabits, 24 MB tardan 29 s y los vídeos largos superan 90 s.
    ruta = ruta_ytdlp()
    if ruta is None:
        return False
    destino = Path(destino)
    try:
        proceso = _lanzar_audio(_argumentos_audio(ruta, destino, video_id))
        inicio = time.monotonic()
        if not _bombear_progreso(proceso, aviso_progreso, inicio,
                                 tope_segundos):
            return False
        if not _esperar_cierre(proceso, inicio, tope_segundos):
            return False
        if _codigo_salida(proceso) != 0:
            logger.debug("descargar audio: yt-dlp terminó con error")
            return False
        return destino.is_file() and destino.stat().st_size >= TAMANIO_MINIMO
    except Exception as exc:
        logger.debug("descargar audio: %s", exc)
        return False


def _argumentos_video_cache(ruta: str | os.PathLike, temporal: Path, video_id: str,
                          tope_mb: int | None = None) -> list[str]:
    argumentos = [
        str(ruta), *argumentos_comunes(), "-f",
        "bv*[height<=720][protocol=https]+ba[protocol=https][ext=m4a]/b[height<=720]/bv*+ba/b",
        "-o", str(temporal), "--no-playlist",
        "--no-warnings", "--limit-rate", LIMITE_CACHE,
        "--merge-output-format", "mp4",
    ]
    # El tope se mira antes de bajar: sin esto un vídeo largo se descarga
    # entero y al podar desplaza los vídeos buenos.
    if tope_mb is not None and tope_mb > 0:
        argumentos.extend(["--max-filesize", f"{tope_mb}M"])
    ffmpeg = ffmpeg_bin.ruta_ffmpeg()
    if ffmpeg:
        argumentos.extend(["--ffmpeg-location", ffmpeg])
    argumentos.append(f"https://www.youtube.com/watch?v={video_id}")
    return argumentos


def descargar_video_cache(video_id: str, destino: Path, cancel_event=None,
                          tope_segundos: int = 3600,
                          tope_mb: int | None = None) -> bool:
    """Descarga vídeo y audio completos a un archivo local limitado."""
    ruta = ruta_ytdlp()
    if ruta is None:
        return False
    destino = Path(destino)
    temporal = None
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".ytcache-", suffix=".mp4",
                                         dir=destino.parent, delete=False) as archivo:
            temporal = Path(archivo.name)
        temporal.unlink()
        argumentos = _argumentos_video_cache(ruta, temporal, video_id, tope_mb=tope_mb)
        from bellbird.core.subprocesos import Estado, ejecutar
        estado = ejecutar(
            argumentos, cancel_event=cancel_event, tope_segundos=tope_segundos,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if estado == Estado.exito:
            if (temporal.is_file() and temporal.stat().st_size > 0
                    and (cancel_event is None or not cancel_event.is_set())):
                os.replace(temporal, destino)
                temporal = None
                return True
        return False
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("descargar vídeo de caché: %s", exc)
        return False
    finally:
        if temporal is not None:
            # Además del temporal, lo que yt-dlp deja a medias al cancelar o
            # fallar: «.ytcache-x.mp4.part», «.ytcache-x.f137.mp4»… Todos
            # comparten el tallo único del temporal, así que el glob no
            # alcanza a otra descarga.
            for resto in [temporal, *temporal.parent.glob(temporal.stem + "*")]:
                try:
                    if resto.exists():
                        resto.unlink()
                except OSError:
                    pass

