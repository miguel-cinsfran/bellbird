"""Cómo se escribe una versión para que la lea una persona.

Una versión SemVer se muestra sin la «v» inicial y sin los guiones y puntos
de la preversión: «3.0.0-beta.2» se lee «3.0.0 beta 2». La comparación de
versiones sigue usando el texto original; esto es solo para mostrar.
"""

from __future__ import annotations

import re

_RE_VERSION = re.compile(
    r"^\s*[vV]?(\d+(?:\.\d+)*)(?:-([0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*))?\s*$")


def version_legible(version):
    """La versión tal como se lee y se oye, o el texto intacto si no se entiende."""
    if not isinstance(version, str):
        return version
    coincidencia = _RE_VERSION.match(version)
    if not coincidencia:
        return version
    base, previa = coincidencia.group(1), coincidencia.group(2)
    if previa is None:
        return base
    return f"{base} {previa.replace('.', ' ')}"
