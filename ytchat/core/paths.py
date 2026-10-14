"""Ubicación de cada archivo y carpeta, en un solo lugar.

Es el ÚNICO módulo de la aplicación que sabe dónde vive cada archivo:
ningún otro arma rutas de datos o de instalación por su cuenta. Solo usa
biblioteca estándar, para no provocar imports circulares.

Dos raíces: `carpeta_instalacion` (lo que viene con el programa) y
`carpeta_datos` (lo que escribe el usuario, en la subcarpeta `data`).
Ninguna función de este módulo crea nada en disco, solo devuelve rutas.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


# Depende de la ubicación de este archivo: vive en `ytchat/core/`, así que
# la raíz en desarrollo está tres niveles arriba.
_RAIZ_DESARROLLO = Path(__file__).resolve().parent.parent.parent

# Nombres que antes vivían duplicados en cada módulo que los usaba.
NOMBRE_CREDENCIALES = "credenciales.json"
NOMBRE_CLIENTE_APP = "cliente_app.json"
NOMBRE_FFMPEG = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
NOMBRE_YTDLP = "yt-dlp.exe"
# Manifiesto que construir.bat escribe en la raíz del paquete distribuible.
NOMBRE_MANIFIESTO = "paquete.json"


def carpeta_instalacion() -> Path:
    """Lo que viene con el programa: junto al .exe, o la raíz en desarrollo."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return _RAIZ_DESARROLLO


def carpeta_datos() -> Path:
    """Lo que escribe el usuario: la subcarpeta `data` junto al programa."""
    return carpeta_instalacion() / "data"


# ── Datos (los escribe el usuario) ───────────────────────────────────────────

def config_ini() -> Path:
    return carpeta_datos() / "config.ini"


def credenciales() -> Path:
    return carpeta_datos() / NOMBRE_CREDENCIALES


def historial_lives() -> Path:
    return carpeta_datos() / "historial_lives.json"


def historial_descargas() -> Path:
    return carpeta_datos() / "historial_descargas.json"


def alias() -> Path:
    return carpeta_datos() / "alias.json"


def mensajes_programados() -> Path:
    return carpeta_datos() / "mensajes_programados.json"


def sounds_ini() -> Path:
    # Va con los datos porque la app lo escribe al cambiar el tema.
    return carpeta_datos() / "sounds.ini"


def log_principal() -> Path:
    return carpeta_datos() / "ytchat.log"


def log_detallado() -> Path:
    return carpeta_datos() / "ytchat-debug.log"


def log_fallos() -> Path:
    return carpeta_datos() / "ytchat-fallos.log"


def cache_audio() -> Path:
    return carpeta_datos() / "cache-audio"


def cache_video() -> Path:
    return carpeta_datos() / "cache-video"


def descargas_por_defecto() -> Path:
    # Son vídeos y audios del usuario y quedan a la vista, junto al programa.
    return carpeta_instalacion() / "Descargas"


def datos_a_migrar() -> list[Path]:
    """Rutas de datos que la migración mueve de la raíz a `data/`."""
    return [
        config_ini(),
        credenciales(),
        historial_lives(),
        historial_descargas(),
        alias(),
        mensajes_programados(),
        log_principal(),
        log_detallado(),
        log_fallos(),
        cache_audio(),
        cache_video(),
    ]


# ── Instalación (viene con el programa) ──────────────────────────────────────

def carpeta_sonidos() -> Path:
    return carpeta_instalacion() / "sounds"


def pagina_overlay() -> Path:
    return carpeta_instalacion() / "web" / "chat.html"


def config_predeterminada_ini() -> Path:
    return carpeta_instalacion() / "config.predeterminado.ini"


def ffmpeg_empaquetado() -> Path:
    return carpeta_instalacion() / NOMBRE_FFMPEG


def ytdlp_empaquetado() -> Path:
    return carpeta_instalacion() / NOMBRE_YTDLP


def carpeta_vlc_empaquetada() -> Path:
    return carpeta_instalacion() / "vlc"


def carpeta_interna() -> Path:
    return carpeta_instalacion() / "_internal"


def cliente_app() -> Path:
    # El cliente de Google de la app viaja junto al ejecutable: no es un
    # dato del usuario y por eso cuelga de la instalación, no de los datos.
    return carpeta_instalacion() / NOMBRE_CLIENTE_APP


# ── Actualización (motor, sin interfaz) ────────────────────────────────────
# El instalador corre desde la carpeta del paquete nuevo, no desde la
# instalación: por eso cada ruta tiene su variante `..._en(instalacion)`
# que arma la misma ruta relativa a la instalación recibida por argumento.
# Las sin sufijo llaman a esas con `carpeta_instalacion()`.

def carpeta_actualizacion_en(instalacion: Path) -> Path:
    return Path(instalacion) / "data" / "actualizacion"


def carpeta_actualizacion() -> Path:
    return carpeta_actualizacion_en(carpeta_instalacion())


def paquete_descargado_en(instalacion: Path) -> Path:
    return carpeta_actualizacion_en(instalacion) / "paquete.zip"


def paquete_descargado() -> Path:
    return paquete_descargado_en(carpeta_instalacion())


def paquete_extraido_en(instalacion: Path) -> Path:
    return carpeta_actualizacion_en(instalacion) / "nueva"


def paquete_extraido() -> Path:
    return paquete_extraido_en(carpeta_instalacion())


def respaldo_actualizacion_en(instalacion: Path) -> Path:
    return carpeta_actualizacion_en(instalacion) / "respaldo"


def respaldo_actualizacion() -> Path:
    return respaldo_actualizacion_en(carpeta_instalacion())


def actualizacion_pendiente_en(instalacion: Path) -> Path:
    return carpeta_actualizacion_en(instalacion) / "pendiente.json"


def actualizacion_pendiente() -> Path:
    return actualizacion_pendiente_en(carpeta_instalacion())


def arranque_confirmado_en(instalacion: Path) -> Path:
    return carpeta_actualizacion_en(instalacion) / "arranque-ok"


def arranque_confirmado() -> Path:
    return arranque_confirmado_en(carpeta_instalacion())


def resultado_actualizacion_en(instalacion: Path) -> Path:
    return carpeta_actualizacion_en(instalacion) / "resultado.json"


def resultado_actualizacion() -> Path:
    return resultado_actualizacion_en(carpeta_instalacion())


def registro_actualizacion_en(instalacion: Path) -> Path:
    return carpeta_actualizacion_en(instalacion) / "registro.log"


def registro_actualizacion() -> Path:
    return registro_actualizacion_en(carpeta_instalacion())
