"""Decisiones de qué hacer cuando el vídeo termina o se corta.

Separa el «qué hacer» del «cómo»: estas funciones no tocan wx ni el
reproductor, solo miran el estado y devuelven una constante. El panel
ejecuta después la acción que le devuelven, con sus mismos anuncios y
registros.
"""

NADA = "nada"
DIRECTO_INTERRUMPIDO = "directo_interrumpido"
FIN_FLUJO_VOD = "fin_flujo_vod"
RECARGAR_APERTURA = "recargar_apertura"
TERMINAR_FLUJO = "terminar_flujo"
FIN_VIDEO = "fin_video"
FALLO = "fallo"
ESCLAVO = "esclavo"
CORTE = "corte"
CORTE_SONADO = "corte_sonado"
REABRIR = "reabrir"

MARGEN_FIN_MS = 5000
TOPE_RECUPERACIONES_VOD = 2


def decidir_al_terminar(estado, *, vod_cargando, hay_relevo, relevo_vod,
                        es_flujo, es_directo, fallo_apertura, flujo_sono,
                        relevo_con_reintento) -> str:
    """Elige la acción ante un estado final de VLC.

    Reproduce las dos cadenas del final de _on_timer: con «ended» mira
    primero el VOD por relevo que sigue cargando, después el directo
    con relevo, después el fin de flujo VOD, después el fallo de
    apertura y después el flujo; con «error» mira primero el VOD por
    relevo que sigue cargando, después el flujo que nunca sonó y
    después el fallo de apertura sin reintento pendiente. Las funciones
    se llaman solo en la rama donde hoy se evalúan, en el mismo orden.
    Con otro estado no hay nada que hacer.
    """
    if estado == "ended":
        if vod_cargando:
            return NADA
        if hay_relevo and es_directo():
            return DIRECTO_INTERRUMPIDO
        if hay_relevo and relevo_vod:
            return FIN_FLUJO_VOD
        if fallo_apertura():
            return RECARGAR_APERTURA
        if es_flujo:
            return TERMINAR_FLUJO
        return FIN_VIDEO
    if estado == "error":
        if vod_cargando:
            return NADA
        if es_flujo and not hay_relevo and not flujo_sono():
            return TERMINAR_FLUJO
        if fallo_apertura() and not relevo_con_reintento():
            return RECARGAR_APERTURA
        return FALLO
    return NADA


def ultima_posicion(relevo_ultima, confirmada, pos_ms) -> int:
    """Última posición efectiva conocida del relevo de VOD.

    Vale la última lectura que avanzó; si no hay, la confirmada de la
    búsqueda; si tampoco hay, la posición guardada. Lo no numérico
    vale 0.
    """
    ultima = relevo_ultima
    if ultima is None:
        ultima = confirmada
    if ultima is None:
        ultima = pos_ms
    try:
        return int(ultima)
    except Exception:
        return 0


def _relevo_sono(ultima, base) -> bool:
    try:
        return base is not None and int(ultima) > int(base)
    except Exception:
        return False


def decidir_fin_vod(dur, ultima, recuperaciones, base, hay_fuentes) -> str:
    """Elige la salida del fin de flujo con relevo de VOD grabado.

    Cerca del final (a MARGEN_FIN_MS o menos) es el fin del vídeo de
    siempre. Lejos del final se reabre el relevo desde la última
    posición, hasta TOPE_RECUPERACIONES_VOD veces. Agotado el tope,
    si el relevo sonó se anuncia el corte (haya o no fuentes); si
    nunca sonó se sigue con el esclavo de audio, y sin fuentes se
    anuncia el corte. Sin fuentes para reabrir también se anuncia
    el corte.
    """
    if dur <= 0 or (dur - ultima) <= MARGEN_FIN_MS:
        return FIN_VIDEO
    if recuperaciones >= TOPE_RECUPERACIONES_VOD:
        if _relevo_sono(ultima, base):
            return CORTE_SONADO
        if not hay_fuentes:
            return CORTE
        return ESCLAVO
    if not hay_fuentes:
        return CORTE
    return REABRIR
