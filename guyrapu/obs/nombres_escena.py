"""Textos y nombres de las escenas de OBS, sin interfaz."""

from __future__ import annotations

from guyrapu.core.idioma import _, ngettext

NOMBRE_VACIO = "vacio"
NOMBRE_REPETIDO = "repetido"


def texto_de_fila(nombre, cantidad, actual=False) -> str:
    """La fila de la lista: nombre, si es la actual y cuántas fuentes tiene."""
    partes = [nombre]
    if actual:
        partes.append(_("escena actual"))
    if cantidad:
        partes.append(ngettext("{n} fuente", "{n} fuentes", cantidad).format(
            n=cantidad))
    else:
        partes.append(_("sin fuentes"))
    return ", ".join(partes)


def nombre_libre(ocupados) -> str:
    """El primer «Escena N» que no esté en uso."""
    numero = 1
    while True:
        nombre = _("Escena {n}").format(n=numero)
        if nombre not in ocupados:
            return nombre
        numero += 1


def nombre_de_copia(nombre, ocupados) -> str:
    """«{nombre} - copia», o el primero con número libre si ya existe."""
    copia = _("{nombre} - copia").format(nombre=nombre)
    if copia not in ocupados:
        return copia
    numero = 2
    while True:
        copia = _("{nombre} - copia {n}").format(nombre=nombre, n=numero)
        if copia not in ocupados:
            return copia
        numero += 1


def validar_nombre(nombre, ocupados, excepto="") -> str:
    """Por qué no sirve el nombre, o vacío si sirve.

    `excepto` es la escena que se está renombrando: su nombre actual no
    cuenta como repetido.
    """
    limpio = (nombre or "").strip()
    if not limpio:
        return NOMBRE_VACIO
    if any(limpio == otro and limpio != excepto for otro in ocupados):
        return NOMBRE_REPETIDO
    return ""
