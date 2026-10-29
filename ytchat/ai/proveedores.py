"""Proveedores de IA y resolución de protocolo y base por modelo.

La app programa protocolos, no proveedores. Este módulo dice qué
proveedores ofrece la ventana y cómo se le habla a cada uno.
"""

from __future__ import annotations

from dataclasses import dataclass

from ytchat.ai import catalogo
from ytchat.ai import protocolos
from ytchat.core.config import APP_VERSION
from ytchat.core.idioma import N_


@dataclass(frozen=True)
class Proveedor:
    id: str
    nombre: str
    id_catalogo: str | None
    protocolo_por_defecto: str
    base_por_defecto: str | None
    pide_direccion: bool
    gratis_por_clave: bool = False
    prefijo_clave: str | None = None


PROVEEDORES = (
    Proveedor("gemini", N_("Google Gemini"), "google", protocolos.GEMINI,
              "https://generativelanguage.googleapis.com/v1beta", False,
              gratis_por_clave=True, prefijo_clave="AIza"),
    # Traductores: nombre comercial del proveedor; no se traduce.
    Proveedor("openai", N_("OpenAI"), "openai", protocolos.RESPONSES,
              "https://api.openai.com/v1", False, prefijo_clave="sk-"),
    # Traductores: nombre comercial del proveedor; no se traduce.
    Proveedor("anthropic", N_("Anthropic"), "anthropic", protocolos.ANTHROPIC,
              "https://api.anthropic.com/v1", False, prefijo_clave="sk-ant-"),
    # Traductores: nombre comercial del proveedor; no se traduce.
    Proveedor("openrouter", N_("OpenRouter"), "openrouter", protocolos.CHAT,
              "https://openrouter.ai/api/v1", False, prefijo_clave="sk-or-"),
    Proveedor("opencode-go", N_("OpenCode Go"), "opencode-go", protocolos.CHAT,
              "https://opencode.ai/inference/go/openai/v1", False),
    Proveedor("commandcode", N_("Command Code"), "commandcode", protocolos.CHAT,
              "https://api.commandcode.ai/provider/v1", False),
    Proveedor("otro", N_("Otro compatible con OpenAI"), None, protocolos.CHAT,
              None, True),
)


def por_id(ident):
    """El proveedor con ese id, o None si no existe."""
    for proveedor in PROVEEDORES:
        if proveedor.id == ident:
            return proveedor
    return None


def _limpiar_direccion(direccion):
    return (direccion or "").strip().rstrip("/")


def _exigir_direccion(direccion):
    limpia = _limpiar_direccion(direccion)
    if not limpia or not limpia.startswith(("http://", "https://")):
        raise ValueError("dirección no admitida")
    return limpia


def resolver(proveedor, modelo_id, muestra, direccion=""):
    """Devuelve (protocolo, base) para ese modelo en ese proveedor."""
    if proveedor.id_catalogo is None:
        return (protocolos.CHAT, _exigir_direccion(direccion))
    for modelo in catalogo.modelos(muestra, proveedor.id_catalogo):
        if modelo.id == modelo_id:
            return (modelo.protocolo, modelo.base)
    return (proveedor.protocolo_por_defecto, proveedor.base_por_defecto)


def cabeceras(proveedor, sesion):
    """Cabeceras extra que pide el proveedor, o un dict vacío."""
    if proveedor.id == "opencode-go":
        return {"x-opencode-session": sesion,
                "User-Agent": f"Bellbird/{APP_VERSION}"}
    return {}
