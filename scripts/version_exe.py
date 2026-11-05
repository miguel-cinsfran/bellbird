#!/usr/bin/env python
"""Genera el archivo de metadatos de versión de Windows para PyInstaller.

Todos los datos salen de `config.py`, que es la fuente única. El archivo se
pasa a PyInstaller con `--version-file` y queda dentro del ejecutable.

Uso:
    uv run python scripts/version_exe.py RUTA
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from guyrapu.core import config  # noqa: E402
from guyrapu.core.version_legible import version_legible  # noqa: E402


AUTOR = "Miguel Ángel Insfrán Caballero"
COPYRIGHT = (f"Copyright (C) 2026 {AUTOR}. "
             "GPL-3.0 con condiciones adicionales.")


def _numeros(version: str) -> tuple[int, int, int, int]:
    """Los tres números de la versión y un cero, para FileVersion."""
    base = str(version or "").split("-", 1)[0]
    partes = [int(numero) for numero in re.findall(r"\d+", base)][:3]
    while len(partes) < 3:
        partes.append(0)
    return (partes[0], partes[1], partes[2], 0)


def componer(version: str | None = None) -> str:
    """El texto del archivo de versión con los campos que pide Windows."""
    version = config.APP_VERSION if version is None else version
    numeros = _numeros(version)
    fijos = ", ".join(str(numero) for numero in numeros)
    campos = [
        ("CompanyName", AUTOR),
        ("FileDescription", config.APP_NAME),
        ("FileVersion", ".".join(str(numero) for numero in numeros)),
        ("LegalCopyright", COPYRIGHT),
        ("OriginalFilename", f"{config.APP_NAME}.exe"),
        ("ProductName", config.APP_NAME),
        ("ProductVersion", version_legible(version)),
    ]
    cadenas = ",\n".join(
        f"          StringStruct({nombre!r}, {valor!r})"
        for nombre, valor in campos)
    return (
        "# UTF-8\n"
        "VSVersionInfo(\n"
        "  ffi=FixedFileInfo(\n"
        f"    filevers=({fijos}),\n"
        f"    prodvers=({fijos}),\n"
        "    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,\n"
        "    date=(0, 0)\n"
        "  ),\n"
        "  kids=[\n"
        "    StringFileInfo([\n"
        "      StringTable('040904B0', [\n"
        f"{cadenas}\n"
        "      ])\n"
        "    ]),\n"
        "    VarFileInfo([VarStruct('Translation', [1033, 1200])])\n"
        "  ]\n"
        ")\n"
    )


def escribir(ruta: str | Path, version: str | None = None) -> Path:
    """Escribe el archivo de versión en `ruta` y la devuelve."""
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(componer(version), encoding="utf-8")
    return destino


def main(argumentos=None) -> int:
    parser = argparse.ArgumentParser(
        description="Genera el archivo de metadatos de versión del ejecutable.")
    parser.add_argument("ruta", help="archivo de salida para --version-file")
    opciones = parser.parse_args(argumentos)
    escribir(opciones.ruta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
