"""Frases del estado y las acciones de transmisión de OBS."""

from ytchat.capture.estado_sesion import _duracion

NOTA_TRANSMISION = (
    "Desde aquí eliges a dónde transmitir, empiezas y terminas el directo "
    "y preparas lo que se ve. En el directo se ve una ventana, la que "
    "eliges en Ventana que se captura. Esa captura no lleva sonido: el "
    "sonido sale del audio del escritorio y del micrófono de OBS. El panel "
    "de chat es solo para YouTube: en TikTok los comentarios ya aparecen "
    "en el directo.")


def frase_transmision(activa, segundos, perdidos, totales) -> str:
    """Describe el estado de la transmisión sin ruido innecesario."""
    if not activa:
        return "No estás transmitiendo"
    frase = f"Transmitiendo desde hace {_duracion(int(segundos))}"
    if perdidos:
        # El total da la medida: 4 fotogramas de 100 es un problema; de
        # 100 000, no.
        de_cuantos = f" de {int(totales)}" if totales else ""
        frase += f", {int(perdidos)}{de_cuantos} fotogramas perdidos"
    return frase


def frase_grabacion(activa, en_pausa, codigo_tiempo) -> str:
    """Describe el estado de la grabación con el tiempo útil de OBS."""
    if not activa:
        return "No estás grabando"
    tiempo = str(codigo_tiempo).split(".", 1)[0]
    return (f"Grabación en pausa, {tiempo}" if en_pausa
            else f"Grabando, {tiempo}")


def frase_escena_al_aire(escena) -> str:
    """Describe la escena que OBS está mostrando al público."""
    return f"Al aire: {escena}" if escena else "No se pudo saber que escena está al aire"


def frase_resultado(accion) -> str:
    """Traduce una acción de OBS a su confirmación audible."""
    return {
        "transmision_iniciada": "Transmisión iniciada",
        "transmision_detenida": "Transmisión detenida",
        "grabacion_iniciada": "Grabación iniciada",
        "grabacion_detenida": "Grabación detenida",
        "grabacion_en_pausa": "Grabación en pausa",
        "grabacion_reanudada": "Grabación reanudada",
        "escena_cambiada": "Escena puesta al aire",
    }[accion]
