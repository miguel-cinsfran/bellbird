"""Textos que muestra la ventana de música, sin wx.

Funciones puras: arman las filas de las dos listas y el resumen de la
biblioteca. La ventana las usa tal cual, así lo que se ve se puede probar
sin abrir nada.
"""

from __future__ import annotations

import unicodedata

from ytchat.music import anuncios
from ytchat.music.anuncios import nombre_tema

ETIQUETA_BIBLIOTECA = "Biblioteca"

TEXTO_AYUDA_COLECCIONES = (
    "Intro reproduce la colección entera, Suprimir borra la lista, "
    "tecla de aplicaciones para más opciones")
TEXTO_COLA_OCULTA = "Cola oculta"


def _plegar(texto) -> str:
    """Minúsculas y sin tildes, para comparar búsquedas."""
    descompuesto = unicodedata.normalize("NFKD", str(texto or ""))
    sin_tildes = "".join(
        caracter for caracter in descompuesto
        if not unicodedata.combining(caracter))
    return sin_tildes.casefold()


def filtrar_lista(temas, texto) -> tuple:
    """Los temas de una lista que coinciden con el texto, sin tocar el disco.

    Mira título, artista y álbum, con la misma tolerancia a mayúsculas y
    tildes que la búsqueda de la carpeta.
    """
    aguja = _plegar(texto).strip()
    if not aguja:
        return tuple(temas)
    return tuple(
        tema for tema in temas
        if any(aguja in _plegar(campo)
               for campo in (tema.titulo, tema.artista, tema.album)))


def filtrar_biblioteca(biblioteca, texto) -> tuple:
    """El filtro de la carpeta, delegado en `Biblioteca.buscar`."""
    if not _plegar(texto).strip():
        return tuple(biblioteca.temas())
    return tuple(biblioteca.buscar(texto))


def filtrar_fuente(temas, texto, biblioteca=None) -> tuple:
    """El filtro que corresponde a la colección elegida."""
    if biblioteca is not None:
        return filtrar_biblioteca(biblioteca, texto)
    return filtrar_lista(temas, texto)


def filas_colecciones(nombres, cantidad_biblioteca=None,
                      cantidades=None) -> list[str]:
    """Las filas de «Colecciones», con la cantidad cuando se conoce.

    Cada fila es el nombre y dos puntos con la cantidad. Sin cantidad
    va solo el nombre: la carpeta todavía cargando o una lista ilegible.
    """
    cantidades = cantidades or {}
    filas = [_fila_coleccion(ETIQUETA_BIBLIOTECA, cantidad_biblioteca)]
    filas.extend(_fila_coleccion(str(nombre), cantidades.get(str(nombre)))
                 for nombre in nombres)
    return filas


def _fila_coleccion(nombre, cantidad) -> str:
    """Una fila de «Colecciones»: el nombre y la cantidad si se sabe."""
    if cantidad is None:
        return nombre
    return f"{nombre}: {cantidad}"


def texto_cola_visible(cantidad: int) -> str:
    """Cuántos temas hay al mostrar la Cola."""
    cantidad = max(0, int(cantidad))
    if cantidad == 0:
        return "Cola visible, vacía"
    if cantidad == 1:
        return "Cola visible, 1 canción"
    return f"Cola visible, {cantidad} canciones"


def texto_coincidencias(cantidad: int) -> str:
    """Cuántos temas coinciden, para anunciar después de teclear."""
    cantidad = max(0, int(cantidad))
    if cantidad == 0:
        return anuncios.TEXTO_NINGUN_TEMA_COINCIDE
    if cantidad == 1:
        return anuncios.TEXTO_UN_TEMA_COINCIDE
    return anuncios.TEXTO_TEMAS_COINCIDEN.format(cantidad=cantidad)


def indice_seleccion_tras_refrescar(indice, total) -> int:
    """El índice que hay que seleccionar después de recargar una lista.

    Conserva el mismo índice recortado al total. Sin selección o sin filas
    devuelve -1, que es el valor de «ninguna» en wx.
    """
    total = max(0, int(total))
    if total == 0 or indice is None or int(indice) < 0:
        return -1
    return min(int(indice), total - 1)


def ayuda_biblioteca(es_lista_propia: bool) -> str:
    """La ayuda de teclas de la Biblioteca."""
    if es_lista_propia:
        return anuncios.TEXTO_AYUDA_BIBLIOTECA_LISTA
    return anuncios.TEXTO_AYUDA_BIBLIOTECA


def ayuda_colecciones() -> str:
    """La ayuda de teclas de la lista de colecciones."""
    return TEXTO_AYUDA_COLECCIONES


def ayuda_cola() -> str:
    """La ayuda de teclas de la Cola."""
    return anuncios.TEXTO_AYUDA_COLA


def ayuda_buscar() -> str:
    """La ayuda de teclas del buscador."""
    return anuncios.TEXTO_AYUDA_BUSCAR


def texto_duracion(ms) -> str:
    """La duración como m:ss, o h:mm:ss desde una hora. Vacía si no se sabe."""
    segundos = ms // 1000 if isinstance(ms, int) and not isinstance(ms, bool) else 0
    if segundos <= 0:
        return ""
    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)
    if horas:
        return f"{horas}:{minutos:02d}:{segundos:02d}"
    return f"{minutos}:{segundos:02d}"


def fila_tema(tema) -> str:
    """El título y, separados por coma, el artista y la duración que haya."""
    partes = [nombre_tema(tema, False)]
    if tema.artista:
        partes.append(tema.artista)
    duracion = texto_duracion(tema.duracion_ms)
    if duracion:
        partes.append(duracion)
    return ", ".join(partes)


def filas_temas(temas) -> list[str]:
    """Una fila por tema, en el orden de la lista."""
    return [fila_tema(tema) for tema in temas]


def filas_cola(estado) -> list[str]:
    """Una fila por tema de la cola, numerada desde 1.

    La del tema actual empieza por «Sonando: » (o «En pausa: » si está en
    pausa). Sin tema sonando, ninguna lleva prefijo. Cola vacía: lista vacía.
    """
    actual = None if estado.terminado else estado.posicion
    filas = []
    for indice, tema in enumerate(estado.cola):
        texto = f"{indice + 1}. {fila_tema(tema)}"
        if actual == indice:
            prefijo = "En pausa: " if estado.pausado else "Sonando: "
            texto = prefijo + texto
        filas.append(texto)
    return filas


def texto_resumen(cantidad_total: int, cantidad_filtrada: int,
                  buscando: bool) -> str:
    """Cuántos temas hay, con o sin búsqueda.

    «120 temas en la carpeta», o buscando «8 de 120 temas». El singular va
    con la cantidad de la que habla el sustantivo: «1 tema en la carpeta» y
    «1 de 1 tema».
    """
    total = max(0, int(cantidad_total))
    filtrada = max(0, int(cantidad_filtrada))
    if buscando:
        return f"{filtrada} de {total} {_sustantivo(total)}"
    return f"{total} {_sustantivo(total)} en la carpeta"


def _sustantivo(cantidad: int) -> str:
    return "canción" if cantidad == 1 else "canciones"


TEXTO_CARPETA_EXAMINADA_SIN_CAMBIOS = "Carpeta examinada: sin cambios."


def texto_carpeta_examinada(nuevas: int, quitadas: int) -> str:
    """El anuncio tras examinar la carpeta a mano.

    Sin cambios dice que no hubo; si no, cuántas canciones nuevas y
    quitadas, en singular con 1 y omitiendo la parte que sea cero.
    """
    partes = _partes_examen(nuevas, quitadas)
    if not partes:
        return TEXTO_CARPETA_EXAMINADA_SIN_CAMBIOS
    return f"Carpeta examinada: {' y '.join(partes)}."


def _partes_examen(nuevas, quitadas) -> list:
    """Las partes del anuncio del examen, sin la parte que sea cero."""
    nuevas = max(0, int(nuevas))
    quitadas = max(0, int(quitadas))
    partes = []
    if nuevas:
        partes.append(f"{nuevas} canción nueva"
                      if nuevas == 1 else f"{nuevas} canciones nuevas")
    if quitadas:
        partes.append("1 quitada" if quitadas == 1 else f"{quitadas} quitadas")
    return partes
