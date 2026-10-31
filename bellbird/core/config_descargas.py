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
    BITRATES, FORMATOS, LIMITE_MAX, PLANTILLAS, RESOLUCIONES,
    SIMULTANEAS_DEFECTO, SIMULTANEAS_MAX, SIMULTANEAS_MIN)


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
_PLANTILLAS_VALIDAS = tuple(clave for _etiqueta, clave, _plantilla in PLANTILLAS)


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


def _entero_descargas(p, ruta, clave, defecto, minimo, maximo) -> int:
    """Entero de [descargas]: ausente no reescribe, inválido fija el defecto."""
    from bellbird.core.config import guardar_opcion

    if not p.has_option("descargas", clave):
        return defecto
    try:
        valor = int(str(p.get("descargas", clave)).strip())
    except Exception:
        valor = defecto
    if valor < minimo or valor > maximo:
        valor = defecto
        if ruta.exists():
            guardar_opcion(ruta, "descargas", clave, str(valor))
    return valor


def _booleano_descargas(p, clave) -> bool:
    """Booleano de [descargas]: ausente es falso y no reescribe."""
    if not p.has_option("descargas", clave):
        return False
    return str(p.get("descargas", clave)).strip().lower() in ("true", "1", "yes", "on")


def _plantilla_descargas(p, ruta) -> str:
    """Clave de plantilla: ausente no reescribe, desconocida fija el defecto."""
    if not p.has_option("descargas", "plantilla"):
        return "titulo_id"
    crudo = str(p.get("descargas", "plantilla")).strip()
    return _validar_y_fijar(ruta, "descargas", "plantilla", crudo, "titulo_id",
                            _PLANTILLAS_VALIDAS)


def _formato_descargas(p, ruta) -> str:
    """Formato validado contra los nueve de `opciones_formato`."""
    crudo = (p.get("descargas", "formato", fallback="mp4").strip().lower()
             if p.has_section("descargas") else "mp4")
    return _validar_y_fijar(ruta, "descargas", "formato", crudo, "mp4",
                            _FORMATOS_VALIDOS)


def _bitrate_descargas(p, ruta) -> int:
    """Bitrate validado contra los cuatro que admite la app."""
    crudo = (p.get("descargas", "bitrate", fallback="192").strip()
             if p.has_section("descargas") else "192")
    try:
        crudo = int(crudo)
    except Exception:
        crudo = 192
    return _validar_y_fijar(ruta, "descargas", "bitrate", crudo, 192,
                            _BITRATES_VALIDOS)


def _resolucion_descargas(p, ruta) -> int:
    """Resolución validada: ausente no reescribe, inválida fija cero."""
    from bellbird.core.config import guardar_opcion

    if not p.has_option("descargas", "resolucion"):
        return 0
    try:
        valor = int(p.get("descargas", "resolucion").strip())
    except Exception:
        valor = 0
    if valor not in RESOLUCIONES:
        valor = 0
        if ruta.exists():
            guardar_opcion(ruta, "descargas", "resolucion", "0")
    return valor


def _enumerar_descargas(p) -> bool:
    """Numerar archivos de listas: ausente es falso y no reescribe."""
    crudo = (p.get("descargas", "enumerar", fallback="false").strip().lower()
             if p.has_section("descargas") else "false")
    return crudo in ("true", "1", "yes", "on")


def _rango(valor, defecto, minimo, maximo) -> int:
    """Entero dentro del rango o el defecto, para guardar sin INI."""
    try:
        numero = int(valor)
    except Exception:
        return defecto
    if numero < minimo or numero > maximo:
        return defecto
    return numero


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
        try:
            p.read(ruta, encoding="utf-8")
        except configparser.Error:
            pass
    formato = _formato_descargas(p, ruta)
    bitrate = _bitrate_descargas(p, ruta)
    return {"formato": formato, "bitrate": bitrate,
            "resolucion": _resolucion_descargas(p, ruta),
            "carpeta": _carpeta_descargas(p),
            "enumerar": _enumerar_descargas(p),
            "simultaneas": _entero_descargas(p, ruta, "simultaneas",
                                             SIMULTANEAS_DEFECTO,
                                             SIMULTANEAS_MIN, SIMULTANEAS_MAX),
            "limite": _entero_descargas(p, ruta, "limite", 0, 0, LIMITE_MAX),
            "carpeta_lista": _booleano_descargas(p, "carpeta_lista"),
            "plantilla": _plantilla_descargas(p, ruta)}


def _plantilla_guardada(op: dict) -> str:
    """Plantilla validada contra las que admite la app."""
    plantilla = str(op.get("plantilla", "titulo_id")).strip()
    if plantilla not in _PLANTILLAS_VALIDAS:
        plantilla = "titulo_id"
    return plantilla


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
    bitrate = _rango(op.get("bitrate", 192), 192, 0, 10000)
    if bitrate not in _BITRATES_VALIDOS:
        bitrate = 192
    resolucion = _rango(op.get("resolucion", 0), 0, 0, 10000)
    if resolucion not in RESOLUCIONES:
        resolucion = 0
    carpeta = str(op.get("carpeta") or paths.descargas_por_defecto()).strip()
    enumerar = bool(op.get("enumerar", False))
    simultaneas = _rango(op.get("simultaneas", SIMULTANEAS_DEFECTO),
                         SIMULTANEAS_DEFECTO, SIMULTANEAS_MIN, SIMULTANEAS_MAX)
    limite = _rango(op.get("limite", 0), 0, 0, LIMITE_MAX)
    carpeta_lista = bool(op.get("carpeta_lista", False))
    plantilla = _plantilla_guardada(op)
    guardar_opcion(ruta, "descargas", "formato", formato)
    guardar_opcion(ruta, "descargas", "bitrate", str(bitrate))
    guardar_opcion(ruta, "descargas", "resolucion", str(resolucion))
    guardar_opcion(ruta, "descargas", "carpeta", carpeta)
    guardar_opcion(ruta, "descargas", "enumerar", "true" if enumerar else "false")
    guardar_opcion(ruta, "descargas", "simultaneas", str(simultaneas))
    guardar_opcion(ruta, "descargas", "limite", str(limite))
    guardar_opcion(ruta, "descargas", "carpeta_lista",
                    "true" if carpeta_lista else "false")
    guardar_opcion(ruta, "descargas", "plantilla", plantilla)
