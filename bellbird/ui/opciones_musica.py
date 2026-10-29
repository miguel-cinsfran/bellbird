"""Opciones de salida de audio para la página Música de Preferencias.

Lógica pura, sin wx: arma la lista del combinado de salida a partir del
identificador guardado y de lo que anuncia libVLC. La página la usa al abrir
(con lista vacía, sin consultar VLC) y al terminar la búsqueda pedida con el
botón; los controles viven en `gui_preferencias`.
"""

from __future__ import annotations

from bellbird.core.idioma import _, N_

# Traductores: primera opción del combinado de salida de música; la que elige el sistema.
ETIQUETA_PREDETERMINADA = N_("Salida predeterminada")


def opciones_salida(guardada_id, guardada_nombre, encontradas):
    """Etiquetas, identificadores y selección del combinado de salida.

    La primera opción es siempre la predeterminada, con id "". Después va
    cada par `(id, nombre)` de `encontradas`, saltando el de id "" (libVLC
    lista el predeterminado con id vacío) y los repetidos. Si la guardada
    no está entre las encontradas, se agrega igual con su nombre guardado
    (o el id si no hay nombre), para no perderla. La selección es el índice
    de la guardada, o 0 si no hay guardada.
    """
    etiquetas = [_(ETIQUETA_PREDETERMINADA)]
    identificadores = [""]
    vistos = {""}
    for par in encontradas or []:
        ident, nombre = par
        ident = ident or ""
        if ident in vistos:
            continue
        vistos.add(ident)
        identificadores.append(ident)
        etiquetas.append(nombre or ident)
    guardada_id = guardada_id or ""
    if guardada_id and guardada_id not in vistos:
        identificadores.append(guardada_id)
        etiquetas.append(guardada_nombre or guardada_id)
    seleccion = identificadores.index(guardada_id) if guardada_id else 0
    return etiquetas, identificadores, seleccion
