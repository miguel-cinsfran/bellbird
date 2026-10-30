"""Filas de la lista única de descargas, lógica pura sin wx.

Razón del módulo: qué filas muestra la lista y qué se puede hacer con cada
una. La interfaz en `descargas_listas.py` solo las dibuja.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from bellbird.downloads.argumentos_ytdlp import recortar_url_registro

TODAS = "todas"
EN_CURSO = "en_curso"
EN_ESPERA = "en_espera"
COMPLETADAS = "completadas"
CON_ERRORES = "con_errores"

FILTROS = (TODAS, EN_CURSO, EN_ESPERA, COMPLETADAS, CON_ERRORES)

FINALES = ("completado", "parcial", "cancelado", "error")
ACTIVAS = ("descargando", "en_cola")


def cola_terminada(items) -> bool:
    """Si la cola terminó: hay elementos y ninguno sigue activo."""
    elementos = list(items or [])
    return bool(elementos) and all(
        getattr(i, "estado", "") not in ACTIVAS for i in elementos)

_ID_VIEJO = re.compile(r"^[A-Za-z0-9_-]{11}$")


@dataclass
class Fila:
    """Una fila de la lista única. `item` es el `ItemDescarga`, o None si la
    fila sale del historial."""
    clave: str
    estado: str
    progreso: float
    nombre: str
    fecha: str
    url: str
    ruta: str
    carpeta: str
    mensaje: str
    item: Any | None


def clave_de_entrada(entrada: dict) -> str:
    """Clave de una entrada del historial, con `id` o fecha más nombre."""
    ident = entrada.get("id") or ""
    if ident:
        return str(ident)
    return f"{entrada.get('fecha') or ''}|{entrada.get('nombre') or ''}"





def _fila_de_item(item) -> Fila:
    rutas = getattr(item, "rutas", None) or []
    return Fila(
        clave=item.id,
        estado=item.estado,
        progreso=float(getattr(item, "progreso", 0.0) or 0.0),
        nombre=getattr(item, "nombre", "") or getattr(item, "url", ""),
        fecha="",
        url=getattr(item, "url", "") or "",
        ruta=rutas[0] if rutas else "",
        carpeta=getattr(item, "carpeta", "") or "",
        mensaje=getattr(item, "mensaje", "") or "",
        item=item,
    )


def _fila_de_entrada(entrada: dict, mensaje: str = "") -> Fila:
    estado = str(entrada.get("estado") or "")
    progreso = 100.0 if estado == "completado" else 0.0
    return Fila(
        clave=clave_de_entrada(entrada),
        estado=estado,
        progreso=progreso,
        nombre=str(entrada.get("nombre") or ""),
        fecha=str(entrada.get("fecha") or ""),
        url=str(entrada.get("url") or ""),
        ruta=str(entrada.get("ruta") or ""),
        carpeta=str(entrada.get("carpeta") or ""),
        mensaje=mensaje if mensaje else str(entrada.get("mensaje") or ""),
        item=None,
    )


def construir(items, historial) -> list[Fila]:
    """Junta lo activo y lo terminado en una sola lista.

    Primero lo `descargando`, después lo `en_cola`, los dos en orden de cola,
    y después lo terminado, más reciente primero. Un ítem terminado con una
    entrada de historial de igual `id` aparece una sola vez, la del historial,
    pero con el `mensaje` del ítem.
    """
    items = list(items or [])
    historial = list(historial or [])
    por_id = {getattr(i, "id", ""): i for i in items}
    filas: list[Fila] = []
    for item in items:
        if getattr(item, "estado", "") == "descargando":
            filas.append(_fila_de_item(item))
    for item in items:
        if getattr(item, "estado", "") == "en_cola":
            filas.append(_fila_de_item(item))
    vistas: set[str] = set()
    terminadas: list[Fila] = []
    for entrada in historial:
        ident = entrada.get("id") or ""
        item = por_id.get(ident) if ident else None
        if item is not None and getattr(item, "estado", "") in FINALES:
            clave = clave_de_entrada(entrada)
            if clave in vistas:
                continue
            terminadas.append(_fila_de_entrada(entrada, mensaje=getattr(item, "mensaje", "") or ""))
            vistas.add(ident)
            vistas.add(clave)
        elif item is None:
            clave = clave_de_entrada(entrada)
            if clave in vistas:
                continue
            terminadas.append(_fila_de_entrada(entrada))
            vistas.add(clave)
    for item in items:
        if getattr(item, "estado", "") in FINALES and getattr(item, "id", "") not in vistas:
            terminadas.append(_fila_de_item(item))
    terminadas.sort(key=lambda f: f.fecha or "", reverse=True)
    filas.extend(terminadas)
    return filas


def filtrar(filas: list[Fila], filtro: str) -> list[Fila]:
    """Devuelve solo las filas del filtro pedido."""
    if filtro == EN_CURSO:
        return [f for f in filas if f.estado == "descargando"]
    if filtro == EN_ESPERA:
        return [f for f in filas if f.estado == "en_cola"]
    if filtro == COMPLETADAS:
        return [f for f in filas if f.estado == "completado"]
    if filtro == CON_ERRORES:
        return [f for f in filas if f.estado in ("error", "parcial")]
    return list(filas)


def cantidades(filas: list[Fila]) -> dict:
    """Una cantidad por filtro."""
    return {
        TODAS: len(filas),
        EN_CURSO: sum(1 for f in filas if f.estado == "descargando"),
        EN_ESPERA: sum(1 for f in filas if f.estado == "en_cola"),
        COMPLETADAS: sum(1 for f in filas if f.estado == "completado"),
        CON_ERRORES: sum(1 for f in filas if f.estado in ("error", "parcial")),
    }


def url_utilizable(url) -> str:
    """El enlace si empieza con `http`, o el de YouTube si es un identificador
    viejo de 11 caracteres. Cualquier otra cosa da cadena vacía."""
    texto = (url or "").strip() if isinstance(url, str) else ""
    if texto.startswith("http"):
        return texto
    if _ID_VIEJO.match(texto):
        return f"https://www.youtube.com/watch?v={texto}"
    return ""


def acciones(fila: Fila) -> tuple[str, ...]:
    """Claves de lo que se puede hacer con la fila elegida."""
    if fila.estado in ACTIVAS:
        base = ["cancelar", "copiar"]
    elif fila.estado == "completado":
        base = ["abrir_archivo", "abrir_carpeta", "volver_a_descargar",
                "copiar", "eliminar"]
    elif fila.estado == "parcial":
        base = ["abrir_carpeta", "reintentar", "copiar", "eliminar"]
    else:
        base = ["reintentar", "copiar", "eliminar"]
    if not url_utilizable(fila.url):
        base = [a for a in base if a not in ("reintentar", "volver_a_descargar", "copiar")]
    if not (fila.ruta or "").strip():
        base = [a for a in base if a != "abrir_archivo"]
    if not (fila.ruta or "").strip() and not (fila.carpeta or "").strip():
        base = [a for a in base if a != "abrir_carpeta"]
    return tuple(base)


def pasos_para_sincronizar(actuales: list[str], deseadas: list[str]) -> list:
    """Pasos `("borrar", i)` e `("insertar", i, clave)` para convertir una
    lista de claves en la otra, sin tocar las filas que no cambian de lugar."""
    actuales = list(actuales)
    deseadas = list(deseadas)
    if actuales == deseadas:
        return []
    pasos: list = []
    simulada = list(actuales)
    deseadas_conjunto = set(deseadas)
    for i in range(len(simulada) - 1, -1, -1):
        if simulada[i] not in deseadas_conjunto:
            pasos.append(("borrar", i))
            del simulada[i]
    i = 0
    while i < len(deseadas):
        if i < len(simulada) and simulada[i] == deseadas[i]:
            i += 1
            continue
        if deseadas[i] in simulada:
            j = simulada.index(deseadas[i])
            pasos.append(("borrar", j))
            del simulada[j]
            continue
        pasos.append(("insertar", i, deseadas[i]))
        simulada.insert(i, deseadas[i])
        i += 1
    while len(simulada) > len(deseadas):
        pasos.append(("borrar", len(simulada) - 1))
        del simulada[-1]
    return pasos


def fecha_legible(iso: str) -> str:
    """«30/10/2026 08:33», o el texto tal cual si no se puede leer."""
    texto = iso or ""
    if not isinstance(texto, str) or not texto.strip():
        return texto
    try:
        momento = datetime.fromisoformat(texto.strip())
    except ValueError:
        return texto
    if momento.hour == 0 and momento.minute == 0 and momento.second == 0 \
            and "T" not in texto and " " not in texto.strip():
        return momento.strftime("%d/%m/%Y")
    return momento.strftime("%d/%m/%Y %H:%M")


def ya_descargado(url, historial) -> bool:
    """Si ese enlace ya está en el historial como `completado`.

    Vale la URL igual o el mismo identificador recortado, para que una
    entrada vieja con solo el identificador también cuente. Un
    identificador vacío o «sin identificador» nunca coincide.
    """
    texto = (url or "").strip() if isinstance(url, str) else ""
    if not texto:
        return False
    recorte = recortar_url_registro(texto)
    if recorte in ("", "sin identificador"):
        recorte = ""
    for entrada in historial or []:
        if not isinstance(entrada, dict) or entrada.get("estado") != "completado":
            continue
        otro = str(entrada.get("url") or "")
        if otro and otro == texto:
            return True
        recorte_otro = recortar_url_registro(otro) if otro else ""
        if recorte and recorte_otro not in ("", "sin identificador") \
                and recorte_otro == recorte:
            return True
    return False
