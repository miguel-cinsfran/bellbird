"""Modos por aviso de TikTok: leer en voz alta, mostrar o no mostrar.

Cada aviso de un directo (entradas, me gusta, seguidores, compartidos y
cofres) guarda su modo en `[tiktok]` y la app lo consulta antes de leer,
mostrar o descartar. Puro y sin wx: `config` lo importa sin ciclo porque
los tipos son los mismos textos que `config.TIPO_*`.
"""

from __future__ import annotations

from ytchat.core.idioma import N_

MODOS = (("leer", N_("Leer en voz alta")),
         ("mostrar", N_("Mostrar y sonar")),
         ("ocultar", N_("No mostrar")))

AVISOS = (("entrada", "aviso_entradas", N_("&Entradas al directo:"),
           "mostrar"),
          ("me_gusta", "aviso_me_gusta", N_("&Me gusta:"), "mostrar"),
          ("seguir", "aviso_seguidores", N_("&Seguidores nuevos:"),
           "leer"),
          ("compartir", "aviso_compartidos", N_("Directo compar&tido:"),
           "leer"),
          ("cofre", "aviso_cofres", N_("Co&fres:"), "leer"))

TIPOS_AVISO = frozenset(tipo for tipo, _clave, _rotulo, _fabrica in AVISOS)

_FABRICA = {tipo: fabrica for tipo, _clave, _rotulo, fabrica in AVISOS}
_CLAVE = {tipo: "tiktok_" + clave for tipo, clave, _rotulo, _fabrica in AVISOS}
_VALIDOS = frozenset(modo for modo, _rotulo in MODOS)


def modo_de(config, tipo) -> str | None:
    """Modo guardado del aviso, el de fábrica si falta o es extraño."""
    if tipo not in _FABRICA:
        return None
    valor = config.get(_CLAVE[tipo])
    if isinstance(valor, str) and valor in _VALIDOS:
        return valor
    return _FABRICA[tipo]


def pasa_filtro(filtro, tipo) -> bool:
    """Si un registro pasa el filtro del chat: None todo, conjunto sus
    tipos, texto el que sea igual."""
    if filtro is None:
        return True
    if isinstance(filtro, frozenset):
        return tipo in filtro
    return filtro == tipo


def migrar(parser, ruta, guardar) -> None:
    """Pasa las dos casillas viejas a las claves nuevas, una sola vez.

    Escribe en el disco con `guardar` y también en el parser, para que la
    lectura de después lo vea. Las claves viejas no se borran."""
    for vieja, nueva in (("anunciar_entradas", "aviso_entradas"),
                         ("leer_me_gusta", "aviso_me_gusta")):
        if parser.has_option("tiktok", nueva):
            continue
        try:
            previo = parser.getboolean("tiktok", vieja)
        except Exception:
            previo = False
        valor = "leer" if previo else "mostrar"
        guardar(ruta, "tiktok", nueva, valor)
        if not parser.has_section("tiktok"):
            parser.add_section("tiktok")
        parser.set("tiktok", nueva, valor)
