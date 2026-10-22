"""Proveedores de IA y resolución de protocolo y base por modelo.

La app programa protocolos, no proveedores. Este módulo dice qué
proveedores ofrece la ventana y cómo se le habla a cada uno.
"""

from __future__ import annotations

from dataclasses import dataclass

from ytchat.ai import catalogo
from ytchat.ai import protocolos
from ytchat.core.config import APP_VERSION


@dataclass(frozen=True)
class Proveedor:
    id: str
    nombre: str
    id_catalogo: str | None
    protocolo_por_defecto: str
    base_por_defecto: str | None
    pide_direccion: bool
    gratis_por_clave: bool = False


PROVEEDORES = (
    Proveedor("gemini", "Google Gemini", "google", protocolos.GEMINI,
              "https://generativelanguage.googleapis.com/v1beta", False,
              gratis_por_clave=True),
    Proveedor("openai", "OpenAI", "openai", protocolos.RESPONSES,
              "https://api.openai.com/v1", False),
    Proveedor("anthropic", "Anthropic", "anthropic", protocolos.ANTHROPIC,
              "https://api.anthropic.com/v1", False),
    Proveedor("openrouter", "OpenRouter", "openrouter", protocolos.CHAT,
              "https://openrouter.ai/api/v1", False),
    Proveedor("opencode-go", "OpenCode Go", "opencode-go", protocolos.CHAT,
              "https://opencode.ai/inference/go/openai/v1", False),
    Proveedor("commandcode", "Command Code", "commandcode", protocolos.CHAT,
              "https://api.commandcode.ai/provider/v1", False),
    Proveedor("otro", "Otro compatible con OpenAI", None, protocolos.CHAT,
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
