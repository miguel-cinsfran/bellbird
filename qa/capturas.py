"""Nombres, deduplicación e índice de las capturas del banco de QA.

Módulo puro: sin wx, sin ventanas, sin red. Lo usa `conducir.py` para
decidir qué archivo le pide a la sonda y lo usa `sonda.py` para la
conversión de colores. Las pruebas están en `tests/test_qa_capturas.py`.
"""

from __future__ import annotations

import datetime
import re
import unicodedata
from pathlib import Path

# Un título largo recortado sigue reconociéndose, y el nombre entra en
# cualquier sistema de archivos sin pelear con el límite de 255.
LIMITE_TITULO = 40
LIMITE_PESTANA = 30


def plegar(texto: str) -> str:
    """Minúsculas, sin tildes ni espacios ni símbolos, con `_` de relleno."""
    descompuesto = unicodedata.normalize("NFKD", str(texto or ""))
    sin_tildes = "".join(c for c in descompuesto
                         if not unicodedata.combining(c))
    bajo = sin_tildes.casefold()
    plano = re.sub(r"[^a-z0-9]+", "_", bajo).strip("_")
    return re.sub(r"_+", "_", plano)


def clave(escenario: str, titulo: str, extra: str = "") -> tuple:
    """Lo que distingue una captura de otra: escenario, título y variante."""
    return (str(escenario or "").strip().lower(),
            str(titulo or "").strip().lower(),
            str(extra or "").strip().lower())


def nombre_base(n: int, escenario: str, titulo: str, extra: str = "") -> str:
    """`NN_escenario_titulo[_extra].png`, con títulos largos recortados."""
    esc = plegar(escenario) or "escenario"
    tit = plegar(titulo)[:LIMITE_TITULO].strip("_") or "ventana"
    base = f"{n:02d}_{esc}_{tit}"
    if str(extra or "").strip():
        base += "_" + plegar(extra)[:LIMITE_PESTANA].strip("_")
    return base


def nombre_pagina(base: str, pagina: int, pestana: str) -> str:
    """`base_pPP_pestana.png`, con la pestaña recortada."""
    pest = plegar(pestana)[:LIMITE_PESTANA].strip("_") or "pagina"
    return f"{base}_p{pagina:02d}_{pest}"


def bgra_a_rgb(datos: bytes) -> bytes:
    """Pasa bytes BGRA de 32 bits (como los da `GetDIBits`) a RGB de 24.

    Cada grupo de cuatro (azul, verde, rojo, alfa) queda en (rojo, verde,
    azul), que es lo que espera `wx.Image`. Sin el giro, el rojo sale azul.
    """
    crudos = bytes(datos)
    if len(crudos) % 4:
        raise ValueError(f"los bytes BGRA vienen de a 4 y hay {len(crudos)}")
    salida = bytearray(len(crudos) // 4 * 3)
    for i in range(0, len(crudos), 4):
        salida[i // 4 * 3] = crudos[i + 2]
        salida[i // 4 * 3 + 1] = crudos[i + 1]
        salida[i // 4 * 3 + 2] = crudos[i]
    return bytes(salida)


def linea_ok(n: int, archivo: str, escenario: str, titulo: str, pestana: str,
             tamano: tuple, minimo) -> str:
    """Un renglón del índice por cada archivo que sí quedó."""
    pest = pestana or "—"
    if minimo and minimo[0] >= 0 and minimo[1] >= 0:
        texto_minimo = f"{minimo[0]}x{minimo[1]}"
    else:
        texto_minimo = "—"
    return (f"- {n:02d} · {archivo} · {escenario} · {titulo} · {pest} · "
            f"{tamano[0]}x{tamano[1]} · mín {texto_minimo}")


def linea_fallo(n: int, escenario: str, titulo: str, motivo: str) -> str:
    """Un renglón del índice por cada captura que no salió, con su motivo."""
    return (f"- {n:02d} · {escenario} · {titulo} · "
            f"FALLIDA: {motivo or 'sin motivo'}")


NO_CAPTURABLE = (
    "Los menús contextuales y los cuadros nativos de Windows no se capturan: "
    "`PrintWindow` dibuja ventanas wx de nivel superior, y eso no es una. "
    "Cuando un escenario abre algo así, queda anotado acá con su motivo en "
    "vez de forzarse."
)


def carpeta_por_defecto(ahora=None) -> str:
    """`AAAA-MM-DD_HH-MM` con la hora local, para `qa/salida/capturas/`."""
    momento = ahora or datetime.datetime.now()
    return momento.strftime("%Y-%m-%d_%H-%M")


class RegistroCapturas:
    """Qué se capturó y con qué número, para no repetir ni perder nada.

    Una captura es única por escenario, título y variante: el mismo título
    en otro escenario se captura de nuevo, porque el estado puede ser otro.
    """

    def __init__(self, carpeta):
        self.carpeta = Path(carpeta)
        self._siguiente = 1
        self._vistos: set = set()
        self.lineas: list[str] = []

    def reservar(self, escenario: str, titulo: str,
                 extra: str = "") -> tuple | None:
        """Devuelve `(número, base)` o `None` si ya se capturó esta vista."""
        marca = clave(escenario, titulo, extra)
        if marca in self._vistos:
            return None
        self._vistos.add(marca)
        n = self._siguiente
        self._siguiente += 1
        return n, nombre_base(n, escenario, titulo, extra)

    def anotar_ok(self, n: int, archivo: str, escenario: str, titulo: str,
                  pestana: str, tamano: tuple, minimo) -> None:
        self.lineas.append(linea_ok(n, archivo, escenario, titulo, pestana,
                                    tamano, minimo))

    def anotar_fallo(self, n: int, escenario: str, titulo: str,
                     motivo: str) -> None:
        self.lineas.append(linea_fallo(n, escenario, titulo, motivo))

    def indice_texto(self) -> str:
        partes = ["# Capturas del banco de QA", "",
                 "Una línea por archivo: número, escenario, título, pestaña, "
                 "tamaño en píxeles y tamaño mínimo de la ventana.", ""]
        partes += self.lineas if self.lineas else ["(sin capturas)"]
        partes += ["", "## No capturado", "", NO_CAPTURABLE]
        return "\n".join(partes) + "\n"

    def escribir(self) -> Path:
        destino = self.carpeta / "indice.md"
        self.carpeta.mkdir(parents=True, exist_ok=True)
        destino.write_text(self.indice_texto(), encoding="utf-8")
        return destino
