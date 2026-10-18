"""Textos que muestra la ventana de música, sin wx.

Funciones puras: arman las filas de las dos listas y el resumen de la
biblioteca. La ventana las usa tal cual, así lo que se ve se puede probar
sin abrir nada.
"""

from __future__ import annotations

from ytchat.music.anuncios import nombre_tema


def filas_temas(temas, incluir_artista: bool) -> list[str]:
    """Una fila por tema, en el orden de la lista."""
    return [nombre_tema(tema, incluir_artista) for tema in temas]


def filas_cola(estado, incluir_artista: bool) -> list[str]:
    """Una fila por tema de la cola, numerada desde 1.

    La del tema actual empieza por «Sonando: » (o «En pausa: » si está en
    pausa). Sin tema sonando, ninguna lleva prefijo. Cola vacía: lista vacía.
    """
    actual = None if estado.terminado else estado.posicion
    filas = []
    for indice, tema in enumerate(estado.cola):
        texto = f"{indice + 1}. {nombre_tema(tema, incluir_artista)}"
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
    return "tema" if cantidad == 1 else "temas"
