"""Entradas y despliegue de los menús contextuales de la ventana de música.

Las entradas se arman con funciones puras que devuelven pares
(etiqueta, acción), para poder comprobarlas sin mostrar el menú. Una acción
que es una lista de entradas se despliega como submenú. El despliegue es lo
único que toca wx.
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
ACCION_EDITAR_LISTA = "editar_lista"
ACCION_REPRODUCIR_COLECCION = "reproducir_coleccion"
ACCION_AGREGAR_COLECCION = "agregar_coleccion"
ACCION_NUEVA_LISTA = "nueva_lista"
ACCION_NUEVA_LISTA_CON_TEMA = "nueva_lista_con_tema"

ACCION_REPRODUCIR = "reproducir"
ACCION_QUITAR = "quitar"
ACCION_SUBIR = "subir"
ACCION_BAJAR = "bajar"
ACCION_IR_AL_QUE_SUENA = "ir_al_que_suena"
ACCION_MEZCLAR = "mezclar"
ACCION_VACIAR = "vaciar"
ACCION_GUARDAR_COLA = "guardar_cola"


def entradas_agregar_a_lista(nombres) -> list:
    """Una entrada por lista propia y, al final, la de crear una nueva."""
    entradas = [
        (str(nombre), (ACCION_AGREGAR_A_LISTA, str(nombre)))
        for nombre in (nombres or ())
    ]
    entradas.append(("&Nueva lista…", ACCION_NUEVA_LISTA_CON_TEMA))
    return entradas


def entradas_biblioteca(es_lista_propia: bool, nombres_listas=()) -> list:
    """Las entradas del menú de la Biblioteca, según la fuente elegida."""
    entradas = [
        ("Reproducir &ahora", ACCION_AHORA),
        ("Reproducir a &continuación", ACCION_CONTINUACION),
        ("A&gregar a la cola", ACCION_AGREGAR),
        ("Reproducir &todo desde aquí", ACCION_TODO_DESDE_AQUI),
        ("Agregar a una &lista", entradas_agregar_a_lista(nombres_listas)),
    ]
    if es_lista_propia:
        entradas += [
            ("&Quitar de esta lista", ACCION_QUITAR_DE_LISTA),
        ]
    return entradas


def entradas_colecciones(es_lista: bool) -> list:
    """Las entradas del menú de «Colecciones», según lo elegido."""
    entradas = [
        ("&Reproducir", ACCION_REPRODUCIR_COLECCION),
        ("A&gregar a la cola", ACCION_AGREGAR_COLECCION),
    ]
    if es_lista:
        entradas += [
            ("&Editar la lista…", ACCION_EDITAR_LISTA),
            ("Re&nombrar la lista…", ACCION_RENOMBRAR_LISTA),
            ("&Borrar la lista…", ACCION_BORRAR_LISTA),
        ]
    entradas.append(("&Nueva lista…", ACCION_NUEVA_LISTA))
    return entradas


def entradas_cola() -> list:
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


def _agregar_entradas(menu, entradas, al_elegir) -> None:
    """Engancha cada entrada en el menú que la contiene."""
    for etiqueta, accion in entradas:
        if isinstance(accion, list):
            submenu = wx.Menu()
            menu.AppendSubMenu(submenu, etiqueta)
            _agregar_entradas(submenu, accion, al_elegir)
            continue
        ident = wx.NewIdRef()
        menu.Append(ident, etiqueta)
        menu.Bind(
            wx.EVT_MENU, lambda _evento, accion=accion: al_elegir(accion),
            id=ident)


def mostrar_menu(ventana, entradas, al_elegir) -> None:
    """Muestra las entradas y despacha la acción elegida."""
    menu = wx.Menu()
    try:
        _agregar_entradas(menu, entradas, al_elegir)
        ventana.PopupMenu(menu)
    finally:
        menu.Destroy()
