"""Textos y decisiones puras de la ventana Preguntar a la IA.

Sin wx: la ventana solo muestra lo que estas funciones devuelven.
"""

from bellbird.core.idioma import N_, _

FILA_GUIA = N_("Sin mensajes. Agrega una captura y escribe tu pregunta.")
TEXTO_ANALIZANDO = N_("Analizando…")
TEXTO_CANCELADA = N_("Consulta cancelada.")
TEXTO_COPIADA = N_("Respuesta copiada.")
TEXTO_NO_COPIADA = N_("No se pudo copiar la respuesta.")
TEXTO_SIN_RESPUESTA = N_("Todavía no hay ninguna respuesta.")
TEXTO_NUEVA = N_("Conversación nueva.")


def texto_captura_agregada(fuente) -> str:
    # Traductores: anuncio al agregar una imagen; {fuente} es su origen en OBS.
    return _("Captura agregada: {fuente}.").format(fuente=fuente)


def filas_visibles(filas):
    if not filas:
        return [_(FILA_GUIA)]
    return list(filas)


def ultima_respuesta(charla):
    for mensaje in reversed(charla.mensajes):
        if mensaje.rol == "asistente":
            return mensaje.texto
    return None


def hora_de(momento) -> str:
    return momento.strftime("%H:%M")
