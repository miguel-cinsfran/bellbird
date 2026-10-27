"""Lee valores de un ConfigParser con su tipo y, si faltan, el valor de config_predeterminada."""

from __future__ import annotations

from ytchat.core import config_predeterminada


def predeterminado(sec: str, k: str) -> str:
    return config_predeterminada.obtener(sec, k, "")


def leer_texto(p, sec, k):
    return p.get(sec, k, fallback=predeterminado(sec, k)).strip()


def a_entero(v, d):
    try:
        return int(str(v).strip())
    except Exception:
        return d


def a_decimal(v, d):
    try:
        return float(str(v).strip())
    except Exception:
        return d


def leer_entero(p, sec, k, lo=0, hi=None):
    fb = predeterminado(sec, k)
    try:
        d = int(fb.strip()) if fb.strip() else 0
    except Exception:
        d = 0
    v = max(lo, a_entero(leer_texto(p, sec, k), d))
    return min(hi, v) if hi is not None else v


def leer_decimal(p, sec, k, lo=0.0, hi=1.0):
    fb = predeterminado(sec, k)
    try:
        d = float(fb.strip()) if fb.strip() else 1.0
    except Exception:
        d = 1.0
    return max(lo, min(hi, a_decimal(leer_texto(p, sec, k), d)))


def leer_booleano(p, sec, k):
    try:
        return p.getboolean(sec, k)
    except Exception:
        return predeterminado(sec, k).strip().lower() in ("true", "yes", "1", "on")


def separar_por_comas(v: str) -> list:
    return [x.strip().lower() for x in v.split(",") if x.strip()]
