"""Decisiones puras del cierre de la aplicación."""

from __future__ import annotations

import logging

NOMBRES_HILOS_CAPTURA = frozenset(("Chat", "TikTok", "LiveChatId"))
# Ocho segundos porque el hilo Chat llegó a tardar más de cuatro en
# terminar (medido el 25/08/2026), y cortarlo antes deja un hilo dentro
# de código nativo, que termina en corrupción de heap 0xc0000374.
TOPE_ESPERA_CIERRE = 8.0


def nivel_registro_cierre(nombres: set[str] | tuple[str, ...]) -> int:
    """Devuelve el nivel adecuado para el resultado del cierre."""
    return logging.WARNING if nombres else logging.INFO


def hilos_captura_vivos(nombres: set[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Devuelve los nombres de captura que siguen vivos, ordenados."""
    return tuple(sorted(set(nombres) & NOMBRES_HILOS_CAPTURA))


def hay_que_seguir_esperando(
    nombres: set[str] | tuple[str, ...], transcurrido: float, tope: float
) -> bool:
    """Indica si quedan hilos vivos y todavía no venció el tope."""
    return bool(nombres) and transcurrido < tope


def componer_resultado_cierre(nombres: set[str] | tuple[str, ...] | list[str], tope: float) -> str:
    """Compone el registro del resultado final de la espera."""
    vivos = tuple(sorted(nombres))
    if not vivos:
        return "CIERRE captura limpia"
    return f"CIERRE por tope={tope:.1f}s hilos vivos={', '.join(vivos)}"
