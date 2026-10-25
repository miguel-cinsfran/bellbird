"""Filtros y orden de la biblioteca de música, sin interfaz.

Los artistas se separan por «&», por «feat.» o «ft.» y por coma. Las
claves y la comparación van sin tildes ni mayúsculas, para que la misma
persona caiga en el mismo grupo aunque esté escrita distinto.
"""

from __future__ import annotations

import re
import unicodedata

TODAS = ""
SIN_ARTISTA = "sin artista"

CRITERIO_COLECCION = "coleccion"
CRITERIO_TITULO = "titulo"
CRITERIO_ARTISTA = "artista"
CRITERIO_RECIENTES = "recientes"
CRITERIO_DURACION = "duracion"

CRITERIOS = (
    (CRITERIO_COLECCION, "Orden de la colección"),
    (CRITERIO_TITULO, "Título"),
    (CRITERIO_ARTISTA, "Artista"),
    (CRITERIO_RECIENTES, "Más recientes primero"),
    (CRITERIO_DURACION, "Duración"),
)

_SEPARADOR = re.compile(r"\s*(?:&|,|\b(?:feat|ft)\b\.?)\s*", re.IGNORECASE)


def clave_artista(texto) -> str:
    """El artista en minúsculas y sin tildes, para comparar y ordenar."""
    descompuesto = unicodedata.normalize("NFKD", str(texto or ""))
    sin_tildes = "".join(
        caracter for caracter in descompuesto
        if not unicodedata.combining(caracter))
    return sin_tildes.casefold().strip()


def artistas_de(tema) -> tuple[str, ...]:
    """Los artistas del tema, separados y sin repetir."""
    artista = str(getattr(tema, "artista", "") or "")
    nombres = []
    vistos = set()
    for parte in _SEPARADOR.split(artista):
        nombre = " ".join(parte.split())
        clave = clave_artista(nombre)
        if not clave or clave in vistos:
            continue
        vistos.add(clave)
        nombres.append(nombre)
    return tuple(nombres)


def opciones_artistas(temas) -> tuple[tuple[str, str], ...]:
    """Las opciones del cuadro «Mostrar», como pares (clave, etiqueta).

    Primero «Todas las canciones», después cada artista con su cantidad en
    orden alfabético y al final «Sin artista» si hay canciones sin artista.
    La etiqueta es la del primer tema que trae ese artista.
    """
    grupos = {}
    sin_artista = 0
    for tema in temas:
        nombres = artistas_de(tema)
        if not nombres:
            sin_artista += 1
            continue
        for nombre in nombres:
            clave = clave_artista(nombre)
            if clave not in grupos:
                grupos[clave] = [nombre, 0]
            grupos[clave][1] += 1
    opciones = [(TODAS, "Todas las canciones")]
    for clave in sorted(grupos):
        nombre, cantidad = grupos[clave]
        opciones.append((clave, f"{nombre}, {_cantidad(cantidad)}"))
    if sin_artista:
        opciones.append(
            (SIN_ARTISTA, f"Sin artista, {_cantidad(sin_artista)}"))
    return tuple(opciones)


def filtrar_por_artista(temas, clave):
    """Los temas que tienen ese artista; con la clave de «Todas», todos."""
    clave = str(clave or "")
    if not clave:
        return tuple(temas)
    if clave == SIN_ARTISTA:
        return tuple(tema for tema in temas if not artistas_de(tema))
    buscada = clave_artista(clave)
    return tuple(
        tema for tema in temas
        if any(clave_artista(nombre) == buscada
               for nombre in artistas_de(tema)))


def normalizar_criterio(criterio) -> str:
    """El criterio si es válido; si no, el orden de la colección."""
    validos = {clave for clave, _etiqueta in CRITERIOS}
    return criterio if criterio in validos else CRITERIO_COLECCION


def ordenar(temas, criterio):
    """Los mismos temas ordenados; estable y sin tildes ni mayúsculas.

    «recientes» va por fecha descendente y «duración» por duración
    ascendente. El orden de la colección los deja tal cual.
    """
    criterio = normalizar_criterio(criterio)
    temas = tuple(temas)
    if criterio == CRITERIO_TITULO:
        return tuple(sorted(temas, key=lambda tema: clave_artista(tema.titulo)))
    if criterio == CRITERIO_ARTISTA:
        return tuple(sorted(
            temas, key=lambda tema: clave_artista(tema.artista)))
    if criterio == CRITERIO_RECIENTES:
        return tuple(sorted(
            temas, key=lambda tema: -_entero(tema.fecha_ns)))
    if criterio == CRITERIO_DURACION:
        return tuple(sorted(
            temas, key=lambda tema: _entero(tema.duracion_ms)))
    return temas


def _cantidad(cantidad: int) -> str:
    """«1 canción» o «N canciones»."""
    return "1 canción" if cantidad == 1 else f"{cantidad} canciones"


def _entero(valor) -> int:
    """Un entero del modelo, sin booleanos; cualquier otra cosa vale 0."""
    if isinstance(valor, bool) or not isinstance(valor, int):
        return 0
    return valor
