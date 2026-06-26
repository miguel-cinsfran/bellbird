"""Personas (assistant presets) — wx-free, testable in WSL."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from bellbird.core.paths import user_data_dir

PERSONAS_PATH = user_data_dir() / "personas.json"

_BUILTIN_PERSONAS: list[dict] = [
    {
        "id": "general",
        "nombre": "Asistente general",
        "system_prompt": (
            "Eres un asistente útil, claro y conciso. "
            "Respondés en español, vas al grano y, si algo es ambiguo, "
            "pedís la aclaración mínima."
        ),
        "builtin": True,
        "activa": True,
    },
    {
        "id": "desarrollador",
        "nombre": "Desarrollador / revisor de código",
        "system_prompt": (
            "Eres un desarrollador senior y revisor de código. "
            "Señalás errores, riesgos y mejoras concretas, con el fragmento "
            "corregido y una explicación breve del porqué."
        ),
        "builtin": True,
        "activa": True,
    },
    {
        "id": "traductor",
        "nombre": "Traductor y corrector al inglés",
        "system_prompt": (
            "Eres traductor y corrector. Detectás el idioma de entrada y "
            "respondés con una versión en inglés correcta, natural y mejorada, "
            "sin comentarios extra salvo que se pidan."
        ),
        "builtin": True,
        "activa": True,
    },
    {
        "id": "editor",
        "nombre": "Corrector de estilo / editor",
        "system_prompt": (
            "Eres editor de textos. Corregís ortografía, gramática y estilo "
            "manteniendo la voz del autor; devolvés el texto corregido y, "
            "aparte, una lista breve de los cambios principales."
        ),
        "builtin": True,
        "activa": True,
    },
    {
        "id": "redactor_tecnico",
        "nombre": "Redactor técnico",
        "system_prompt": (
            "Eres redactor técnico. A partir de pasos o notas, escribís una "
            "guía clara y precisa, con encabezados y pasos numerados, sin relleno."
        ),
        "builtin": True,
        "activa": True,
    },
    {
        "id": "profesor",
        "nombre": "Profesor / explicador",
        "system_prompt": (
            "Eres un profesor paciente. Explicás conceptos en términos simples, "
            "con un ejemplo concreto, y subís la complejidad solo si se pide."
        ),
        "builtin": True,
        "activa": True,
    },
    {
        "id": "generador_prompts",
        "nombre": "Generador de prompts",
        "system_prompt": (
            "Eres ingeniero de prompts. Convertís una idea vaga en un prompt "
            "detallado y sin ambigüedades, con rol, objetivo, restricciones y formato."
        ),
        "builtin": True,
        "activa": True,
    },
    {
        "id": "generador_commits",
        "nombre": "Generador de mensajes de commit",
        "system_prompt": (
            "Generás mensajes según Conventional Commits. A partir de un diff "
            "o descripción, devolvés solo el mensaje formateado "
            "(tipo, ámbito opcional, descripción concisa)."
        ),
        "builtin": True,
        "activa": True,
    },
    {
        "id": "entrevistador",
        "nombre": "Entrevistador",
        "system_prompt": (
            "Eres un entrevistador para el puesto indicado. Hacés una pregunta "
            "a la vez y esperás la respuesta antes de la siguiente; "
            "no escribís todo de golpe."
        ),
        "builtin": True,
        "activa": True,
    },
    {
        "id": "describe_imagenes",
        "nombre": "Describe imágenes (accesibilidad)",
        "system_prompt": (
            "Eres un asistente de descripción visual para personas ciegas. "
            "Describís la imagen de forma objetiva y ordenada: primero lo "
            "principal, luego detalles, texto presente y contexto; "
            "sin suposiciones ni juicios."
        ),
        "builtin": True,
        "activa": True,
    },
]


@dataclass
class Persona:
    id: str
    nombre: str
    system_prompt: str
    builtin: bool = False
    activa: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Persona":
        return cls(
            id=d["id"],
            nombre=d["nombre"],
            system_prompt=d["system_prompt"],
            builtin=d.get("builtin", False),
            activa=d.get("activa", True),
        )


def _builtin_defaults() -> list[Persona]:
    return [Persona.from_dict(p) for p in _BUILTIN_PERSONAS]


def load_personas() -> list[Persona]:
    """Load personas from disk, merging built-ins with user overrides."""
    builtin_map = {p.id: p for p in _builtin_defaults()}

    if not PERSONAS_PATH.exists():
        return list(builtin_map.values())

    try:
        data = json.loads(PERSONAS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return list(builtin_map.values())

    result: list[Persona] = []
    seen_ids: set[str] = set()

    for item in data:
        p = Persona.from_dict(item)
        seen_ids.add(p.id)
        result.append(p)

    # Append any built-ins not present in the saved file (new additions).
    for p in builtin_map.values():
        if p.id not in seen_ids:
            result.append(p)

    return result


def save_personas(personas: list[Persona]) -> None:
    PERSONAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PERSONAS_PATH.write_text(
        json.dumps([p.to_dict() for p in personas], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_active_personas(personas: list[Persona]) -> list[Persona]:
    return [p for p in personas if p.activa]


def find_by_id(personas: list[Persona], persona_id: str) -> Optional[Persona]:
    for p in personas:
        if p.id == persona_id:
            return p
    return None


def reset_builtin(personas: list[Persona], persona_id: str) -> list[Persona]:
    """Restore a built-in persona to its original system_prompt."""
    default_map = {p.id: p for p in _builtin_defaults()}
    if persona_id not in default_map:
        return personas
    return [
        default_map[persona_id] if p.id == persona_id else p
        for p in personas
    ]


def apply_persona(config, persona: Optional[Persona]) -> None:
    """Set config.system_prompt (and persona_activa) from a Persona.

    Passing None clears the system prompt (no-persona mode).
    """
    if persona is None:
        config.system_prompt = ""
        config.persona_activa = None
    else:
        config.system_prompt = persona.system_prompt
        config.persona_activa = persona.id
