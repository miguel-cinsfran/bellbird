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

TEXTO_LIENZO = N_(
    "OBS compone lo que ven los espectadores sobre un\n"
    "rectángulo de tamaño fijo, llamado lienzo. No es la pantalla del equipo\n"
    "ni la ventana del juego.\n\n"
    "Lo que queda dentro del lienzo se emite. Lo que sobresale del borde se\n"
    "recorta, sin ningún aviso.\n\n"
    "Que dos fuentes se superpongan no es necesariamente un problema. El\n"
    "fondo de este panel es transparente: solo se ven las tarjetas de los\n"
    "mensajes, y solo tapan lo que hay justo debajo de ellas.")

TEXTO_COMO_SE_COLOCA = N_(
    "Este cuadro de diálogo no crea escenas ni agrega otras fuentes, salvo la captura de ventana desde la sección Escena. Hace una sola\n"
    "cosa: pone el panel de chat de esta aplicación dentro de una escena de OBS\n"
    "y lo coloca donde quieras.\n\n"
    "El orden es este.\n\n"
    "Uno. Pulsa Preparar panel. Eso enciende el servidor del panel y crea la\n"
    "fuente dentro de la escena elegida, si todavía no estaba.\n\n"
    "Dos. Elige la escena en el desplegable Escena. Recorrerlo no cambia lo que\n"
    "ven los espectadores: para eso está el botón Poner al aire.\n\n"
    "Tres. Elige qué fuente vas a mover en el desplegable Fuente. Normalmente es\n"
    "el panel de chat, pero puedes mover cualquier fuente que ya exista en la\n"
    "escena. Este cuadro de diálogo solo agrega el panel y la captura de ventana: lo demás se hace\n"
    "desde OBS.\n\n"
    "Cuatro. Coloca la fuente. Tienes dos formas. El desplegable Posición más su\n"
    "botón la lleva a una de nueve posiciones fijas. El Ajuste fino la mueve de\n"
    "a poco con las flechas, y confirma con Intro.\n\n"
    "Cinco. El tamaño se cambia con Ancho y Alto y se aplica con su botón.\n\n"
    "El cuadro Estado del panel describe en todo momento dónde está la\n"
    "fuente, de qué tamaño es, si se sale del lienzo y si tapa a otras. Se\n"
    "actualiza solo con cada cambio.\n\n"
    "Restablecer deshace todo lo que hiciste desde que abriste esta ventana.")

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
