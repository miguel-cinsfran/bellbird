"""Modos por aviso de TikTok y por evento: voz, sonido o nada.

Cada aviso de un directo (entradas, me gusta, seguidores, compartidos y
cofres) guarda su modo en `[tiktok]` y cada evento de la app su modo en
`[eventos]`. La app los consulta antes de leer, mostrar o descartar. Puro y
sin wx: `config` lo importa sin ciclo porque los tipos son los mismos textos
que `config.TIPO_*`.
"""

from __future__ import annotations

from bellbird.core.idioma import N_

MODOS = (("leer", N_("Sonido y voz")),
         ("mostrar", N_("Solo sonido")),
         ("ocultar", N_("Desactivado")))

AVISOS = (("entrada", "aviso_entradas", N_("&Entradas al directo:"),
           "mostrar"),
          ("me_gusta", "aviso_me_gusta", N_("&Me gusta:"), "mostrar"),
          ("seguir", "aviso_seguidores", N_("&Seguidores nuevos:"),
           "leer"),
          ("compartir", "aviso_compartidos", N_("Directo compar&tido:"),
           "leer"),
          ("cofre", "aviso_cofres", N_("Co&fres:"), "leer"))

MODOS_EVENTO = (("principal", N_("Voz principal")),
                ("secundaria", N_("Voz secundaria")),
                ("mostrar", N_("Solo sonido")),
                ("ocultar", N_("Desactivado")))

EVENTOS = (("superchat", "principal"),
           ("miembro", "principal"),
           ("entrada", "mostrar"),
           ("me_gusta", "mostrar"),
           ("seguir", "principal"),
           ("compartir", "principal"),
           ("cofre", "principal"))

TIPOS_AVISO = frozenset(tipo for tipo, _clave, _rotulo, _fabrica in AVISOS)

_EVENTO_DE_TIPO = {
    "superchat": "superchat", "sticker": "superchat", "member": "miembro",
    "entrada": "entrada", "me_gusta": "me_gusta", "seguir": "seguir",
    "compartir": "compartir", "cofre": "cofre",
}
_FABRICA = {tipo: fabrica for tipo, _clave, _rotulo, fabrica in AVISOS}
_CLAVE = {tipo: "tiktok_" + clave for tipo, clave, _rotulo, _fabrica in AVISOS}
_CLAVE_EVENTO = {tipo: clave
                 for tipo, clave, _rotulo, _fabrica in AVISOS}
_VALIDOS = frozenset(modo for modo, _rotulo in MODOS)
_FABRICA_EVENTO = dict(EVENTOS)
_VALIDOS_EVENTO = frozenset(modo for modo, _rotulo in MODOS_EVENTO)


def modo_de(config, tipo) -> str | None:
    """Modo guardado del aviso, el de fábrica si falta o es extraño."""
    if tipo not in _FABRICA:
        return None
    valor = config.get(_CLAVE[tipo])
    if isinstance(valor, str) and valor in _VALIDOS:
        return valor
    return _FABRICA[tipo]


def evento_de(tipo) -> str | None:
    """Nombre del evento de un tipo, o None si se lee con la principal."""
    return _EVENTO_DE_TIPO.get(tipo)


def modo_evento(config, tipo) -> str | None:
    """Modo del evento, el de fábrica si falta o es extraño. None: texto."""
    clave = evento_de(tipo)
    if clave is None:
        return None
    valor = config.get("evento_" + clave)
    if isinstance(valor, str) and valor in _VALIDOS_EVENTO:
        return valor
    return _FABRICA_EVENTO[clave]


def opciones_eventos(p) -> dict:
    """La sección [eventos] como claves en memoria, ya validada."""
    opciones = {}
    for clave, fabrica in EVENTOS:
        try:
            valor = (p.get("eventos", clave, fallback=fabrica) or "").strip()
        except Exception:
            valor = fabrica
        valor = valor.lower()
        opciones["evento_" + clave] = (valor if valor in _VALIDOS_EVENTO
                                       else fabrica)
    return opciones


def pasa_filtro(filtro, tipo) -> bool:
    """Si un registro pasa el filtro del chat: None todo, conjunto sus
    tipos, texto el que sea igual."""
    if filtro is None:
        return True
    if isinstance(filtro, frozenset):
        return tipo in filtro
    return filtro == tipo


def migrar(parser, ruta, guardar, guardar_varias=None) -> None:
    """Pasa las claves viejas a las nuevas, una sola vez.

    Escribe en el disco con `guardar` (o `guardar_varias` en un solo lote) y
    también en el parser, para que la lectura de después lo vea. Las claves
    viejas no se borran."""
    cambios = []
    for vieja, nueva in (("anunciar_entradas", "aviso_entradas"),
                         ("leer_me_gusta", "aviso_me_gusta")):
        if parser.has_option("tiktok", nueva):
            continue
        valor = "leer" if _booleano(parser, "tiktok", vieja) else "mostrar"
        _fijar(parser, "tiktok", nueva, valor)
        cambios.append(("tiktok", nueva, valor))
    if not parser.has_section("eventos"):
        cambios.extend(_migrar_eventos(parser))
    _escribir(ruta, cambios, guardar, guardar_varias)


def _migrar_eventos(parser) -> list:
    """Modos de [eventos] que salen de los avisos viejos y de multivoz."""
    secundaria = (_booleano(parser, "voz", "multivoz")
                  and bool(_texto(parser, "voz", "voz_eventos")))
    cambios = []
    for clave, fabrica in EVENTOS:
        nuevo = _modo_nuevo(parser, clave, secundaria)
        if nuevo != fabrica:
            _fijar(parser, "eventos", clave, nuevo)
            cambios.append(("eventos", clave, nuevo))
    if not parser.has_option("voz", "voz_secundaria"):
        voz_eventos = _texto(parser, "voz", "voz_eventos")
        if voz_eventos:
            _fijar(parser, "voz", "voz_secundaria", voz_eventos)
            cambios.append(("voz", "voz_secundaria", voz_eventos))
    return cambios


def _modo_nuevo(parser, clave, secundaria) -> str:
    """Modo de un evento al migrar desde las claves viejas."""
    viejo = _modo_viejo(parser, clave)
    if viejo in ("mostrar", "ocultar"):
        return viejo
    if clave == "me_gusta":
        return "principal"
    return "secundaria" if secundaria else "principal"


def _modo_viejo(parser, clave) -> str:
    """Modo que tenía el aviso antes de [eventos], con su valor de fábrica."""
    nueva = _CLAVE_EVENTO.get(clave)
    if nueva is not None and parser.has_option("tiktok", nueva):
        valor = (parser.get("tiktok", nueva) or "").strip().lower()
        if valor in ("leer", "mostrar", "ocultar"):
            return valor
    return "mostrar" if clave in ("entrada", "me_gusta") else "leer"


def _fijar(parser, seccion, clave, valor) -> None:
    if not parser.has_section(seccion):
        parser.add_section(seccion)
    parser.set(seccion, clave, valor)


def _escribir(ruta, cambios, guardar, guardar_varias) -> None:
    if not cambios:
        return
    if guardar_varias is not None:
        guardar_varias(ruta, cambios)
        return
    for seccion, clave, valor in cambios:
        guardar(ruta, seccion, clave, valor)


def _booleano(parser, seccion, clave) -> bool:
    try:
        return parser.getboolean(seccion, clave)
    except Exception:
        return False


def _texto(parser, seccion, clave) -> str:
    try:
        return (parser.get(seccion, clave) or "").strip()
    except Exception:
        return ""
