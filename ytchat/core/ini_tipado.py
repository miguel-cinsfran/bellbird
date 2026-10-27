"""Lee valores de un ConfigParser con su tipo y, si faltan, el valor de config_predeterminada."""

from __future__ import annotations

from ytchat.core import config_predeterminada


def _fallback(sec: str, k: str) -> str:
    return config_predeterminada.obtener(sec, k, "")


def _gs(p, sec, k):
    return p.get(sec, k, fallback=_fallback(sec, k)).strip()


def _gi(v, d):
    try:
        return int(str(v).strip())
    except Exception:
        return d


def _gf(v, d):
    try:
        return float(str(v).strip())
    except Exception:
        return d


def _pi(p, sec, k, lo=0, hi=None):
    fb = _fallback(sec, k)
    try:
        d = int(fb.strip()) if fb.strip() else 0
    except Exception:
        d = 0
    v = max(lo, _gi(_gs(p, sec, k), d))
    return min(hi, v) if hi is not None else v


def _pf(p, sec, k, lo=0.0, hi=1.0):
    fb = _fallback(sec, k)
    try:
        d = float(fb.strip()) if fb.strip() else 1.0
    except Exception:
        d = 1.0
    return max(lo, min(hi, _gf(_gs(p, sec, k), d)))


def _pb(p, sec, k):
    try:
        return p.getboolean(sec, k)
    except Exception:
        return _fallback(sec, k).strip().lower() in ("true", "yes", "1", "on")


def _lista(v: str) -> list:
    return [x.strip().lower() for x in v.split(",") if x.strip()]
