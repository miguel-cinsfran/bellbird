"""Qué se dice al pasar de tema en la música: modos y textos.

Puro: sin wx ni VLC. El cuadro nuevo de Preferencias guarda uno de los
cuatro modos y el cargador deriva el modo de las casillas viejas, para
quien ya las tenía guardadas.
"""

from __future__ import annotations

import os

MODOS = ("nada", "titulo", "titulo_artista", "artista")


def normalizar(valor) -> str:
    """Uno de los cuatro modos; «titulo» para cualquier otra cosa."""
    texto = str(valor or "").strip().lower()
    if texto in MODOS:
        return texto
    return "titulo"


def desde_ini(decir, decir_titulo: bool, incluir_artista: bool) -> str:
    """Modo desde el ini: `decir` manda y si falta se deriva de las viejas.

    Sin texto en `decir`, `decir_titulo` en falso da «nada»; si no,
    `incluir_artista` en verdadero da «titulo_artista»; si no, «titulo».
    """
    if str(decir or "").strip():
        return normalizar(decir)
    if not decir_titulo:
        return "nada"
    if incluir_artista:
        return "titulo_artista"
    return "titulo"


def incluye_artista(modo) -> bool:
    """Si el modo muestra al artista: «titulo_artista» y «artista»."""
    return normalizar(modo) in ("titulo_artista", "artista")


def modo_manual(modo) -> str:
    """Modo para un cambio pedido por el usuario: con «nada» dice el título.

    Con «nada» el cambio automático calla pero el manual dice el título,
    porque el usuario lo pidió; los demás modos valen tal cual.
    """
    if normalizar(modo) == "nada":
        return "titulo"
    return normalizar(modo)


def texto(titulo, artista, modo) -> str:
    """Lo que se dice de un tema según el modo.

    «nada» calla; «titulo» dice el título; «titulo_artista» dice
    «Título, de Artista» o solo el título sin artista; «artista» dice el
    artista o el título si no hay artista.
    """
    modo = normalizar(modo)
    if modo == "nada":
        return ""
    if modo == "titulo":
        return titulo or ""
    if modo == "titulo_artista":
        if artista:
            return f"{titulo}, de {artista}"
        return titulo or ""
    if artista:
        return artista
    return titulo or ""


def titulo_respaldo(origen: str, es_enlace: bool) -> str:
    """Título cuando el tema no trae: el enlace o el archivo sin extensión."""
    if es_enlace:
        return origen
    return os.path.splitext(os.path.basename(origen))[0]


def texto_tema(tema, modo) -> str:
    """Texto de un tema según el modo, con su título de respaldo."""
    return texto(tema.titulo or titulo_respaldo(tema.origen, tema.es_enlace),
                 tema.artista or "", modo)
