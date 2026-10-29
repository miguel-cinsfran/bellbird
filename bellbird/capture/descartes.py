"""Decisiones y textos accesibles sobre mensajes descartados."""

from bellbird.core.idioma import _


UMBRAL_AVISO = 3


def hay_que_avisar(descartados: int, ya_avisado: bool,
                    umbral: int = UMBRAL_AVISO) -> bool:
    """Indica si esta sesión debe anunciar los descartes."""
    return descartados >= umbral and not ya_avisado


def frase_aviso(umbral_solo_nombre: int) -> str:
    """Devuelve el aviso que se interrumpe para no ocultar los descartes."""
    if umbral_solo_nombre > 0:
        # Traductores: aviso que se anuncia cuando se descartan mensajes.
        return _("La lectura va con retraso y se están descartando mensajes. "
                 "Puedes buscarlos en la lista del chat.")
    # Traductores: aviso que se anuncia cuando se descartan mensajes.
    return _("La lectura va con retraso y se están descartando mensajes. "
             "Puedes buscarlos en la lista del chat. Activa en Preferencias "
             "la lectura solo del nombre cuando haya muchos mensajes.")


def frase_estado(descartados: int) -> str:
    """Devuelve el componente de estado, vacío si no hubo descartes."""
    if descartados <= 0:
        return ""
    # Traductores: componente del estado F2. {descartados} es cuántos mensajes se descartaron.
    return _("Mensajes descartados: {descartados}").format(descartados=descartados)
