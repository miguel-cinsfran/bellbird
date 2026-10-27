"""Ajustes de IA en config.ini, sección [ia].

La ventana y el atajo solo leen y guardan por acá. No toca
`cargar_configuracion`: esa función ya mide 180 líneas y el
trinquete no la deja crecer.
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

from ytchat.core import config
from ytchat.core import ini_tipado
from ytchat.ai import conversacion
from ytchat.ai import proveedores

SECCION = "ia"

LARGOS = (
    conversacion.CORTA,
    conversacion.MEDIA,
    conversacion.LARGA,
)

TIEMPO_MINIMO = 10
TIEMPO_MAXIMO = 300


@dataclass
class AjustesIA:
    proveedor: str = "gemini"
    modelo: str = ""
    direccion: str = ""
    pregunta: str = ""
    largo: str = "media"
    tiempo_espera: int = 60
    solo_gratis: bool = False
    privacidad_aceptada: bool = False
    decir_analizando: bool = True


def _ids_proveedores() -> set:
    return {p.id for p in proveedores.PROVEEDORES}


def _leer_crudo(ruta) -> configparser.ConfigParser:
    fabrica = AjustesIA()
    texto_fabrica = (
        "[ia]\nproveedor = {}\nmodelo = \ndireccion = \npregunta = \n"
        "largo = {}\ntiempo_espera = {}\n".format(
            fabrica.proveedor, fabrica.largo, fabrica.tiempo_espera)
    )
    parser = config._mk_parser()
    try:
        parser.read_string(texto_fabrica)
        parser.read(ruta, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeError):
        parser = config._mk_parser()
        parser.read_string(texto_fabrica)
    return parser


def _proveedor_valido(valor: str) -> str:
    limpio = (valor or "").strip()
    if limpio in _ids_proveedores():
        return limpio
    return "gemini"


def _largo_valido(valor: str) -> str:
    limpio = (valor or "").strip().lower()
    if limpio in LARGOS:
        return limpio
    return conversacion.MEDIA


def _tiempo_valido(valor: str) -> int:
    try:
        numero = int(str(valor).strip())
    except (TypeError, ValueError):
        return 60
    return max(TIEMPO_MINIMO, min(TIEMPO_MAXIMO, numero))


def leer(ruta) -> AjustesIA:
    """Lee la sección [ia]. Sin archivo, rota o sin sección da la fábrica."""
    parser = _leer_crudo(ruta)
    texto_pregunta = parser.get(SECCION, "pregunta", fallback="")
    return AjustesIA(
        proveedor=_proveedor_valido(
            parser.get(SECCION, "proveedor", fallback="gemini")),
        modelo=parser.get(SECCION, "modelo", fallback="").strip(),
        direccion=parser.get(SECCION, "direccion", fallback="").strip(),
        pregunta=config.decodificar_texto_ini(texto_pregunta),
        largo=_largo_valido(parser.get(SECCION, "largo", fallback="media")),
        tiempo_espera=_tiempo_valido(
            parser.get(SECCION, "tiempo_espera", fallback="60")),
        solo_gratis=ini_tipado.leer_booleano(parser, SECCION, "solo_gratis"),
        privacidad_aceptada=ini_tipado.leer_booleano(parser, SECCION, "privacidad_aceptada"),
        decir_analizando=ini_tipado.leer_booleano(parser, SECCION, "decir_analizando"),
    )


def _bool_a_texto(valor: bool) -> str:
    return "true" if valor else "false"


def cambios(ajustes: AjustesIA) -> list:
    """Los nueve valores de la sección [ia] ya convertidos a texto."""
    return [
        (SECCION, "proveedor", ajustes.proveedor),
        (SECCION, "modelo", ajustes.modelo),
        (SECCION, "direccion", ajustes.direccion),
        (SECCION, "pregunta",
         config.codificar_texto_ini(ajustes.pregunta)),
        (SECCION, "largo", ajustes.largo),
        (SECCION, "tiempo_espera", str(ajustes.tiempo_espera)),
        (SECCION, "solo_gratis", _bool_a_texto(ajustes.solo_gratis)),
        (SECCION, "privacidad_aceptada", _bool_a_texto(ajustes.privacidad_aceptada)),
        (SECCION, "decir_analizando",
         _bool_a_texto(ajustes.decir_analizando)),
    ]


def guardar(ruta, ajustes: AjustesIA):
    """Guarda los nueve valores de una vez, conservando el resto."""
    return config.guardar_opciones(Path(ruta) if ruta is not None else None,
                                   cambios(ajustes))


def guardar_decir_analizando(ruta, valor: bool):
    """Guarda solo la voz del «Analizando…», conservando el resto."""
    return config.guardar_opcion(Path(ruta) if ruta is not None else None,
                                 SECCION, "decir_analizando",
                                 _bool_a_texto(valor))


def guardar_privacidad_aceptada(ruta, valor: bool):
    """Guarda solo la aceptación del aviso de privacidad, conservando el resto."""
    return config.guardar_opcion(Path(ruta) if ruta is not None else None,
                                 SECCION, "privacidad_aceptada",
                                 _bool_a_texto(valor))


def pregunta_efectiva(ajustes: AjustesIA) -> str:
    """La pregunta sin bordes, o la de fábrica si queda vacía."""
    limpia = (ajustes.pregunta or "").strip()
    if limpia:
        return limpia
    return conversacion.PREGUNTA_INICIAL
