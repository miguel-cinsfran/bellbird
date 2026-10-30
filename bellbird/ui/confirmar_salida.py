"""Decide qué se le pregunta al usuario antes de salir.

Vive acá para que `gui.py` no crezca: es la única razón por la que este
módulo existe.
"""

from bellbird.core.idioma import _


def mensaje_confirmar_salida(confirmar_salida: bool, chat_conectado: bool,
                             supervisor_activo: bool,
                             obs_transmitiendo: bool) -> str | None:
    """Mensaje para preguntar antes de salir, o None si no hay que preguntar.

    Pura y sin wx: recibe la opción y los tres estados y decide. Lo
    importante va primero, en tono de herramienta.
    """
    if not confirmar_salida:
        return None
    transmision = bool(supervisor_activo or obs_transmitiendo)
    if chat_conectado and transmision:
        return (_("¿Salir de la aplicación? Hay un chat conectado y una transmisión en curso."))
    if chat_conectado:
        return _("¿Salir de la aplicación? Hay un chat conectado.")
    if transmision:
        return _("¿Salir de la aplicación? Hay una transmisión en curso.")
    return None
