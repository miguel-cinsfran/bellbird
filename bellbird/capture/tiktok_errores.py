"""Clasificación de los errores de TikTokLive.

Cambia solo cuando cambia cómo se clasifican y se cuentan los errores de
TikTokLive; la conexión y la reconexión viven en tiktok_captura.
"""

from bellbird.core.idioma import N_, _


# Excepciones de TikTokLive que no vale la pena reintentar. Se comparan por
# NOMBRE de clase (la librería es opcional, no se importa aquí) y no por
# subcadena del mensaje: un «404 Not Found» del servidor de firmas es un
# httpx.HTTPStatusError transitorio, no un usuario inexistente.
CLASES_OFFLINE = ("UserOfflineError",)
CLASES_NO_EXISTE = ("UserNotFoundError",)

# Cuánto dura el bloqueo de TikTok ante consultas seguidas, en segundos.
ESPERA_LIMITE = 60

# Traductores: error transitorio que se anuncia y se muestra en la barra de estado.
TEXTO_ERROR_FIRMAS = N_(
    "TikTok no responde por ahora. Espera un momento y vuelve a intentarlo.")


def nombre(exc) -> str:
    return type(exc).__name__


def es_error_http(exc) -> bool:
    n = nombre(exc).lower()
    return "http" in n or n.endswith("statuserror")


def _es_nodo_limite(exc) -> bool:
    """¿Esta excepción sola es el freno de TikTok?"""
    return (nombre(exc) == "JSONDecodeError"
            or _codigo_respuesta(exc) == 403)


def _cadena_limite(exc) -> bool:
    # La cadena de causas de Python: la excepción, su __cause__ y su
    # __context__, sin recursar de más: TikTokLive envuelve el fallo de la
    # sala una sola vez (FailedParseRoomIdError con un JSONDecodeError).
    vistos = set()
    actual = exc
    while actual is not None and id(actual) not in vistos:
        vistos.add(id(actual))
        if _es_nodo_limite(actual):
            return True
        causa = getattr(actual, "__cause__", None)
        contexto = getattr(actual, "__context__", None)
        actual = causa if causa is not None else contexto
    return False


def _codigo_respuesta(exc):
    try:
        return getattr(getattr(exc, "response", None), "status_code", None)
    except Exception:
        return None


def es_limite(exc) -> bool:
    """¿TikTok está frenando las consultas seguidas desde esta conexión?

    Verdadero ante un JSONDecodeError (el 403 con cuerpo vacío que
    TikTokLive no puede decodificar), venga directo o en la causa, o ante
    un error HTTP con respuesta 403.
    """
    try:
        return _cadena_limite(exc)
    except Exception:
        return False


def _mensaje_conocido(exc, nombre_exc, t):
    """Texto propio de un error conocido, o None si es genérico."""
    if nombre_exc in CLASES_OFFLINE:
        # Traductores: error permanente que se anuncia y se muestra en la barra de estado.
        return _("Ese usuario de TikTok no está en directo ahora mismo.")
    if nombre_exc in CLASES_NO_EXISTE:
        # Traductores: error permanente que se anuncia y se muestra en la barra de estado.
        return _("No se encontró ese usuario de TikTok. Revisa el enlace.")
    if "sign" in t or "euler" in t or "rate" in t and "limit" in t:
        return _(TEXTO_ERROR_FIRMAS)
    if "captcha" in t or "blocked" in t:
        # Traductores: error transitorio que se anuncia y se muestra en la barra de estado.
        return _("TikTok pidió verificación (captcha). Vuelve a intentarlo "
                 "más tarde.")
    if es_error_http(exc):
        # Traductores: error transitorio que se anuncia y se muestra en la barra de estado. {detalle} es el detalle técnico.
        return _("TikTok devolvió un error: {detalle}").format(detalle=exc)
    return None


def mensaje_error(exc) -> str:
    if es_limite(exc):
        # Traductores: error transitorio que se anuncia y se muestra en la barra de estado.
        return _("TikTok está limitando las consultas desde esta conexión. "
                 "Espera un minuto y vuelve a intentarlo.")
    nombre_exc = nombre(exc)
    conocido = _mensaje_conocido(
        exc, nombre_exc, f"{nombre_exc}: {exc}".lower())
    if conocido is not None:
        return conocido
    # Traductores: error transitorio que se anuncia y se muestra en la barra de estado. {detalle} es el detalle técnico.
    return _("No se pudo conectar al directo de TikTok: {detalle}").format(detalle=exc)


def es_error_permanente(exc) -> bool:
    return nombre(exc) in CLASES_OFFLINE + CLASES_NO_EXISTE
