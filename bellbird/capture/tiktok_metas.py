"""Lectura de `GoalUpdateEvent` de TikTokLive hacia el registro de metas.

Único módulo que conoce el evento de metas de TikTokLive. Única razón para
cambiar: cómo se lee una meta de la biblioteca. No se usa `goal.status`: la
meta se considera cumplida por el avance de sus submetas.
"""

from __future__ import annotations

from bellbird.capture import metas
from bellbird.core.tipos_mensaje import TIPO_META


def _texto(valor) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def _entero(valor) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def _clave(goal) -> str:
    return (_texto(getattr(goal, "id_str", ""))
            or _texto(getattr(goal, "id", "")))


def _submetas(goal) -> list[tuple[int, int]]:
    return [(_entero(getattr(submeta, "progress", 0)),
             _entero(getattr(submeta, "target", 0)))
            for submeta in (getattr(goal, "sub_goals", None) or [])]


def procesar(evento, on_evento) -> None:
    """Lee una meta y avisa cuando se cumple."""
    goal = getattr(evento, "goal", None)
    if goal is None:
        return
    clave = _clave(goal)
    if not clave:
        return
    descripcion = _texto(getattr(goal, "description", ""))
    if metas.registro.actualizar(clave, descripcion, _submetas(goal)):
        on_evento("", metas.frase_cumplida(descripcion), TIPO_META, "", "")


def reiniciar() -> None:
    """Olvida las metas de la conexión anterior."""
    metas.registro.reiniciar()
