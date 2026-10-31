"""Autocomprobación del paquete armado.

Carga cada pieza crítica del `.exe` y anota el resultado, para que el armado
frene si PyInstaller dejó algo afuera. Corre sin ventanas, sin voz, sin red y
sin crear la carpeta de datos. La usa `construir.bat` con `--autocomprobar`.
"""

from __future__ import annotations

import logging
import sys


logger = logging.getLogger(__name__)


def _wxpython():
    import wx  # noqa: F401


def _prism():
    import prism
    prism.Context()
    from bellbird.voice.motores import MotorPrism
    motor = MotorPrism("sapi")
    cerrar = getattr(motor, "cerrar", None)
    if cerrar is not None:
        cerrar()


def _pytchat():
    import pytchat  # noqa: F401


def _tiktoklive():
    from TikTokLive import TikTokLiveClient  # noqa: F401
    from TikTokLive.events import CommentEvent  # noqa: F401
    from TikTokLive.proto.custom_proto import ExtendedUser  # noqa: F401


def _api_google():
    from googleapiclient.discovery import build
    build("youtube", "v3", developerKey="autocomprobacion",
          cache_discovery=False)


def _yt_dlp():
    import yt_dlp  # noqa: F401


def _idiomas():
    import gettext

    from bellbird.core import idioma
    from bellbird.core import paths
    carpeta = paths.carpeta_idiomas()
    for codigo in idioma.codigos_con_catalogo(carpeta):
        gettext.translation(
            idioma.DOMINIO, localedir=str(carpeta), languages=[codigo])


def _vlc():
    from bellbird.player import motor_vlc
    if not motor_vlc.cargar():
        raise RuntimeError("no se pudo cargar libVLC")
    instancia = motor_vlc.instancia()
    if instancia is None:
        raise RuntimeError("la instancia de VLC salió vacía")
    reproductor = instancia.media_player_new()
    if reproductor is None:
        raise RuntimeError("VLC no pudo crear un reproductor")
    try:
        if not motor_vlc.fijar_salida_audio(reproductor):
            raise RuntimeError("no se pudo fijar la salida DirectSound")
    finally:
        try:
            reproductor.release()
        except Exception as exc:
            logger.debug("No se pudo liberar el reproductor de VLC: %s", exc)


def _detector_rostros():
    import cv2
    import numpy

    from bellbird.camera import detector_rostros
    from bellbird.core import paths
    # Gris lisa: da igual si hay rostros, solo importa que el detector corra.
    gris = numpy.full((64, 64), 128, dtype=numpy.uint8)
    ok, datos = cv2.imencode(".bmp", gris)
    if not ok:
        raise RuntimeError("no se pudo codificar la imagen de prueba")
    detector = detector_rostros.DetectorRostros(paths.modelo_rostros())
    detector.analizar(datos.tobytes())


PIEZAS = (
    ("wxPython", _wxpython),
    ("Prism", _prism),
    ("pytchat", _pytchat),
    ("TikTokLive", _tiktoklive),
    ("API de Google", _api_google),
    ("yt-dlp", _yt_dlp),
    ("VLC", _vlc),
    ("Idiomas", _idiomas),
    ("Detector de rostros", _detector_rostros),
)


def comprobar(piezas=PIEZAS):
    """Carga cada pieza en su propio try. Una que falla no impide las demás.

    Devuelve una lista de `(nombre, None)` si cargó o `(nombre, "Tipo: mensaje")`
    si no, en el mismo orden en que se pasaron.
    """
    resultados = []
    for nombre, cargar in piezas:
        try:
            cargar()
        except Exception as exc:
            resultados.append((nombre, f"{type(exc).__name__}: {exc}"))
        else:
            resultados.append((nombre, None))
    return resultados


def lineas(resultados):
    """Una línea por pieza: «OK nombre» o «FALLA nombre: Tipo: mensaje»."""
    return [
        f"OK {nombre}" if error is None else f"FALLA {nombre}: {error}"
        for nombre, error in resultados
    ]


def principal(argumentos):
    """Corre la comprobación y devuelve el código de salida.

    Con una ruta escribe ahí en UTF-8, sin ruta escribe en `sys.stdout` si
    existe (en el `.exe` sin consola es None). 0 si todo cargó, 1 si algo
    falló y 2 si no se pudo escribir el archivo.
    """
    resultados = comprobar()
    texto = "\n".join(lineas(resultados)) + "\n"
    if argumentos:
        try:
            with open(argumentos[0], "w", encoding="utf-8") as archivo:
                archivo.write(texto)
        except OSError:
            return 2
    elif sys.stdout is not None:
        sys.stdout.write(texto)
    return 0 if all(error is None for _sin_uso, error in resultados) else 1
