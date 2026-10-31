"""Leer la sección [transmision] de config.ini.

Una sola responsabilidad: las opciones de transmisión validadas contra un
único origen de verdad, sin tener que duplicar la carga de config.ini.
`config` las reexporta para que la carga y las pruebas sigan iguales. Lo que
necesita de `config` (`decodificar_texto_ini`) se importa dentro de la
función para no cerrar un import circular.
"""

from __future__ import annotations

from bellbird.core.ini_tipado import leer_texto, leer_booleano


def opciones_transmision(p) -> dict:
    """La sección [transmision] como claves en memoria, en el mismo orden."""
    from bellbird.obs import obs_destinos as _destinos
    destino = leer_texto(p, "transmision", "destino")
    if destino not in _destinos.DESTINOS:
        destino = ""

    return {
        "transmision_destino": destino,
        "avisar_sobrecarga": leer_booleano(p, "transmision", "avisar_sobrecarga"),
        "grabar_al_transmitir": leer_booleano(p, "transmision", "grabar_al_transmitir"),
        "avisar_encuadre": leer_booleano(p, "transmision", "avisar_encuadre"),
        "camara_fuente": leer_texto(p, "transmision", "camara_fuente"),
        "camara_invertir": leer_booleano(p, "transmision", "camara_invertir"),
        **_opciones_youtube(p),
    }


def _opciones_youtube(p) -> dict:
    """Las claves de YouTube, con sus valores validados."""
    from bellbird.core.config import decodificar_texto_ini

    from bellbird.youtube import emision as _emision
    privacidad = leer_texto(p, "transmision", "youtube_privacidad")
    if privacidad not in _emision.PRIVACIDADES:
        privacidad = _emision.PRIVACIDAD_INICIAL
    latencia = leer_texto(p, "transmision", "youtube_latencia")
    if latencia not in _emision.LATENCIAS:
        latencia = _emision.LATENCIA_INICIAL
    categoria = leer_texto(p, "transmision", "youtube_categoria")
    if categoria not in {identificador for identificador, _t
                         in _emision.CATEGORIAS}:
        categoria = ""

    return {
        "transmision_youtube_titulo": decodificar_texto_ini(leer_texto(p, "transmision", "youtube_titulo")),
        "transmision_youtube_descripcion": decodificar_texto_ini(leer_texto(p, "transmision", "youtube_descripcion")),
        "transmision_youtube_privacidad": privacidad,
        "transmision_youtube_latencia": latencia,
        "transmision_youtube_ninos": leer_booleano(p, "transmision", "youtube_ninos"),
        "transmision_youtube_dvr": leer_booleano(p, "transmision", "youtube_dvr"),
        "transmision_youtube_categoria": categoria,
        "transmision_youtube_etiquetas": decodificar_texto_ini(leer_texto(p, "transmision", "youtube_etiquetas")),
        "transmision_youtube_miniatura": decodificar_texto_ini(
            leer_texto(p, "transmision", "youtube_miniatura")),
        "transmision_youtube_lista": leer_texto(p, "transmision", "youtube_lista"),
        "transmision_youtube_lista_titulo": decodificar_texto_ini(
            leer_texto(p, "transmision", "youtube_lista_titulo")),
    }
