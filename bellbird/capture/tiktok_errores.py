"""Clasificación de los errores de TikTokLive.

Cambia solo cuando cambia cómo se clasifican y se cuentan los errores de
TikTokLive; la conexión y la reconexión viven en tiktok_captura.
"""

from bellbird.core.idioma import _


# Excepciones de TikTokLive que no vale la pena reintentar. Se comparan por
# NOMBRE de clase (la librería es opcional, no se importa aquí) y no por
# subcadena del mensaje: un «404 Not Found» del servidor de firmas es un
# httpx.HTTPStatusError transitorio, no un usuario inexistente.
CLASES_OFFLINE = ("UserOfflineError",)
CLASES_NO_EXISTE = ("UserNotFoundError",)


def nombre(exc) -> str:
    return type(exc).__name__


def es_error_http(exc) -> bool:
    n = nombre(exc).lower()
    return "http" in n or n.endswith("statuserror")


def mensaje_error(exc) -> str:
    nombre_exc = nombre(exc)
    t = f"{nombre_exc}: {exc}".lower()
    if nombre_exc in CLASES_OFFLINE:
        # Traductores: error permanente que se anuncia y se muestra en la barra de estado.
        return _("Ese usuario de TikTok no está en directo ahora mismo.")
    if nombre_exc in CLASES_NO_EXISTE:
        # Traductores: error permanente que se anuncia y se muestra en la barra de estado.
        return _("No se encontró ese usuario de TikTok. Revisa la URL.")
    if "sign" in t or "euler" in t or "rate" in t and "limit" in t:
        # Traductores: error transitorio que se anuncia y se muestra en la barra de estado.
        return _("El servidor de firmas de TikTok no responde o alcanzó su "
                 "límite. Espera un momento y reintenta.")
    if "captcha" in t or "blocked" in t:
        # Traductores: error transitorio que se anuncia y se muestra en la barra de estado.
        return _("TikTok pidió verificación (captcha). Reintenta más tarde.")
    if es_error_http(exc):
        # Traductores: error transitorio que se anuncia y se muestra en la barra de estado. {detalle} es el detalle técnico.
        return _("TikTok no respondió bien (error HTTP): {detalle}").format(detalle=exc)
    # Traductores: error transitorio que se anuncia y se muestra en la barra de estado. {detalle} es el detalle técnico.
    return _("No se pudo conectar al directo de TikTok: {detalle}").format(detalle=exc)


def es_error_permanente(exc) -> bool:
    return nombre(exc) in CLASES_OFFLINE + CLASES_NO_EXISTE
