"""Frases del estado y las acciones de transmisión de OBS."""

from bellbird.capture.estado_sesion import _duracion
from bellbird.core.idioma import N_, _

NOTA_TRANSMISION = N_(
    "Desde aquí eliges a dónde transmitir, empiezas y terminas el directo "
    "y preparas lo que se ve. En el directo se ve una ventana, la que "
    "eliges en Ventana que se captura. Esa captura no lleva sonido: el "
    "sonido sale del audio del escritorio y del micrófono de OBS. El panel "
    "de chat es solo para YouTube: en TikTok los comentarios ya aparecen "
    "en el directo.")

_TEXTO_SIN_ESCENA = N_("No se pudo saber que escena está al aire")


def frase_transmision(activa, segundos, perdidos, totales) -> str:
    """Describe el estado de la transmisión sin ruido innecesario."""
    if not activa:
        return _("No estás transmitiendo")
    frase = _("Transmitiendo desde hace {duracion}").format(duracion=_duracion(int(segundos)))
    if perdidos:
        # El total da la medida: 4 fotogramas de 100 es un problema; de
        # 100 000, no.
        de_cuantos = _(" de {t}").format(t=int(totales)) if totales else ""
        frase += _(", {n}{de} fotogramas perdidos").format(n=int(perdidos), de=de_cuantos)
    return frase


def frase_grabacion(activa, en_pausa, codigo_tiempo) -> str:
    """Describe el estado de la grabación con el tiempo útil de OBS."""
    if not activa:
        return _("No estás grabando")
    tiempo = str(codigo_tiempo).split(".", 1)[0]
    return (_("Grabación en pausa, {tiempo}") if en_pausa
            else _("Grabando, {tiempo}")).format(tiempo=tiempo)


def frase_escena_al_aire(escena) -> str:
    """Describe la escena que OBS está mostrando al público."""
    return _("Al aire: {escena}").format(escena=escena) if escena else _(_TEXTO_SIN_ESCENA)


def frase_resultado(accion) -> str:
    """Traduce una acción de OBS a su confirmación audible."""
    return _({
        "transmision_iniciada": N_("Transmisión iniciada"),
        "transmision_detenida": N_("Transmisión detenida"),
        "grabacion_iniciada": N_("Grabación iniciada"),
        "grabacion_detenida": N_("Grabación detenida"),
        "grabacion_en_pausa": N_("Grabación en pausa"),
        "grabacion_reanudada": N_("Grabación reanudada"),
        "escena_cambiada": N_("Escena puesta al aire"),
    }[accion])
