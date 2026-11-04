"""Qué ventanas sobran entre dos escenarios del banco de QA.

Recibe la lista que devuelve la orden `ventanas` y el título de la ventana
principal. Devuelve las visibles que no son la principal. No cierra nada.
"""

from __future__ import annotations


def ventanas_sobrantes(ventanas, titulo_principal: str) -> list[dict]:
    """Las ventanas visibles distintas de la principal, en el orden recibido."""
    return [v for v in ventanas
            if v.get("visible")
            and (v.get("titulo") or "") != titulo_principal]
