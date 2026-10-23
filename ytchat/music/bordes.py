"""Bordes de sonido de la música local, sin interfaz.

Muchas canciones traen segundos de silencio al principio o al final. Para
encadenarlas con fundido cruzado hay que saber dónde empieza y dónde termina
el sonido real. Se mide con ffmpeg leyendo solo los primeros y los últimos
segundos, y el PCM se parte en ventanas para no depender del texto de ningún
filtro. Módulo puro salvo `medir_bordes`, que lanza subprocesos reales.
"""

from __future__ import annotations

import array
import math
import subprocess
import sys
from dataclasses import dataclass

from ytchat.core import diagnostico

logger = diagnostico.obtener_logger(__name__)

UMBRAL_DBFS = -50.0
VENTANA_MS = 100
TASA = 8000
SEGUNDOS_INICIO = 20
SEGUNDOS_FINAL = 30

REFERENCIA_RMS = 32768.0
MUESTRAS_POR_VENTANA = TASA * VENTANA_MS // 1000


@dataclass(frozen=True)
class Bordes:
    """Cuántos milisegundos de silencio tiene una canción en cada punta."""

    silencio_inicial_ms: int
    silencio_final_ms: int


def _muestras(pcm):
    """Las muestras s16le mono de `pcm`, como enteros con signo.

    Ignora un último byte suelto porque no completa una muestra.
    """
    if not isinstance(pcm, (bytes, bytearray, memoryview)):
        return array.array("h")
    datos = bytes(pcm)
    datos = datos[:len(datos) - (len(datos) % 2)]
    muestras = array.array("h")
    muestras.frombytes(datos)
    if sys.byteorder != "little":
        muestras.byteswap()
    return muestras


def _ventanas(muestras):
    """Las ventanas de `VENTANA_MS` en que se parte el audio."""
    for inicio in range(0, len(muestras), MUESTRAS_POR_VENTANA):
        yield muestras[inicio:inicio + MUESTRAS_POR_VENTANA]


def _ventana_es_silencio(muestras):
    """Verdadero si la ventana no llega al umbral, o si no tiene sonido."""
    if not muestras:
        return True
    energia = sum(muestra * muestra for muestra in muestras)
    rms = math.sqrt(energia / len(muestras))
    if rms <= 0:
        return True
    return 20.0 * math.log10(rms / REFERENCIA_RMS) <= UMBRAL_DBFS


def silencio_inicial_ms(pcm):
    """Milisegundos de silencio desde el principio del fragmento.

    Cuenta las ventanas de silencio seguidas del principio. Devuelve 0 si el
    fragmento está vacío o si todo es silencio, porque no se sabe dónde está
    el sonido y no conviene saltear nada. Función pura.
    """
    ventanas = list(_ventanas(_muestras(pcm)))
    if not ventanas:
        return 0
    seguidas = 0
    for ventana in ventanas:
        if not _ventana_es_silencio(ventana):
            break
        seguidas += 1
    if seguidas == len(ventanas):
        return 0
    return seguidas * VENTANA_MS


def silencio_final_ms(pcm):
    """Milisegundos de silencio desde el final del fragmento.

    Cuenta las ventanas de silencio seguidas del final. La última ventana
    puede estar incompleta y cuenta como entera. Devuelve 0 si el fragmento
    está vacío o si todo es silencio. Función pura.
    """
    ventanas = list(_ventanas(_muestras(pcm)))
    if not ventanas:
        return 0
    seguidas = 0
    for ventana in reversed(ventanas):
        if not _ventana_es_silencio(ventana):
            break
        seguidas += 1
    if seguidas == len(ventanas):
        return 0
    return seguidas * VENTANA_MS


def _argumentos_inicio(ruta_ffmpeg, ruta):
    """Los argumentos para leer el principio del archivo."""
    return [ruta_ffmpeg, "-hide_banner", "-nostats", "-v", "error",
            "-t", str(SEGUNDOS_INICIO), "-i", ruta,
            "-vn", "-sn", "-dn", "-ac", "1", "-ar", str(TASA),
            "-f", "s16le", "-"]


def _argumentos_final(ruta_ffmpeg, ruta):
    """Los argumentos para leer el final del archivo."""
    return [ruta_ffmpeg, "-hide_banner", "-nostats", "-v", "error",
            "-sseof", f"-{SEGUNDOS_FINAL}", "-i", ruta,
            "-vn", "-sn", "-dn", "-ac", "1", "-ar", str(TASA),
            "-f", "s16le", "-"]


def _leer_pcm(argumentos, ruta, plazo_s):
    """El PCM que escribe ffmpeg en stdout, o None con el motivo registrado.

    Sin ventana y con prioridad baja, vinculado a la app para que muera si la
    app se cierra. Si vence el plazo, mata al proceso antes de volver.
    """
    try:
        banderas = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        banderas |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
        proceso = subprocess.Popen(
            argumentos,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=banderas,
        )
    except Exception as exc:
        logger.warning("No se pudo medir los bordes de %s: %s", ruta, exc)
        return None
    try:
        from ytchat.core.subprocesos import vincular_a_la_app
        vincular_a_la_app(proceso)
    except Exception as exc:
        logger.debug("No se pudo vincular la medición a la app: %s", exc)
    try:
        salida, errores = proceso.communicate(timeout=plazo_s)
    except subprocess.TimeoutExpired:
        try:
            proceso.kill()
        except Exception as exc:
            logger.debug("No se pudo matar la medición vencida: %s", exc)
        try:
            proceso.wait(timeout=10)
        except Exception as exc:
            logger.debug("Espera tras matar la medición: %s", exc)
        logger.warning("La medición de los bordes de %s venció el plazo de %s s",
                       ruta, plazo_s)
        return None
    except Exception as exc:
        logger.warning("No se pudo esperar la medición de los bordes de %s: %s",
                       ruta, exc)
        return None
    if proceso.returncode != 0:
        detalle = (errores or b"").decode("utf-8", "replace").strip()
        logger.warning(
            "ffmpeg no pudo medir los bordes de %s (código %s): %s",
            ruta, proceso.returncode, detalle)
        return None
    return salida or b""


def medir_bordes(ruta_ffmpeg, ruta, plazo_s=20):
    """Los bordes de sonido de ese archivo, medidos con ffmpeg, o None.

    Corre ffmpeg dos veces sobre el mismo archivo: una para los primeros
    `SEGUNDOS_INICIO` y otra para los últimos `SEGUNDOS_FINAL`. Nunca lanza:
    cada None deja una línea en el registro con el motivo.
    """
    inicio = _leer_pcm(_argumentos_inicio(ruta_ffmpeg, ruta), ruta, plazo_s)
    if inicio is None:
        return None
    final = _leer_pcm(_argumentos_final(ruta_ffmpeg, ruta), ruta, plazo_s)
    if final is None:
        return None
    return Bordes(silencio_inicial_ms(inicio), silencio_final_ms(final))
