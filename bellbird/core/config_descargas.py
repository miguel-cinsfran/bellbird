"""Leer y guardar la sección [descargas] de config.ini.

Una sola responsabilidad: las opciones de descarga (formato, bitrate,
resolucion, carpeta, enumerar) validadas contra un único origen de verdad, sin tener
que duplicar la carga de config.ini. `config` las reexporta para que
`descargas`, `gui_descargas` y las pruebas sigan iguales. Lo que necesita
de `config` (`_mk_parser`, `guardar_opcion`, `_CONFIG_FALLBACK`) se importa
dentro de cada función para no cerrar un import circular.
"""

from __future__ import annotations

import configparser
from pathlib import Path

from bellbird.core import diagnostico
from bellbird.core import paths
from bellbird.downloads.opciones_formato import (
    BITRATES, FORMATOS, RESOLUCIONES)


logger = diagnostico.obtener_logger(__name__)


# ── Helpers de descargas (formato, bitrate, resolucion, carpeta, enumerar) ────
# Se leen/escriben del INI con `guardar_opcion` (preserva comentarios). Sirven
# para que `descargas.GestorDescargas` y `gui_descargas` trabajen contra un
# único origen de verdad, sin tener que duplicar la carga de config.ini.
#
# Formato por defecto: mp4 muxed (mejor compat con NVDA, sin audio separado).
# Carpeta por defecto: `paths.descargas_por_defecto()` (portable, escribible
# sin permisos de admin). Si el INI trae la clave vacía, también se rellena.

_FORMATOS_VALIDOS = tuple(clave for _etiqueta, clave in FORMATOS)
_BITRATES_VALIDOS = BITRATES


def _validar_y_fijar(ruta, seccion, clave, valor, defecto, validos):
    """Devuelve el valor si es válido y si no fija el defecto en el INI."""
    from bellbird.core.config import guardar_opcion

    if valor not in validos:
        valor = defecto
        if ruta.exists():
            guardar_opcion(ruta, seccion, clave, str(valor))
    return valor


def _carpeta_descargas(p) -> str:
    """Carpeta de destino: la del INI o la de descargas por defecto."""
    crudo = (p.get("descargas", "carpeta", fallback="").strip()
             if p.has_section("descargas") else "")
    if not crudo:
        return str(paths.descargas_por_defecto())
    if not Path(crudo).anchor:
        # El valor predeterminado es «Descargas» a secas: yt-dlp lo resolvía
        # contra el directorio de trabajo del proceso, que con un acceso
        # directo o desde una consola no es la carpeta de la app.
        return str(paths.carpeta_instalacion() / crudo)
    return crudo


def obtener_opciones_descarga() -> dict:
    """Lee la sección [descargas] del INI y devuelve un dict validado.

    Si la sección no existe o falta alguna clave, se rellena con `guardar_opcion`
    (que conserva comentarios y orden) y se devuelve el dict ya con defaults.
    Funciona standalone: NO requiere haber llamado a `cargar_configuracion`.
    """
    from bellbird.core.config import _mk_parser, guardar_opcion

    ruta = paths.config_ini()
    p = _mk_parser()
    if ruta.exists():
        try:    p.read(ruta, encoding="utf-8")
        except configparser.Error: pass

    # Carpeta: si está vacía o no existe, usar la de descargas por defecto.
    carpeta = _carpeta_descargas(p)

    formato_crudo = (p.get("descargas", "formato", fallback="mp4").strip().lower()
                     if p.has_section("descargas") else "mp4")
    formato = _validar_y_fijar(ruta, "descargas", "formato", formato_crudo, "mp4",
                               _FORMATOS_VALIDOS)
    bitrate_crudo = (p.get("descargas", "bitrate", fallback="192").strip()
                     if p.has_section("descargas") else "192")
    try:    bitrate_crudo = int(bitrate_crudo)
    except Exception: bitrate_crudo = 192
    bitrate = _validar_y_fijar(ruta, "descargas", "bitrate", bitrate_crudo, 192, _BITRATES_VALIDOS)

    if p.has_option("descargas", "resolucion"):
        try:    resolucion = int(p.get("descargas", "resolucion").strip())
        except Exception: resolucion = 0
        if resolucion not in RESOLUCIONES:
            resolucion = 0
            if ruta.exists():
                guardar_opcion(ruta, "descargas", "resolucion", "0")
    else:
        resolucion = 0

    enumerar_raw = (p.get("descargas", "enumerar", fallback="false").strip().lower()
                    if p.has_section("descargas") else "false")
    enumerar = enumerar_raw in ("true", "1", "yes", "on")

    return {"formato": formato, "bitrate": bitrate, "resolucion": resolucion,
            "carpeta": carpeta, "enumerar": enumerar}


def guardar_opciones_descarga(op: dict) -> None:
    """Persiste todas las opciones de descarga de una vez. Valida y normaliza
    los valores antes de escribir."""
    from bellbird.core.config import _CONFIG_FALLBACK, guardar_opcion

    ruta = paths.config_ini()
    if not ruta.exists():
        # Si por algo no existe, crearlo con el fallback y volver a llamar.
        try:    ruta.write_text(_CONFIG_FALLBACK, encoding="utf-8")
        except Exception as exc:
            logger.debug("guardar_opciones_descarga: no se pudo crear config.ini: %s", exc)
            return

    formato = str(op.get("formato", "mp4")).lower().strip()
    if formato not in _FORMATOS_VALIDOS:
        formato = "mp4"
    try:    bitrate = int(op.get("bitrate", 192))
    except Exception: bitrate = 192
    if bitrate not in _BITRATES_VALIDOS:
        bitrate = 192
    try:    resolucion = int(op.get("resolucion", 0))
    except Exception: resolucion = 0
    if resolucion not in RESOLUCIONES:
        resolucion = 0
    carpeta = str(op.get("carpeta") or paths.descargas_por_defecto()).strip()
    enumerar = bool(op.get("enumerar", False))

    guardar_opcion(ruta, "descargas", "formato", formato)
    guardar_opcion(ruta, "descargas", "bitrate", str(bitrate))
    guardar_opcion(ruta, "descargas", "resolucion", str(resolucion))
    guardar_opcion(ruta, "descargas", "carpeta", carpeta)
    guardar_opcion(ruta, "descargas", "enumerar", "true" if enumerar else "false")
