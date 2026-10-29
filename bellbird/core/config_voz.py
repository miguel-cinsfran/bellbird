"""Leer la sección [voz] de config.ini.

Una sola responsabilidad: las opciones de voz validadas contra un único
origen de verdad, sin tener que duplicar la carga de config.ini. `config`
las reexporta para que la carga y las pruebas sigan iguales. Lo que necesita
de `config` (`guardar_opcion`, `a_entero`) se importa dentro de la función
para no cerrar un import circular.
"""

from __future__ import annotations

from bellbird.core.ini_tipado import leer_texto, leer_decimal, leer_entero, leer_booleano


def opciones_voz(p, ruta) -> dict:
    """La sección [voz] como claves en memoria, en el mismo orden."""
    from bellbird.core.config import guardar_opcion, a_entero

    # [voz]: el motor se valida contra los válidos de Prism (importarlos aquí
    # no arrastra Prism: motores lo importa de forma perezosa). La velocidad se
    # guarda como porcentaje propio (0..100); la clave vieja en palabras por
    # minuto se convierte una sola vez y se fija en el archivo, así el arranque
    # siguiente no vuelve al valor de fábrica.
    from bellbird.voice import escala_voz as _escala
    from bellbird.voice import motores as _motores
    motor = leer_texto(p, "voz", "motor").lower()
    if motor not in _motores.MOTORES:
        motor = "sapi"
    if p.has_option("voz", "velocidad_voz"):
        velocidad_voz = max(0, min(100, a_entero(
            leer_texto(p, "voz", "velocidad_voz"), _escala.VELOCIDAD_NORMAL)))
    elif p.has_option("voz", "velocidad"):
        velocidad_voz = _escala.velocidad_desde_wpm(
            a_entero(leer_texto(p, "voz", "velocidad"), 175))
        guardar_opcion(ruta, "voz", "velocidad_voz", str(velocidad_voz))
    else:
        velocidad_voz = _escala.VELOCIDAD_NORMAL

    return {
        "motor": motor,
        "voz": leer_texto(p, "voz", "voz"),
        "velocidad_voz": velocidad_voz,
        "volumen": leer_decimal(p, "voz", "volumen"),
        "tono": leer_entero(p, "voz", "tono", lo=0, hi=100),
        "multivoz": leer_booleano(p, "voz", "multivoz"),
        "voz_eventos": leer_texto(p, "voz", "voz_eventos"),
        "voz_respaldo": leer_texto(p, "voz", "voz_respaldo"),
        "elevenlabs_tope": leer_entero(p, "voz", "elevenlabs_tope", lo=0),
        "elevenlabs_solo_importantes": leer_booleano(p, "voz", "elevenlabs_solo_importantes"),
    }
