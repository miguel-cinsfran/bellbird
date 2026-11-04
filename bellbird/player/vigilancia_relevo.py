"""Cuándo un relevo de directo está roto y hay que reiniciarlo."""

from __future__ import annotations


def aviso_de_corte(pct, pct_anterior) -> str:
    """Devuelve avisos solo al empezar y recuperarse un corte de búfer."""
    if pct < 100 and (pct_anterior is None or pct_anterior >= 100):
        return f"VLC_CORTE empezó porcentaje={pct:.0f}"
    if pct >= 100 and pct_anterior is not None and pct_anterior < 100:
        return "VLC_CORTE recuperado"
    return ""
