"""Punto único de traducción de la aplicación, con gettext.

Resuelve el idioma una sola vez, en la primera llamada, y guarda la
traducción. Los módulos de la app importan `_` de acá de forma explícita:
no se instala nada en `builtins`, para que las pruebas y las herramientas
lo vean. Cambiar de idioma pide reiniciar la aplicación.

El orden de resolución es la variable de entorno `BELLBIRD_IDIOMA`, la
clave `idioma` de la sección `[ui]` de config.ini y el idioma de la
interfaz de Windows. Un código regional sin catálogo prueba su idioma
base y, si tampoco está, se usa el texto original, que es el español.
"""

from __future__ import annotations

import configparser
import ctypes
import gettext
import locale
import logging
import os
from pathlib import Path

from ytchat.core import paths

logger = logging.getLogger(f"ytchat.{__name__}")

DOMINIO = "bellbird"
IDIOMA_ORIGINAL = "es"
IDIOMA_PSEUDO = "pseudo"

_estado = {
    "codigo": None,
    "traduccion": None,
    "carpeta": None,
}


class _TraduccionPseudo:
    """Marca los textos para ver de un vistazo los que faltan traducir."""

    def gettext(self, texto):
        return f"[¡{texto}!]"

    def ngettext(self, singular, plural, n):
        return f"[¡{singular if n == 1 else plural}!]"

    def pgettext(self, contexto, texto):
        return f"[¡{texto}!]"


def _buscar_codigo(codigo, codigos):
    """Busca el código exacto o su equivalente sin distinguir mayúsculas."""
    if codigo in codigos:
        return codigo
    por_minusculas = {catalogo.lower(): catalogo for catalogo in codigos}
    return por_minusculas.get(codigo.lower())


def elegir_codigo(valor_entorno, valor_config, idioma_windows, codigos):
    """Elige el código de idioma, sin tocar el entorno, el ini ni Windows."""
    elegido = (valor_entorno or "").strip()
    if not elegido:
        elegido = (valor_config or "").strip()
    if not elegido or elegido.lower() == "windows":
        elegido = (idioma_windows or IDIOMA_ORIGINAL).strip()
    if elegido.lower() == IDIOMA_PSEUDO:
        return IDIOMA_PSEUDO
    normalizado = elegido.replace("-", "_")
    encontrado = _buscar_codigo(normalizado, codigos)
    if encontrado:
        return encontrado
    base = normalizado.split("_")[0]
    encontrado = _buscar_codigo(base, codigos)
    if encontrado:
        return encontrado
    return IDIOMA_ORIGINAL


def idioma_windows():
    """Idioma de la interfaz de Windows, o español si no se puede leer."""
    try:
        identificador = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return locale.windows_locale.get(identificador, IDIOMA_ORIGINAL)
    except Exception as exc:
        logger.warning("no se pudo leer el idioma de Windows: %s", exc)
        return IDIOMA_ORIGINAL


def _idioma_config():
    """Valor de `[ui] idioma` en config.ini; `windows` si no se puede leer."""
    ruta = paths.config_ini()
    if not ruta.is_file():
        logger.debug("no hay config.ini, se usa el idioma de Windows")
        return "windows"
    lector = configparser.ConfigParser()
    try:
        leidos = lector.read(ruta, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeDecodeError) as exc:
        logger.warning("no se pudo leer %s: %s", ruta, exc)
        return "windows"
    if not leidos or not lector.has_section("ui"):
        logger.debug("config.ini sin sección [ui], se usa el idioma de Windows")
        return "windows"
    return lector.get("ui", "idioma", fallback="windows")


def codigos_con_catalogo(carpeta=None):
    """Códigos que tienen un catálogo compilado en la carpeta indicada."""
    raiz = Path(carpeta) if carpeta is not None else paths.carpeta_idiomas()
    if not raiz.is_dir():
        return set()
    return {
        ruta.parent.parent.name
        for ruta in raiz.glob(f"*/LC_MESSAGES/{DOMINIO}.mo")
    }


def _cargar(codigo, carpeta):
    """Traducción del código, con el texto original si no hay catálogo."""
    if codigo == IDIOMA_PSEUDO:
        return _TraduccionPseudo()
    try:
        return gettext.translation(
            DOMINIO, localedir=str(carpeta), languages=[codigo],
            fallback=True)
    except Exception as exc:
        logger.warning("no se pudo cargar la traducción %s: %s", codigo, exc)
        return gettext.NullTranslations()


def _instalar_en_memoria(codigo, carpeta):
    _estado["codigo"] = codigo
    _estado["carpeta"] = Path(carpeta)
    _estado["traduccion"] = _cargar(codigo, _estado["carpeta"])
    logger.debug("idioma %s, catálogos en %s", codigo, carpeta)


def instalar(codigo, carpeta=None):
    """Fija el idioma a mano, para pruebas y para el arranque."""
    raiz = Path(carpeta) if carpeta is not None else paths.carpeta_idiomas()
    _instalar_en_memoria(codigo, raiz)


def _resolver():
    if _estado["traduccion"] is not None:
        return
    carpeta = paths.carpeta_idiomas()
    codigo = elegir_codigo(
        os.environ.get("BELLBIRD_IDIOMA", ""),
        _idioma_config(),
        idioma_windows(),
        codigos_con_catalogo(carpeta),
    )
    _instalar_en_memoria(codigo, carpeta)


def idioma_actual():
    """Código de idioma en uso."""
    _resolver()
    return _estado["codigo"]


def _(texto):
    _resolver()
    return _estado["traduccion"].gettext(texto)


def ngettext(singular, plural, n):
    _resolver()
    return _estado["traduccion"].ngettext(singular, plural, n)


def pgettext(contexto, texto):
    _resolver()
    return _estado["traduccion"].pgettext(contexto, texto)


def _reiniciar():
    """Vuelve al estado sin resolver, solo para las pruebas."""
    _estado["codigo"] = None
    _estado["traduccion"] = None
    _estado["carpeta"] = None
