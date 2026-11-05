"""Tipos de mensaje que circulan por la captura y la interfaz.

Única razón para cambiar: qué tipos de mensaje existen.
"""

from __future__ import annotations

# ── Tipos de mensaje ──────────────────────────────────────────────────────────

TIPO_TEXTO     = "text"
TIPO_SUPERCHAT = "superchat"
TIPO_STICKER   = "sticker"
TIPO_MIEMBRO   = "member"
TIPO_ENTRADA   = "entrada"   # alguien entra al directo (solo TikTok, opcional)
TIPO_SEGUIR    = "seguir"    # alguien sigue el canal (solo TikTok)
TIPO_COMPARTIR = "compartir" # alguien comparte el directo (solo TikTok)
TIPO_COFRE     = "cofre"     # cofre de regalos (solo TikTok)
TIPO_ME_GUSTA  = "me_gusta"  # me gusta del directo (solo TikTok, solo suena)
TIPO_ENCUESTA     = "encuesta"      # se abrió una encuesta (solo TikTok)
TIPO_ENCUESTA_FIN = "encuesta_fin"  # se cerró una encuesta (solo TikTok)
TIPO_META         = "meta"          # se cumplió una meta (solo TikTok)
TIPO_BATALLA      = "batalla"       # empezó una batalla (solo TikTok)
TIPO_BATALLA_FIN  = "batalla_fin"   # terminó una batalla (solo TikTok)

# Variantes que viajan en `monto` cuando el tipo es TIPO_COFRE o TIPO_MIEMBRO.
VARIANTE_SUPERFANS = "superfans"  # caja de superfans (solo TikTok)
VARIANTE_REGALO    = "regalo"     # suscripción regalada (solo TikTok)
