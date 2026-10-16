"""Exportar, importar y restablecer el archivo de preferencias.

Lógica pura, sin wx: recibe rutas o usa las de `paths` por defecto. Solo toca
el ini de preferencias y su copia de respaldo; las credenciales nunca se leen
ni se escriben desde acá.
"""

from __future__ import annotations

import configparser
from pathlib import Path

from ytchat.core import archivos
from ytchat.core import config_predeterminada
from ytchat.core import paths

# Más de esto no es un archivo de preferencias: se rechaza sin leerlo entero.
LIMITE_BYTES = 1_048_576


class ErrorPreferencias(ValueError):
    """El archivo no se pudo importar o no se pudo escribir el nuevo."""


def motivo_no_importable(origen) -> str | None:
    """None si el archivo se puede importar; si no, el motivo para mostrar."""
    origen = Path(origen)
    try:
        if origen.stat().st_size > LIMITE_BYTES:
            return "Ese archivo pesa más de 1 MB."
    except OSError:
        return "No se pudo leer ese archivo."
    try:
        texto = origen.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return "No se pudo leer ese archivo."
    # Mismo molde con el que la aplicación lee su configuración: sin
    # interpolación y sin sección por defecto.
    parser = configparser.ConfigParser(
        interpolation=None, default_section="__none__")
    try:
        parser.read_string(texto)
    except configparser.Error:
        return "Ese archivo no es de preferencias de la aplicación."
    conocidas = set(config_predeterminada.secciones())
    if not any(seccion in conocidas for seccion in parser.sections()):
        return "Ese archivo no es de preferencias de la aplicación."
    return None


def exportar(destino, origen=None) -> Path:
    """Copia el ini actual a `destino`, tal cual; sin ini, el de fábrica."""
    actual = Path(origen) if origen is not None else paths.config_ini()
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if actual.is_file():
        destino.write_bytes(actual.read_bytes())
        return destino
    archivos.escribir_texto_atomico(
        destino, config_predeterminada.generar_texto())
    return destino


def _guardar_respaldo(actual: Path, respaldo: Path) -> None:
    """Guarda una copia del ini actual en el respaldo, si el actual existe."""
    if actual.is_file():
        respaldo.parent.mkdir(parents=True, exist_ok=True)
        respaldo.write_bytes(actual.read_bytes())


def importar(origen, destino=None, respaldo=None) -> Path:
    """Escribe el contenido de `origen` en el ini, con respaldo del anterior."""
    motivo = motivo_no_importable(origen)
    if motivo is not None:
        raise ErrorPreferencias(motivo)
    actual = Path(destino) if destino is not None else paths.config_ini()
    copia = Path(respaldo) if respaldo is not None else paths.config_anterior()
    _guardar_respaldo(actual, copia)
    actual.parent.mkdir(parents=True, exist_ok=True)
    archivos.escribir_texto_atomico(
        actual, Path(origen).read_text(encoding="utf-8"))
    return actual


def restablecer(destino=None, respaldo=None) -> Path:
    """Deja el ini de fábrica, con respaldo del anterior."""
    actual = Path(destino) if destino is not None else paths.config_ini()
    copia = Path(respaldo) if respaldo is not None else paths.config_anterior()
    _guardar_respaldo(actual, copia)
    actual.parent.mkdir(parents=True, exist_ok=True)
    archivos.escribir_texto_atomico(
        actual, config_predeterminada.generar_texto())
    return actual
