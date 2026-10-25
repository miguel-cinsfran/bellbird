"""Igualación de volumen de la música local, sin interfaz.

Muchas canciones vienen de YouTube y unas suenan más fuerte que otras. Cada
archivo se mide una sola vez con ffmpeg (sonoridad integrada EBU R128) y el
resultado se guarda en una caché en disco; al reproducir, la ganancia
guardada corrige el volumen sin aplastar la diferencia entre las partes
suaves y fuertes de cada canción, como hace Spotify. Módulo puro salvo
`medir`, que lanza un subproceso real.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from ytchat.core import archivos
from ytchat.core import diagnostico

logger = diagnostico.obtener_logger(__name__)

# El de Spotify y YouTube, en LUFS.
OBJETIVO_LUFS = -14.0
# Pico máximo permitido tras aplicar la ganancia, en dB: se compara con
# el pico de muestra que informa `ebur128`.
TECHO_PICO_DBTP = -1.0
GANANCIA_MINIMA_DB = -15.0
GANANCIA_MAXIMA_DB = 10.0
# Hasta acá acepta VLC y amplifica por software.
VOLUMEN_MAXIMO_VLC = 200

# Lo que puede pasar al pedir la igualación del volumen.
INICIO = "inicio"
YA_MIDIENDO = "ya_midiendo"
OPCION_APAGADA = "opcion_apagada"
SIN_FFMPEG = "sin_ffmpeg"
NADA_PENDIENTE = "nada_pendiente"

SONIDO_IGUALANDO = "musica_igualando"

TEXTO_IGUALANDO = "Igualando el volumen de {total} canciones"
TEXTO_IGUALACION_DESACTIVADA = (
    "La igualación del volumen está desactivada. Actívala en Preferencias, "
    "página Música.")
TEXTO_SIN_FFMPEG = "No se puede igualar el volumen: falta ffmpeg."
TEXTO_NADA_PENDIENTE = "Todas las canciones tienen el volumen igualado."
TEXTO_IGUALACION_DETENIDA = "Igualación del volumen detenida."
TEXTO_PROGRESO = "Igualando el volumen: {hechas} de {total}"

VERSION = 1


@dataclass(frozen=True)
class ResultadoIgualacion:
    """Lo que pasó al pedir la igualación del volumen.

    El código dice qué pasó y `total` cuántas canciones quedan por medir.
    """

    codigo: str
    total: int = 0


_NUMERO = r"[+-]?(?:inf(?:inity)?|nan|\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)"
_PATRON_I = re.compile(r"^\s*I:\s*(" + _NUMERO + r")",
                      re.IGNORECASE | re.MULTILINE)
_PATRON_PICO = re.compile(r"^\s*Peak:\s*(" + _NUMERO + r")",
                         re.IGNORECASE | re.MULTILINE)


def leer_medicion(texto):
    """La sonoridad medida por ffmpeg, o None si no se puede leer.

    Del texto que ffmpeg escribe en stderr con el filtro `ebur128`, toma
    lo que sigue a la última línea «Summary:» y de ahí el número de la
    línea `I:` (sonoridad integrada) y el de la línea `Peak:` (pico de
    muestra). Devuelve `(integrada, pico)` como floats. None si falta el
    resumen, si falta alguna de las dos líneas o si algún número no es
    finito (ffmpeg escribe «-inf» en un archivo mudo).
    """
    if not isinstance(texto, str) or not texto:
        return None
    indice = texto.rfind("Summary:")
    if indice < 0:
        return None
    resumen = texto[indice + len("Summary:"):]
    encuentro_i = _PATRON_I.search(resumen)
    encuentro_pico = _PATRON_PICO.search(resumen)
    if encuentro_i is None or encuentro_pico is None:
        return None
    try:
        valor_i = float(encuentro_i.group(1))
        valor_pico = float(encuentro_pico.group(1))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(valor_i) or not math.isfinite(valor_pico):
        return None
    return (valor_i, valor_pico)


def ganancia_db(input_i, input_tp):
    """La corrección en dB para llevar la canción al objetivo.

    `OBJETIVO_LUFS - input_i`, sin pasar de `TECHO_PICO_DBTP - input_tp`
    para no saturar, y dentro de `[GANANCIA_MINIMA_DB, GANANCIA_MAXIMA_DB]`.
    Redondeada a una décima.
    """
    cruda = OBJETIVO_LUFS - input_i
    tope_pico = TECHO_PICO_DBTP - input_tp
    ganancia = min(cruda, tope_pico)
    ganancia = max(GANANCIA_MINIMA_DB, min(GANANCIA_MAXIMA_DB, ganancia))
    return round(ganancia, 1)


def texto_progreso(progreso) -> str:
    """«Igualando el volumen: hechas de total», o vacío sin medición.

    Vacío si `progreso` es None. Función pura.
    """
    if progreso is None:
        return ""
    try:
        hechas, total = progreso
    except (TypeError, ValueError):
        return ""
    return TEXTO_PROGRESO.format(hechas=hechas, total=total)


def volumen_efectivo(volumen, ganancia):
    """El volumen con la ganancia aplicada, como entero hasta 200.

    VLC eleva el volumen al cubo, por eso la ganancia se divide entre 60.
    Con ganancia 0 devuelve el mismo volumen. El margen para no distorsionar
    ya lo garantiza `ganancia_db`, por eso pasado 100 se puede amplificar.
    """
    try:
        efectivo = round(float(volumen) * 10.0 ** (float(ganancia) / 60.0))
    except (TypeError, ValueError, OverflowError):
        return int(volumen) if isinstance(volumen, int) else 0
    return max(0, min(VOLUMEN_MAXIMO_VLC, int(efectivo)))


def _argumentos_medicion(ruta_ffmpeg, ruta):
    """Los argumentos de ffmpeg para medir la sonoridad de `ruta`."""
    return [ruta_ffmpeg, "-hide_banner", "-nostats", "-threads", "1",
            "-i", ruta, "-vn", "-sn", "-dn", "-af",
            "ebur128=peak=sample:framelog=quiet",
            "-f", "null", "-"]


def _salida_medicion(proceso, ruta, plazo_s):
    """El stderr de la medición, o None si venció el plazo o falló la espera.

    Si vence el plazo, mata al proceso antes de volver.
    """
    try:
        _salida, errores = proceso.communicate(timeout=plazo_s)
    except subprocess.TimeoutExpired:
        try:
            proceso.kill()
        except Exception as exc:
            logger.debug("No se pudo matar la medición vencida: %s", exc)
        try:
            proceso.wait(timeout=10)
        except Exception as exc:
            logger.debug("Espera tras matar la medición: %s", exc)
        logger.warning("La medición de %s venció el plazo de %s s",
                       ruta, plazo_s)
        return None
    except Exception as exc:
        logger.warning("No se pudo esperar la medición de %s: %s", ruta, exc)
        return None
    return errores or ""


def medir(ruta_ffmpeg, ruta, plazo_s=180):
    """La ganancia en dB de ese archivo, medida con ffmpeg, o None.

    Corre ffmpeg con el filtro `ebur128` en modo medición, sin ventana y
    con prioridad baja, vinculado a la app para que muera si la app se
    cierra. Nunca lanza: cada None deja una línea en el registro con el
    motivo (ffmpeg ausente o fallido, plazo vencido o salida ilegible).
    """
    try:
        banderas = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        banderas |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
        proceso = subprocess.Popen(
            _argumentos_medicion(ruta_ffmpeg, ruta),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            creationflags=banderas,
        )
    except Exception as exc:
        logger.warning("No se pudo medir la sonoridad de %s: %s", ruta, exc)
        return None
    try:
        from ytchat.core.subprocesos import vincular_a_la_app
        vincular_a_la_app(proceso)
    except Exception as exc:
        logger.debug("No se pudo vincular la medición a la app: %s", exc)
    errores = _salida_medicion(proceso, ruta, plazo_s)
    if errores is None:
        return None
    if proceso.returncode != 0:
        logger.warning("ffmpeg no pudo medir %s (código %s)",
                       ruta, proceso.returncode)
        return None
    medido = leer_medicion(errores)
    if medido is None:
        logger.warning("ffmpeg no devolvió medición legible para %s", ruta)
        return None
    return ganancia_db(medido[0], medido[1])


class CacheSonoridad:
    """Ganancias ya medidas, en memoria y en un JSON en disco.

    La clave es el `origen` del tema (la ruta resuelta). Cada entrada guarda
    `mtime_ns`, `tamano` y `ganancia_db`: si el archivo cambió, la entrada
    no vale y hay que medirlo de nuevo.
    """

    def __init__(self, ruta):
        self._ruta = Path(ruta)
        self._lock = threading.Lock()
        self._datos: dict[str, dict] = {}
        self._cargar()

    def buscar(self, origen, mtime_ns, tamano):
        """La ganancia de ese archivo, o None si no hay entrada válida.

        Solo vale si `mtime_ns` y `tamano` coinciden con lo guardado: si el
        archivo cambió, None aunque la ruta sea la misma.
        """
        with self._lock:
            entrada = self._datos.get(origen)
            if entrada is None:
                return None
            if entrada.get("mtime_ns") != mtime_ns:
                return None
            if entrada.get("tamano") != tamano:
                return None
            return entrada.get("ganancia_db")

    def poner(self, origen, mtime_ns, tamano, ganancia_db) -> None:
        """Guarda en memoria la ganancia de ese archivo.

        Ignora el pedido si la ganancia no es un número finito, para no
        guardar una entrada que nunca valdría.
        """
        if isinstance(ganancia_db, bool):
            logger.debug("Ganancia no numérica para %s: %r", origen, ganancia_db)
            return
        try:
            ganancia = float(ganancia_db)
        except (TypeError, ValueError):
            logger.debug("Ganancia no numérica para %s: %r", origen, ganancia_db)
            return
        if not math.isfinite(ganancia):
            logger.debug("Ganancia no finita para %s: %r", origen, ganancia_db)
            return
        with self._lock:
            self._datos[origen] = {
                "mtime_ns": mtime_ns,
                "tamano": tamano,
                "ganancia_db": ganancia,
            }

    def guardar(self) -> bool:
        """Escribe la caché en disco, de forma atómica. Nunca lanza.

        Crea la carpeta si falta y descarta las entradas cuyo archivo ya no
        existe. Devuelve verdadero si se guardó, falso si no se pudo.
        """
        try:
            with self._lock:
                vigentes = {
                    origen: dict(entrada)
                    for origen, entrada in self._datos.items()
                    if os.path.exists(origen)
                }
                self._datos = vigentes
                contenido = {"version": VERSION, "sonoridad": vigentes}
            ruta = Path(self._ruta)
            ruta.parent.mkdir(parents=True, exist_ok=True)
            archivos.escribir_json_atomico(ruta, contenido)
        except Exception as exc:
            logger.debug("No se pudo guardar la caché de sonoridad: %s", exc)
            return False
        return True

    def _cargar(self) -> None:
        """Lee el JSON a memoria. Un archivo ausente, vacío, corrupto o con
        forma inesperada deja la caché vacía, sin lanzar."""
        try:
            texto = Path(self._ruta).read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        except OSError as exc:
            logger.debug("No se pudo leer la caché de sonoridad: %s", exc)
            return
        if not texto.strip():
            return
        try:
            crudo = json.loads(texto)
        except ValueError as exc:
            logger.debug("No se pudo leer la caché de sonoridad: %s", exc)
            return
        if not isinstance(crudo, dict) or crudo.get("version") != VERSION:
            logger.debug("No se pudo leer la caché de sonoridad: forma inesperada")
            return
        sonoridad = crudo.get("sonoridad")
        if not isinstance(sonoridad, dict):
            logger.debug("No se pudo leer la caché de sonoridad: forma inesperada")
            return
        datos = {}
        for origen, entrada in sonoridad.items():
            normalizada = self._entrada_valida(origen, entrada)
            if normalizada is not None:
                datos[origen] = normalizada
        with self._lock:
            self._datos = datos

    @staticmethod
    def _entrada_valida(origen, entrada):
        """La entrada normalizada, o None si no sirve."""
        if not isinstance(origen, str) or not origen:
            return None
        if not isinstance(entrada, dict):
            return None
        mtime_ns = entrada.get("mtime_ns")
        tamano = entrada.get("tamano")
        if (isinstance(mtime_ns, bool) or not isinstance(mtime_ns, int)
                or isinstance(tamano, bool) or not isinstance(tamano, int)):
            return None
        ganancia = entrada.get("ganancia_db")
        if isinstance(ganancia, bool):
            return None
        try:
            ganancia = float(ganancia)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(ganancia):
            return None
        return {
            "mtime_ns": mtime_ns,
            "tamano": tamano,
            "ganancia_db": ganancia,
        }
