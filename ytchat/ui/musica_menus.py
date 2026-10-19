"""Entradas y despliegue de los menús contextuales de la ventana de música.

Las entradas se arman con funciones puras que devuelven pares
(etiqueta, acción), para poder comprobarlas sin mostrar el menú. El
despliegue es lo único que toca wx.
"""

from __future__ import annotations

import wx

ACCION_AHORA = "ahora"
ACCION_CONTINUACION = "continuacion"
ACCION_AGREGAR = "agregar"
ACCION_TODO_DESDE_AQUI = "todo_desde_aqui"
ACCION_AGREGAR_A_LISTA = "agregar_a_lista"
ACCION_QUITAR_DE_LISTA = "quitar_de_lista"
ACCION_RENOMBRAR_LISTA = "renombrar_lista"
ACCION_BORRAR_LISTA = "borrar_lista"

ACCION_REPRODUCIR = "reproducir"
ACCION_QUITAR = "quitar"
ACCION_SUBIR = "subir"
ACCION_BAJAR = "bajar"
ACCION_IR_AL_QUE_SUENA = "ir_al_que_suena"
ACCION_MEZCLAR = "mezclar"
ACCION_VACIAR = "vaciar"
ACCION_GUARDAR_COLA = "guardar_cola"


def entradas_biblioteca(es_lista_propia: bool) -> list[tuple[str, str]]:
    """Las entradas del menú de la Biblioteca, según la fuente elegida."""
    entradas = [
        ("Reproducir &ahora", ACCION_AHORA),
        ("Reproducir a &continuación", ACCION_CONTINUACION),
        ("A&gregar a la cola", ACCION_AGREGAR),
        ("Reproducir &todo desde aquí", ACCION_TODO_DESDE_AQUI),
        ("Agregar a una &lista…", ACCION_AGREGAR_A_LISTA),
    ]
    if es_lista_propia:
        entradas += [
            ("&Quitar de esta lista", ACCION_QUITAR_DE_LISTA),
            ("&Renombrar esta lista…", ACCION_RENOMBRAR_LISTA),
            ("&Borrar esta lista…", ACCION_BORRAR_LISTA),
        ]
    return entradas


def entradas_cola() -> list[tuple[str, str]]:
    """Las entradas del menú de la Cola."""
    return [
        ("&Reproducir", ACCION_REPRODUCIR),
        ("&Quitar", ACCION_QUITAR),
        ("&Subir", ACCION_SUBIR),
        ("&Bajar", ACCION_BAJAR),
        ("&Ir al que suena", ACCION_IR_AL_QUE_SUENA),
        ("&Mezclar la cola", ACCION_MEZCLAR),
        ("&Vaciar la cola", ACCION_VACIAR),
        ("&Guardar la cola como lista…", ACCION_GUARDAR_COLA),
    ]


def mostrar_menu(ventana, entradas, al_elegir) -> None:
    """Muestra las entradas y despacha la acción elegida."""
    menu = wx.Menu()
    try:
        for etiqueta, accion in entradas:
            ident = wx.NewIdRef()
            menu.Append(ident, etiqueta)
            menu.Bind(
                wx.EVT_MENU, lambda _evento, accion=accion: al_elegir(accion),
                id=ident)
        ventana.PopupMenu(menu)
    finally:
        menu.Destroy()
