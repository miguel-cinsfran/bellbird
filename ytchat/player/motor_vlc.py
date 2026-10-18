"""Motor compartido de libVLC.

Una sola instancia de libVLC para todo el proceso. Cargar la DLL e instanciar
libVLC es lo lento (medido entre 56 y 128 s en frío en un equipo real), así que
el panel de vídeo y la música de la 2.4 piden la misma instancia en vez de crear
otra. Sin `wx`: lo usan el reproductor y la autocomprobación.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import threading
import time

from ytchat.core import diagnostico
from ytchat.core import paths

logger = diagnostico.obtener_logger(__name__)

_modulo = None          # binding python-vlc; se importa perezosamente
_preparado = False
_inst = None            # Instance compartida del proceso
_lock = threading.Lock()

# Argumentos de la instancia: solo los imprescindibles. Cualquier opción que
# libVLC no reconozca hace que libvlc_new devuelva NULL (instancia None), así
# que el ajuste de buffer va como opción POR MEDIO (más tolerante), no aquí.
ARGS = ("--quiet",)


def _registrar_tiempo_precalentamiento(tramo: str, inicio: float, fin: float) -> None:
    diagnostico.logger.info(
        "VLC_PRECALENTAMIENTO tramo=%s ms=%.0f", tramo, (fin - inicio) * 1000)


def carpeta_empaquetada() -> str | None:
    if getattr(sys, "frozen", False):
        carpeta = paths.carpeta_vlc_empaquetada()
        if os.path.exists(carpeta / "libvlc.dll"):
            return str(carpeta)
    return None


def preparar() -> None:
    """Deja listo el entorno para cargar libVLC. En la app empaquetada apunta a
    la copia de VLC junto al .exe y PRECARGA libvlccore para que el cargador de
    PyInstaller no falle al resolver la dependencia."""
    global _preparado
    inicio = time.monotonic()
    if _preparado:
        return
    _preparado = True
    base = carpeta_empaquetada()
    if not base:
        _registrar_tiempo_precalentamiento("preparar_dll", inicio, time.monotonic())
        return
    lib = os.path.join(base, "libvlc.dll")
    plugins = os.path.join(base, "plugins")
    os.environ["PYTHON_VLC_LIB_PATH"] = lib
    os.environ["PYTHON_VLC_MODULE_PATH"] = plugins
    # VLC_PLUGIN_PATH es lo que lee libVLC para localizar sus plugins; sin esto
    # la instancia sale None en la app empaquetada.
    os.environ["VLC_PLUGIN_PATH"] = plugins
    os.environ["PATH"] = base + os.pathsep + os.environ.get("PATH", "")
    try:
        os.add_dll_directory(base)
    except Exception:
        pass
    # Precargar el core: así libvlc.dll encuentra su dependencia bajo PyInstaller.
    try:
        import ctypes
        ctypes.CDLL(os.path.join(base, "libvlccore.dll"))
    except Exception as exc:
        logger.debug("preload libvlccore: %s", exc)
    _registrar_tiempo_precalentamiento("preparar_dll", inicio, time.monotonic())


def cargar() -> bool:
    """Importa python-vlc de forma perezosa. True si quedó disponible."""
    global _modulo
    if _modulo is not None:
        return True
    preparar()
    inicio = time.monotonic()
    try:
        import vlc
        _modulo = vlc
        _registrar_tiempo_precalentamiento("importar_modulo", inicio, time.monotonic())
        return True
    except Exception as exc:
        _registrar_tiempo_precalentamiento("importar_modulo", inicio, time.monotonic())
        logger.warning("No se pudo cargar libVLC: %s", exc)
        return False


def modulo():
    """El binding python-vlc ya cargado, o None si todavía no se cargó. No carga
    nada por sí solo."""
    return _modulo


def disponible() -> bool:
    """¿Hay VLC? Sin importarlo (cargar la DLL es lento) para no frenar arranque."""
    if getattr(sys, "frozen", False):
        return carpeta_empaquetada() is not None
    try:
        return importlib.util.find_spec("vlc") is not None
    except Exception:
        return False


def instancia():
    """La Instance compartida de libVLC. La primera llamada exitosa la crea; las
    siguientes devuelven el MISMO objeto. Si no se puede cargar el binding, si
    `Instance` lanza o si devuelve None, devuelve None sin recordar el fracaso:
    la próxima llamada lo vuelve a intentar. Segura entre hilos."""
    global _inst
    if _inst is not None:
        return _inst
    if not cargar():
        return None
    with _lock:
        if _inst is None:
            inicio = time.monotonic()
            try:
                creada = _modulo.Instance(*ARGS)
            except Exception as exc:
                _registrar_tiempo_precalentamiento(
                    "crear_instancia", inicio, time.monotonic())
                logger.warning("No se pudo crear la instancia de VLC: %s", exc)
                return None
            _registrar_tiempo_precalentamiento(
                "crear_instancia", inicio, time.monotonic())
            if creada is None:
                return None
            _inst = creada
        return _inst
