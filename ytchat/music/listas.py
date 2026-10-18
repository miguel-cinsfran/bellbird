"""Listas de música propias, en archivos `.m3u8`, sin interfaz.

Cada función recibe la carpeta donde viven las listas: el módulo nunca arma
una ruta fija ni toca la configuración. Para leer reutiliza
`Biblioteca.cargar_m3u8`, así lo que se escribe y lo que se lee van por el
mismo camino. Sin wx y sin VLC, para poder probarlo solo.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

from ytchat.core.archivos import escribir_texto_atomico
from ytchat.music.biblioteca import Biblioteca, ErrorBiblioteca
from ytchat.music.modelo import Tema


EXTENSION = ".m3u8"
# Así se le muestran al usuario. El nombre sí puede llevar espacios: solo se
# recortan los de los extremos, y por eso el conjunto que valida no los tiene.
CARACTERES_PROHIBIDOS = '\\ / : * ? " < > |'
_CARACTERES_INVALIDOS = frozenset('\\/:*?"<>|')

TEXTO_NOMBRE_VACIO = "Escribe un nombre para la lista"
TEXTO_NOMBRE_INVALIDO = f"El nombre no puede tener {CARACTERES_PROHIBIDOS}"
TEXTO_DUPLICADO = "Ya hay una lista con ese nombre"
TEXTO_NO_EXISTE = "No existe la lista: {nombre}"
TEXTO_POSICION = "No hay un tema en la posición {posicion}"


class ErrorListas(ValueError):
    """Nombre inválido, lista inexistente o fallo al leer o escribir."""


def _plegar(texto: str) -> str:
    """Minúsculas y sin tildes, para ordenar y comparar nombres."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return sin_tildes.casefold()


def _ruta(carpeta, nombre) -> Path:
    return Path(carpeta) / f"{nombre}{EXTENSION}"


def _existente(carpeta, nombre) -> Path | None:
    """La ruta del archivo de esa lista, comparando sin distinguir mayúsculas."""
    base = Path(carpeta)
    if not base.is_dir():
        return None
    objetivo = _plegar(nombre)
    for ruta in base.iterdir():
        if ruta.is_file() and ruta.suffix.lower() == EXTENSION \
                and _plegar(ruta.stem) == objetivo:
            return ruta
    return None


def nombres(carpeta) -> list[str]:
    """Los nombres de las listas (sin `.m3u8`), ordenados sin tildes."""
    base = Path(carpeta)
    if not base.is_dir():
        return []
    encontrados = [ruta.stem for ruta in base.iterdir()
                   if ruta.is_file() and ruta.suffix.lower() == EXTENSION]
    return sorted(encontrados, key=_plegar)


def validar_nombre(nombre) -> str:
    """Recorta los espacios y comprueba el nombre. Devuelve el limpio."""
    limpio = (nombre or "").strip()
    if not limpio:
        raise ErrorListas(TEXTO_NOMBRE_VACIO)
    if any(caracter in _CARACTERES_INVALIDOS for caracter in limpio):
        raise ErrorListas(TEXTO_NOMBRE_INVALIDO)
    return limpio


def crear(carpeta, nombre) -> str:
    """Crea una lista vacía. Devuelve el nombre limpio."""
    limpio = validar_nombre(nombre)
    if _existente(carpeta, limpio) is not None:
        raise ErrorListas(TEXTO_DUPLICADO)
    base = Path(carpeta)
    base.mkdir(parents=True, exist_ok=True)
    escribir_texto_atomico(_ruta(base, limpio), "#EXTM3U\n")
    return limpio


def renombrar(carpeta, viejo, nuevo) -> str:
    """Cambia el nombre de una lista. Devuelve el nombre nuevo."""
    origen = _existente(carpeta, viejo)
    if origen is None:
        raise ErrorListas(TEXTO_NO_EXISTE.format(nombre=viejo))
    limpio = validar_nombre(nuevo)
    if _plegar(limpio) == _plegar(origen.stem):
        return origen.stem
    if _existente(carpeta, limpio) is not None:
        raise ErrorListas(TEXTO_DUPLICADO)
    origen.rename(_ruta(origen.parent, limpio))
    return limpio


def borrar(carpeta, nombre) -> None:
    """Elimina el archivo de una lista."""
    ruta = _existente(carpeta, nombre)
    if ruta is None:
        raise ErrorListas(TEXTO_NO_EXISTE.format(nombre=nombre))
    ruta.unlink()


def guardar(carpeta, nombre, temas) -> str:
    """Escribe la lista con esos temas, encima de lo que hubiera.

    Devuelve el nombre limpio, igual que `crear`, para poder anunciarlo.
    """
    limpio = validar_nombre(nombre)
    base = Path(carpeta)
    base.mkdir(parents=True, exist_ok=True)
    escribir_texto_atomico(_ruta(base, limpio), _texto_de(temas))
    return limpio


def cargar(carpeta, nombre) -> tuple[tuple[Tema, ...], int]:
    """Lee una lista y devuelve los temas y cuántas líneas se saltaron."""
    ruta = _existente(carpeta, nombre)
    if ruta is None:
        raise ErrorListas(TEXTO_NO_EXISTE.format(nombre=nombre))
    try:
        return Biblioteca(ruta.parent).cargar_m3u8(ruta)
    except ErrorBiblioteca as exc:
        raise ErrorListas(str(exc)) from exc


def agregar(carpeta, nombre, temas) -> None:
    """Suma temas al final de una lista que ya existe."""
    actuales, _saltadas = cargar(carpeta, nombre)
    guardar(carpeta, nombre, (*actuales, *temas))


def quitar(carpeta, nombre, indice) -> None:
    """Quita el tema de esa posición y guarda la lista."""
    actuales, _saltadas = cargar(carpeta, nombre)
    if indice < 0 or indice >= len(actuales):
        raise ErrorListas(TEXTO_POSICION.format(posicion=indice + 1))
    guardar(carpeta, nombre, actuales[:indice] + actuales[indice + 1:])


def mover(carpeta, nombre, indice, paso) -> int:
    """Mueve el tema y devuelve su posición nueva, sin pasarse de los bordes."""
    actuales, _saltadas = cargar(carpeta, nombre)
    if indice < 0 or indice >= len(actuales):
        raise ErrorListas(TEXTO_POSICION.format(posicion=indice + 1))
    destino = max(0, min(len(actuales) - 1, indice + paso))
    if destino == indice:
        return indice
    lista = list(actuales)
    lista.insert(destino, lista.pop(indice))
    guardar(carpeta, nombre, tuple(lista))
    return destino


def _texto_de(temas) -> str:
    lineas = ["#EXTM3U"]
    for tema in temas:
        lineas.append(f"#EXTINF:-1,{_titulo(tema)}")
        lineas.append(tema.origen if tema.es_enlace
                      else str(Path(tema.origen).resolve()))
    return "\n".join(lineas) + "\n"


def _titulo(tema) -> str:
    if tema.titulo:
        return tema.titulo.replace("\n", " ").strip()
    if tema.es_enlace:
        return tema.origen
    return Path(tema.origen).stem
