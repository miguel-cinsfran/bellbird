"""Índice de la lista de QA en «Colecciones» para `musica_real`.

Módulo puro: sin wx, sin ventanas, sin red ni disco. Lo usa
`conducir.py` para elegir la lista de QA aunque el dueño tenga listas
propias en `data/listas`. Las pruebas están en
`tests/test_qa_musica_colecciones.py`. Importar este módulo no abre
nada.
"""

from __future__ import annotations


def indice_coleccion_qa(filas, fila_biblioteca, fila_qa) -> int | None:
    """Índice de la fila de QA en «Colecciones», None si no es seguro.

    Devuelve la posición de `fila_qa` cuando la fila 0 es exactamente
    `fila_biblioteca` y `fila_qa` aparece exactamente una vez. En
    cualquier otro caso devuelve None: filas vacías o ausentes,
    Biblioteca con otra cantidad, QA ausente o repetida. Nunca lanza.
    """
    try:
        if filas is None:
            return None
        lista = list(filas)
        if not lista:
            return None
        if lista[0] != fila_biblioteca:
            return None
        halladas = [i for i, fila in enumerate(lista) if fila == fila_qa]
        if len(halladas) != 1:
            return None
        return halladas[0]
    except Exception:
        return None
