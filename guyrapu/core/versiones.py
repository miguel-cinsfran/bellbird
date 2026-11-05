"""Lectura y comparación de números de versión de la app.

La única razón para cambiar de este módulo es cómo se lee y se ordena un
número de versión.
"""

from __future__ import annotations

import re


# ── Versiones ─────────────────────────────────────────────────────────────

_VERSION_RE = re.compile(r"^v?(\d+(?:\.\d+)*)(?:-beta\.(\d+))?$")


def version_como_tupla(texto: str | None) -> tuple[int, ...] | None:
    """Convierte un texto de versión en tupla de enteros comparable.

    "v2.10.0", "2.10.0" y "2.10" dan tuplas; "2.10" equivale a "2.10.0".
    "3.0.0-beta.1" suma `(-1, 1)`; otro sufijo devuelve None.
    """
    if not isinstance(texto, str):
        return None
    encontrado = _VERSION_RE.match(texto.strip())
    if not encontrado:
        return None
    partes = tuple(int(p) for p in encontrado.group(1).split("."))
    partes += (0,) * (3 - len(partes))
    beta = encontrado.group(2)
    return partes + (-1, int(beta)) if beta else partes


def orden_version(tupla: tuple[int, ...] | None) -> tuple[float, ...] | None:
    """Clave de orden de una tupla de versión.

    Una estable lleva `float("inf")` al final para quedar por encima de sus
    betas, que ya traen el `-1` en la cuarta posición. Comparar las tuplas a
    pelo dejaría la estable antes que sus propias betas.
    """
    if tupla is None:
        return None
    if len(tupla) >= 5 and tupla[-2] == -1:
        return tupla
    return tupla + (float("inf"),)


def hay_version_nueva(actual: str | None, publicada: str | None) -> bool:
    """Verdadero solo si la publicada es estrictamente mayor. Nunca compara textos."""
    tupla_actual = version_como_tupla(actual)
    tupla_publicada = version_como_tupla(publicada)
    if tupla_actual is None or tupla_publicada is None:
        return False
    return orden_version(tupla_publicada) > orden_version(tupla_actual)


def debe_avisar(version_publicada: str | None, version_actual: str | None,
                ultima_avisada: str | None) -> bool:
    """Verdadero solo si hay versión nueva y todavía no se avisó esa.

    La avisada se compara como tupla, así «2.10» y «2.10.0» cuentan como
    la misma y no se repite el aviso.
    """
    if not hay_version_nueva(version_actual, version_publicada):
        return False
    return (version_como_tupla(version_publicada)
            != version_como_tupla(ultima_avisada))
