"""Política de reconexión de TikTok: qué hace el bucle tras cada sesión.

Es puro: no importa wx, asyncio ni TikTokLive. Solo decide si el bucle
sigue reintentando (devuelve None) o termina (devuelve una tupla
`(tipo, texto)`), y arma los textos de reintento. El orden de las
decisiones es el contrato: el mismo del bucle de `capturar_con_reconexion`.
"""

from bellbird.capture.tiktok_errores import (CLASES_OFFLINE, ESPERA_LIMITE,
    es_error_permanente, es_limite, mensaje_error, nombre)
from bellbird.core.idioma import N_, _

# Texto del estado permanente cuando la TikTokLive instalada no trae lo que
# la captura necesita (llega a la GUI por on_estado como los demás estados).
# Traductores: error permanente que se anuncia y se muestra en la barra de estado.
_TEXTO_VERSION_INCOMPATIBLE = N_(
    "La versión instalada de TikTokLive no es compatible con la aplicación.")


def desenlace(err, *, parado, conecto_alguna, offline_pasajero, reconectar):
    """Qué hace el bucle tras una sesión. None para seguir; si termina,
    `(tipo, texto)` con el estado a anunciar, o tipo None para salir
    callado (la parada pedida). `conecto_alguna` dice si conectó alguna
    vez (el reinicio de intentos lo hace el bucle antes de llamar)."""
    if isinstance(err, (ImportError, AttributeError)):
        # Preparación imposible con esta versión de la librería: no vale
        # la pena reintentar, se avisa una vez y se termina.
        return ("error_permanente", _(_TEXTO_VERSION_INCOMPATIBLE))
    if parado:
        return (None, "")
    if err is not None and es_error_permanente(err) and not (
            offline_pasajero and nombre(err) in CLASES_OFFLINE
            and not conecto_alguna):
        return ("error_permanente", mensaje_error(err))
    if err is None:
        # Conexión que terminó sola (fin del directo): no reintentamos.
        # Suena «fin_directo», no «desconectado» (ese sigue para YouTube
        # y el resto de los cortes).
        # Traductores: estado final que se anuncia y se muestra en la barra de estado.
        return ("fin_directo", _("El directo de TikTok ha terminado."))
    if not reconectar:
        return ("error", mensaje_error(err))
    return None


def espera_tras(err, espera) -> int:
    """Espera antes del próximo intento. Con el límite de TikTok se espera
    lo que dura el bloqueo, nunca menos de lo ya configurado."""
    if err is not None and es_limite(err):
        return max(espera, ESPERA_LIMITE)
    return espera


def texto_agotado(maximo):
    """Texto cuando se acaban los intentos de reconexión, ya formateado."""
    # Traductores: error que se anuncia y se muestra en la barra de estado. {intentos} es cuántos intentos se hicieron.
    return _("Se agotaron los {intentos} intentos de reconexión.").format(
        intentos=maximo)


def texto_reintento(segundos, intento, maximo):
    """Texto del estado «reintentando», ya formateado. Con máximo 0 sale la
    frase sin «de {maximo}»."""
    if maximo:
        # Traductores: estado que se anuncia y se muestra en la barra de estado. {segundos} es la espera, {intento} el intento actual y {maximo} el máximo.
        return _("Reintentando en {segundos} segundos (intento {intento} de {maximo})…").format(
            segundos=segundos, intento=intento, maximo=maximo)
    # Traductores: estado que se anuncia y se muestra en la barra de estado. {segundos} es la espera y {intento} el intento actual.
    return _("Reintentando en {segundos} segundos (intento {intento})…").format(
        segundos=segundos, intento=intento)
