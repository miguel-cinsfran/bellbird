"""Leer la sección [musica] de config.ini.

Una sola responsabilidad: las opciones de música validadas contra un único
origen de verdad, sin tener que duplicar la carga de config.ini. `config`
las reexporta para que la carga y las pruebas sigan iguales. Lo que necesita
de `config` (`decodificar_texto_ini`, `normalizar_repetir`) se importa dentro
de la función para no cerrar un import circular.
"""

from __future__ import annotations

from ytchat.core import diagnostico, musica_decir
from ytchat.core import paths
from ytchat.core.ini_tipado import _gs, _pb, _pi


logger = diagnostico.obtener_logger(__name__)


def opciones_musica(p) -> dict:
    """La sección [musica] como claves en memoria, en el mismo orden."""
    from ytchat.core.config import decodificar_texto_ini, normalizar_repetir

    return {
        "musica_carpeta": paths.resolver_carpeta_musica(decodificar_texto_ini(_gs(p, "musica", "carpeta"))),
        "musica_aleatorio": _pb(p, "musica", "aleatorio"),
        "musica_repetir": normalizar_repetir(_gs(p, "musica", "repetir")),
        "musica_retomar": _pb(p, "musica", "retomar"),
        "musica_sonido_tema": _pb(p, "musica", "sonido_tema"),
        "musica_decir": musica_decir.desde_ini(_gs(p, "musica", "decir"), _pb(p, "musica", "decir_titulo"),
            _pb(p, "musica", "incluir_artista")),
        "musica_decir_pausa": _pb(p, "musica", "decir_pausa"),
        "musica_normalizar": _pb(p, "musica", "normalizar"),
        "musica_preguntar_igualar": _pb(p, "musica", "preguntar_igualar"),
        "musica_volumen": _pi(p, "musica", "volumen", lo=0, hi=100), "musica_cruce": _pi(p, "musica", "cruce", lo=0, hi=12),
        "musica_salida": _gs(p, "musica", "salida"),
        "musica_salida_nombre": decodificar_texto_ini(_gs(p, "musica", "salida_nombre")),
        "musica_atajos_globales": _pb(p, "musica", "atajos_globales"),
    } | _filtros_musica(p)


def _filtros_musica(p) -> dict:
    """La visibilidad de la Cola y los filtros de la ventana de música."""
    return {
        "musica_mostrar_cola": _pb(p, "musica", "mostrar_cola"),
        "musica_mostrar_filtros": _pb(p, "musica", "mostrar_filtros"),
        "musica_orden": _gs(p, "musica", "orden"),
        "musica_artista": _gs(p, "musica", "artista"),
    }
