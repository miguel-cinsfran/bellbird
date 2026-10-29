"""Catálogo de modelos de IA con visión, reducido desde models.dev.

La página de Preferencias ofrece por proveedor solo los modelos que aceptan
imágenes, devuelven texto y no están deprecados. El catálogo público entero
pesa varios MB, así que `reducir` lo deja en lo que la app usa y `descargar`
guarda esa copia pequeña. La app la renueva sola cada tanto (`vencido`).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx

from bellbird.ai import protocolos

URL = "https://models.dev/api.json"

PROVEEDORES = ("google", "openai", "anthropic", "openrouter",
               "opencode-go", "commandcode")

VERSION = 1

_BASES_POR_DEFECTO = {
    "google": "https://generativelanguage.googleapis.com/v1beta",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
}

_PROTOCOLOS_POR_NPM = {
    "@ai-sdk/google": protocolos.GEMINI,
    "@ai-sdk/openai": protocolos.RESPONSES,
    "@ai-sdk/anthropic": protocolos.ANTHROPIC,
    "@ai-sdk/openai-compatible": protocolos.CHAT,
    "@openrouter/ai-sdk-provider": protocolos.CHAT,
}

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Modelo:
    id: str
    nombre: str
    protocolo: str
    base: str
    gratis: bool
    contributor: bool
    piensa: bool
    tope_salida: int | None


def _protocolo_de(modelo, npm_proveedor):
    # El npm del modelo manda: cada modelo de opencode-go trae el suyo y
    # las llamadas reales lo confirmaron. Sin npm no se adivina.
    npm = npm_proveedor
    proveedor = modelo.get("provider")
    if isinstance(proveedor, dict):
        candidato = proveedor.get("npm")
        if isinstance(candidato, str) and candidato:
            npm = candidato
    if not isinstance(npm, str):
        return None
    return _PROTOCOLOS_POR_NPM.get(npm)


def _base_de(modelo, api_proveedor, proveedor):
    base = None
    proveedor_modelo = modelo.get("provider")
    if isinstance(proveedor_modelo, dict):
        candidata = proveedor_modelo.get("api")
        if isinstance(candidata, str) and candidata:
            base = candidata
    if base is None:
        if isinstance(api_proveedor, str) and api_proveedor:
            base = api_proveedor
        else:
            base = _BASES_POR_DEFECTO.get(proveedor)
    if not isinstance(base, str) or not base:
        return None
    return base.rstrip("/")


def _gratis_de(modelo):
    costo = modelo.get("cost")
    if not isinstance(costo, dict):
        return False
    entrada = costo.get("input")
    salida = costo.get("output")
    if isinstance(entrada, bool) or isinstance(salida, bool):
        return False
    return isinstance(entrada, (int, float)) \
        and isinstance(salida, (int, float)) \
        and entrada == 0 and salida == 0


def _tope_de(modelo):
    limite = modelo.get("limit")
    if not isinstance(limite, dict):
        return None
    tope = limite.get("output")
    if isinstance(tope, bool):
        return None
    if isinstance(tope, int):
        return tope
    if isinstance(tope, float):
        return int(tope)
    return None


def _modalidades_validas(modalidades):
    if not isinstance(modalidades, dict):
        return False
    entradas = modalidades.get("input")
    salidas = modalidades.get("output")
    return isinstance(entradas, (list, tuple)) and "image" in entradas \
        and isinstance(salidas, (list, tuple)) and list(salidas) == ["text"]


def _reducir_modelo(ident, datos, npm_proveedor, api_proveedor, proveedor):
    if not isinstance(datos, dict):
        return None
    if datos.get("status") == "deprecated":
        return None
    if not _modalidades_validas(datos.get("modalities")):
        return None
    protocolo = _protocolo_de(datos, npm_proveedor)
    if protocolo is None:
        return None
    base = _base_de(datos, api_proveedor, proveedor)
    if not base:
        return None
    medio = datos.get("id")
    ident_final = medio if isinstance(medio, str) and medio else ident
    if not isinstance(ident_final, str) or not ident_final \
            or "embedding" in ident_final.lower():
        return None
    nombre = datos.get("name")
    if not isinstance(nombre, str) or not nombre:
        nombre = ident_final
    razona = datos.get("reasoning", False)
    return {
        "id": ident_final,
        "nombre": nombre,
        "protocolo": protocolo,
        "base": base,
        "gratis": _gratis_de(datos),
        "contributor": ident_final.endswith("-contributor"),
        "piensa": razona if isinstance(razona, bool) else False,
        "tope_salida": _tope_de(datos),
    }


def _reducir_proveedor(proveedor, entrada):
    npm = entrada.get("npm")
    if not isinstance(npm, str):
        npm = None
    api = entrada.get("api")
    if not isinstance(api, str):
        api = None
    crudos = entrada.get("models")
    if not isinstance(crudos, dict):
        return []
    reducidos = []
    for ident, datos in crudos.items():
        modelo = _reducir_modelo(ident, datos, npm, api, proveedor)
        if modelo is not None:
            reducidos.append(modelo)
    reducidos.sort(key=lambda m: m["nombre"].lower())
    return reducidos


def reducir(completo, fecha):
    """Deja el catálogo entero en lo que la app usa. Pura."""
    proveedores = {}
    if not isinstance(completo, dict):
        return {"version": VERSION, "fecha": fecha, "proveedores": {}}
    for proveedor in PROVEEDORES:
        entrada = completo.get(proveedor)
        if not isinstance(entrada, dict):
            continue
        nombre = entrada.get("name")
        if not isinstance(nombre, str) or not nombre:
            nombre = proveedor
        proveedores[proveedor] = {
            "nombre": nombre,
            "modelos": _reducir_proveedor(proveedor, entrada),
        }
    return {"version": VERSION, "fecha": fecha, "proveedores": proveedores}


def _leer_catalogo(ruta):
    try:
        texto = Path(ruta).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as error:
        logger.warning("no se pudo leer el catálogo %s: %s", ruta, error)
        return None
    try:
        datos = json.loads(texto)
    except ValueError as error:
        logger.warning("catálogo roto en %s: %s", ruta, error)
        return None
    if not isinstance(datos, dict):
        logger.warning("catálogo roto en %s: no es un objeto", ruta)
        return None
    if datos.get("version") != VERSION:
        logger.warning("catálogo en %s con otra versión: %r",
                       ruta, datos.get("version"))
        return None
    if not isinstance(datos.get("proveedores"), dict):
        logger.warning("catálogo roto en %s: sin proveedores", ruta)
        return None
    return {"version": VERSION, "fecha": datos.get("fecha"),
            "proveedores": datos.get("proveedores")}


def cargar(ruta_datos, ruta_paquete):
    """El primer catálogo válido entre datos y paquete, o uno vacío."""
    for ruta in (ruta_datos, ruta_paquete):
        leido = _leer_catalogo(ruta)
        if leido is not None:
            return leido
    return {"version": VERSION, "fecha": None, "proveedores": {}}


def vencido(catalogo, ahora, dias=7):
    """Verdadero si la fecha falta, no se lee o pasó hace más de `dias`."""
    fecha = catalogo.get("fecha") if isinstance(catalogo, dict) else None
    if not isinstance(fecha, str) or not fecha:
        return True
    try:
        momento = datetime.fromisoformat(fecha)
    except ValueError:
        return True
    try:
        pasan = (ahora - momento).total_seconds()
    except TypeError:
        return True
    return pasan > dias * 86400


def _convertir_modelo(crudo):
    if not isinstance(crudo, dict):
        return None
    for campo in ("id", "nombre", "protocolo", "base"):
        valor = crudo.get(campo)
        if not isinstance(valor, str) or not valor:
            return None
    tope = crudo.get("tope_salida")
    if isinstance(tope, bool):
        tope = None
    elif isinstance(tope, float):
        tope = int(tope)
    elif not isinstance(tope, int) and tope is not None:
        tope = None
    return Modelo(
        id=crudo["id"], nombre=crudo["nombre"],
        protocolo=crudo["protocolo"], base=crudo["base"],
        gratis=bool(crudo.get("gratis")),
        contributor=bool(crudo.get("contributor")),
        piensa=bool(crudo.get("piensa")), tope_salida=tope)


def modelos(catalogo, proveedor, solo_gratis=False):
    """Los modelos guardados de un proveedor, en el orden guardado."""
    proveedores = catalogo.get("proveedores") \
        if isinstance(catalogo, dict) else None
    if not isinstance(proveedores, dict):
        return []
    entrada = proveedores.get(proveedor)
    if not isinstance(entrada, dict):
        return []
    crudos = entrada.get("modelos")
    if not isinstance(crudos, list):
        return []
    salida = []
    for crudo in crudos:
        modelo = _convertir_modelo(crudo)
        if modelo is None:
            continue
        if solo_gratis and not modelo.gratis:
            continue
        salida.append(modelo)
    return salida


def _pedir_catalogo(cliente, tiempo_espera):
    try:
        respuesta = cliente.get(URL, timeout=tiempo_espera)
    except httpx.TimeoutException as error:
        raise protocolos.ErrorIA(
            protocolos.TIEMPO_AGOTADO, str(error)[:300]) from error
    except httpx.TransportError as error:
        raise protocolos.ErrorIA(
            protocolos.SIN_RED, str(error)[:300]) from error
    if respuesta.status_code != 200:
        if respuesta.status_code >= 500:
            tipo = protocolos.SERVIDOR
        else:
            tipo = protocolos.RECHAZO
        raise protocolos.ErrorIA(tipo, respuesta.text[:300])
    try:
        datos = json.loads(respuesta.text)
    except ValueError as error:
        raise protocolos.ErrorIA(
            protocolos.RESPUESTA_VACIA, str(error)[:300]) from error
    if not isinstance(datos, dict):
        raise protocolos.ErrorIA(
            protocolos.RESPUESTA_VACIA, "el catálogo no es un objeto")
    return datos


def descargar(destino, fecha, cliente=None, tiempo_espera=30):
    """Baja el catálogo, lo reduce y lo guarda con escritura atómica."""
    destino = Path(destino)
    if cliente is None:
        with httpx.Client(http2=False) as propio:
            completo = _pedir_catalogo(propio, tiempo_espera)
    else:
        completo = _pedir_catalogo(cliente, tiempo_espera)
    reducido = reducir(completo, fecha)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=str(destino.parent),
                prefix=destino.name + ".", suffix=".tmp",
                delete=False) as f:
            temporal = Path(f.name)
            json.dump(reducido, f, ensure_ascii=False, indent=1)
        os.replace(temporal, destino)
    except Exception:
        if temporal is not None:
            try:
                temporal.unlink()
            except OSError as error:
                logger.warning("no se pudo borrar %s: %s", temporal, error)
        raise
    return reducido
