"""Textos y decisiones puras de la ventana Preguntar a la IA.

Sin wx: la ventana solo muestra lo que estas funciones devuelven.
"""

FILA_GUIA = "Sin mensajes. Agrega una captura y escribe tu pregunta."
TEXTO_ANALIZANDO = "Analizando…"
TEXTO_CANCELADA = "Consulta cancelada."
TEXTO_COPIADA = "Respuesta copiada."
TEXTO_NO_COPIADA = "No se pudo copiar la respuesta."
TEXTO_SIN_RESPUESTA = "Todavía no hay ninguna respuesta."
TEXTO_NUEVA = "Conversación nueva."


def texto_captura_agregada(fuente) -> str:
    return "Captura agregada: {}.".format(fuente)


def filas_visibles(filas):
    if not filas:
        return [FILA_GUIA]
    return list(filas)


def ultima_respuesta(charla):
    for mensaje in reversed(charla.mensajes):
        if mensaje.rol == "asistente":
            return mensaje.texto
    return None


def hora_de(momento) -> str:
    return momento.strftime("%H:%M")
