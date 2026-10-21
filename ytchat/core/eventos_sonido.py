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
    "al_aire", "transmision_detenida", "transmision_problema", "aviso",
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
]
