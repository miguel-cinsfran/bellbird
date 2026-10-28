"""Nombres de los eventos de sonido de la aplicación, en orden."""

EVENTOS = [
    "app_inicio", "conectando", "conectado", "desconectado",
    "mensaje_nuevo", "mensaje_propietario", "mensaje_moderador",
    "mensaje_verificado", "mensaje_miembro",
    "superchat", "nuevo_miembro", "error",
    "pausa", "reanudar", "copiar", "voz_cambiada",
    # v0.6 online y acciones que antes reutilizaban otros sonidos:
    "enviado", "comentario", "moderacion", "cola_vaciada",
    "transporte_en_curso",
    # Eventos de TikTok y tramos de regalo por tamaño en diamantes:
    "seguir", "compartir", "cofre", "me_gusta",
    "regalo_chico", "regalo_mediano", "regalo_grande", "entrada",
    # Orilla de las listas y fin del directo de TikTok (suena distinto a
    # «desconectado», que sigue para YouTube y el resto de los cortes):
    "orilla", "fin_directo",
    # Avisos del gestor de descargas, cada fin con su resultado:
    "descarga_iniciada", "descarga_completada", "descarga_fallida",
    "descarga_cancelada",
    # Avisos del supervisor de transmisión y descartes del chat:
    "al_aire", "transmision_detenida", "transmision_problema",
    "grabacion_problema", "aviso",
    # Vuelta de la conexión con el servicio: alivio, distinto de la alarma:
    "transmision_recuperada",
    # Confirmación de cierre, distinta del descenso de transmision_detenida:
    "directo_finalizado",
    # Ventanas que se abren solas al arrancar o al terminar bien:
    "actualizacion_disponible", "actualizacion_lista",
    # Música: cambio, fin, fallo e igualación al medir muchas canciones:
    "musica_tema", "musica_fin", "musica_fallo", "musica_igualando",
    # Preguntar a la IA: consulta que sale, espera que suena, respuesta que
    # llega, fallo, captura agregada, consulta cancelada y captura negra:
    "ia_enviada", "ia_respuesta", "ia_error",
    "ia_analizando", "ia_captura", "ia_cancelada", "ia_imagen_negra",
    # Atajos globales que otro programa ya ocupa: tono de ocupado.
    "atajos_ocupados",
    # El micrófono quedó activado y en tres segundos no entró nada.
    "microfono_sin_senal",
    # Pausa del directo de TikTok y su vuelta: cada una con su sonido.
    "directo_pausado", "directo_reanudado",
]

# Nombre llano de cada evento para la página Sonidos de Preferencias.
# Registro de la app: impersonal, sin jerga, lo importante primero,
# hasta unas seis palabras. Un nombre por evento, sin repetir.
NOMBRES = {
    "app_inicio": "Inicio de la aplicación",
    "conectando": "Conexión en curso",
    "conectado": "Conexión establecida",
    "desconectado": "Desconexión del chat",
    "mensaje_nuevo": "Mensaje nuevo del chat",
    "mensaje_propietario": "Mensaje del propietario del canal",
    "mensaje_moderador": "Mensaje del moderador",
    "mensaje_verificado": "Mensaje de una cuenta verificada",
    "mensaje_miembro": "Mensaje de un miembro del canal",
    "superchat": "Super Chat",
    "nuevo_miembro": "Nuevo miembro del canal",
    "error": "Error",
    "pausa": "Lectura en pausa",
    "reanudar": "Lectura reanudada",
    "copiar": "Texto copiado",
    "voz_cambiada": "Voz cambiada",
    "enviado": "Mensaje enviado",
    "comentario": "Comentario publicado",
    "moderacion": "Acción de moderación",
    "cola_vaciada": "Cola de lectura vaciada",
    "transporte_en_curso": "Reproductor ocupado",
    "seguir": "Nuevo seguidor del directo",
    "compartir": "Alguien compartió el directo",
    "cofre": "Cofre de regalos recibido",
    "me_gusta": "Me gusta del directo",
    "regalo_chico": "Regalo chico recibido",
    "regalo_mediano": "Regalo mediano recibido",
    "regalo_grande": "Regalo grande recibido",
    "entrada": "Alguien entró al directo",
    "orilla": "Principio o final de una lista",
    "fin_directo": "Fin del directo",
    "descarga_iniciada": "Descarga iniciada",
    "descarga_completada": "Descarga completada",
    "descarga_fallida": "Descarga fallida",
    "descarga_cancelada": "Descarga cancelada",
    "al_aire": "Directo al aire",
    "transmision_detenida": "Transmisión detenida",
    "transmision_problema": "Problema de la transmisión",
    "grabacion_problema": "Problema de la grabación",
    "aviso": "Aviso general",
    "transmision_recuperada": "Transmisión recuperada",
    "directo_finalizado": "Cierre confirmado del directo",
    "actualizacion_disponible": "Actualización disponible",
    "actualizacion_lista": "Actualización lista para instalar",
    "musica_tema": "Canción cambiada",
    "musica_fin": "Canción terminada",
    "musica_fallo": "Error al reproducir la canción",
    "musica_igualando": "Igualación del volumen",
    "ia_enviada": "Consulta enviada a la IA",
    "ia_respuesta": "Respuesta de la IA",
    "ia_error": "Error de la IA",
    "ia_analizando": "La IA está analizando",
    "ia_captura": "Captura agregada",
    "ia_cancelada": "Consulta a la IA cancelada",
    "ia_imagen_negra": "Captura negra detectada",
    "atajos_ocupados": "Atajos globales ocupados",
    "microfono_sin_senal": "Micrófono sin señal",
    "directo_pausado": "Directo de TikTok en pausa",
    "directo_reanudado": "Directo de TikTok continúa",
}
