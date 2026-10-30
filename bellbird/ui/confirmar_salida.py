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


def descargas_sin_terminar(items) -> int:
    """Cuántas descargas siguen sin terminar: en cola o descargando.

    Pura: recibe los ítems del gestor y cuenta los que todavía no
    terminaron.
    """
    return sum(1 for item in items
               if getattr(item, "estado", None) in ("en_cola", "descargando"))


def mensaje_con_descargas(mensaje: str | None, sin_terminar: int) -> str | None:
    """Agrega al mensaje de salida cuántas descargas se cancelarán.

    Pura y sin wx: con cero deja el mensaje como está; con más, le suma
    la frase de descargas, o arma la pregunta sola si no había mensaje.
    """
    if not sin_terminar:
        return mensaje
    if sin_terminar == 1:
        descargas = _("Hay 1 descarga sin terminar y se cancelará.")
    else:
        descargas = _("Hay {cantidad} descargas sin terminar y se "
                      "cancelarán.").format(cantidad=sin_terminar)
    if mensaje is None:
        mensaje = _("¿Salir de la aplicación?")
    return _("{mensaje} {descargas}").format(mensaje=mensaje,
                                             descargas=descargas)
