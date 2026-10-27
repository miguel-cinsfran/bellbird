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
from ytchat.core.ini_tipado import leer_texto, leer_booleano, leer_entero


logger = diagnostico.obtener_logger(__name__)


def opciones_musica(p) -> dict:
    """La sección [musica] como claves en memoria, en el mismo orden."""
    from ytchat.core.config import decodificar_texto_ini, normalizar_repetir

    return {
        "musica_carpeta": paths.resolver_carpeta_musica(decodificar_texto_ini(leer_texto(p, "musica", "carpeta"))),
        "musica_aleatorio": leer_booleano(p, "musica", "aleatorio"),
        "musica_repetir": normalizar_repetir(leer_texto(p, "musica", "repetir")),
        "musica_retomar": leer_booleano(p, "musica", "retomar"),
        "musica_sonido_tema": leer_booleano(p, "musica", "sonido_tema"),
        "musica_decir": musica_decir.desde_ini(leer_texto(p, "musica", "decir"), leer_booleano(p, "musica", "decir_titulo"),
            leer_booleano(p, "musica", "incluir_artista")),
        "musica_decir_pausa": leer_booleano(p, "musica", "decir_pausa"),
        "musica_normalizar": leer_booleano(p, "musica", "normalizar"),
        "musica_preguntar_igualar": leer_booleano(p, "musica", "preguntar_igualar"),
        "musica_volumen": leer_entero(p, "musica", "volumen", lo=0, hi=100), "musica_cruce": leer_entero(p, "musica", "cruce", lo=0, hi=12),
        "musica_salida": leer_texto(p, "musica", "salida"),
        "musica_salida_nombre": decodificar_texto_ini(leer_texto(p, "musica", "salida_nombre")),
        "musica_atajos_globales": leer_booleano(p, "musica", "atajos_globales"),
    } | _filtros_musica(p)


def _filtros_musica(p) -> dict:
    """La visibilidad de la Cola y los filtros de la ventana de música."""
    return {
        "musica_mostrar_cola": leer_booleano(p, "musica", "mostrar_cola"),
        "musica_mostrar_filtros": leer_booleano(p, "musica", "mostrar_filtros"),
        "musica_orden": leer_texto(p, "musica", "orden"),
        "musica_artista": leer_texto(p, "musica", "artista"),
    }
