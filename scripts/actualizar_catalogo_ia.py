#!/usr/bin/env python
"""Descarga el catálogo público de modelos de IA y guarda la copia del paquete.

Uso:
    uv run python scripts/actualizar_catalogo_ia.py

Escribe `catalogo_ia.json` en la raíz del repositorio (que en desarrollo es
lo que `paths.carpeta_instalacion()` devuelve) con los modelos con visión
sin deprecados de cada proveedor. El `construir.bat` lleva esa copia en el
paquete. No baja nada fuera de models.dev.
"""

from __future__ import annotations

import datetime
import os
import sys

# Raíz del repositorio: la carpeta de arriba de la suya, como en smoke_test.
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from ytchat.ai import catalogo
from ytchat.ai import protocolos
from ytchat.core import paths


def main() -> int:
    destino = paths.carpeta_instalacion() / "catalogo_ia.json"
    fecha = datetime.date.today().isoformat()
    try:
        reducido = catalogo.descargar(destino, fecha)
    except protocolos.ErrorIA as error:
        print(f"ERROR: {error.tipo}: {error.detalle}")
        return 1
    for ident, entrada in reducido["proveedores"].items():
        lista = entrada["modelos"]
        gratis = sum(1 for modelo in lista if modelo["gratis"])
        print(f"{ident}: {len(lista)} modelos, {gratis} gratis")
    return 0


if __name__ == "__main__":
    sys.exit(main())
