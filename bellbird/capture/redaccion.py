"""Reglas puras para redactar mensajes y comentarios."""

from bellbird.core.idioma import _

MAXIMO_CHAT = 200


def causa_sin_chat(hay_credenciales, consulta_fallo, hay_video,
                    hay_directo, live_chat_id) -> str:
    if not hay_credenciales:
        return "sin_credenciales"
    if consulta_fallo:
        return "fallo_consulta"
    if not hay_video:
        return "sin_video"
    if not hay_directo:
        return "no_es_directo"
    if not live_chat_id:
        return "chat_desactivado"
    return ""


def motivo_chat(conectado, es_tiktok, es_directo, hay_librerias, hay_sesion,
                hay_live_chat, causa="") -> str:
    if not conectado:
        # Traductores: motivo de botón desactivado para escribir en el chat.
        return _("Conéctate a un directo para escribir en el chat")
    if es_tiktok:
        # Traductores: motivo de botón desactivado para escribir en el chat.
        return _("El chat de TikTok no permite escribir desde aquí")
    if not es_directo:
        # Traductores: motivo de botón desactivado para escribir en el chat.
        return _("Este vídeo no tiene chat en vivo")
    if not hay_librerias:
        # Traductores: motivo de botón desactivado para escribir en el chat.
        return _("Faltan las librerías de la API para escribir en el chat")
    if not hay_sesion:
        # Traductores: motivo de botón desactivado para escribir en el chat.
        return _("Inicia sesión en Configuración de API para escribir en el chat")
    if not hay_live_chat:
        if causa == "sin_credenciales":
            # Traductores: motivo de botón desactivado para escribir en el chat.
            return _("Falta la API key para saber si este directo permite escribir. Ponla en Preferencias, pestaña API")
        if causa == "sin_video":
            # Traductores: motivo de botón desactivado para escribir en el chat.
            return _("No se encontró este video")
        if causa == "no_es_directo":
            # Traductores: motivo de botón desactivado para escribir en el chat.
            return _("Este video no es un directo")
        if causa == "chat_desactivado":
            # Traductores: motivo de botón desactivado para escribir en el chat.
            return _("Este directo tiene el chat desactivado")
        # Traductores: motivo de botón desactivado para escribir en el chat.
        return _("No se pudo acceder al chat de este directo")
    return ""


def motivo_comentario(hay_video, hay_sesion, comentarios_cerrados=False) -> str:
    if not hay_video:
        # Traductores: motivo de botón desactivado para comentar.
        return _("Conéctate a un vídeo para poder comentar")
    if comentarios_cerrados:
        # Traductores: motivo de botón desactivado para comentar.
        return _("Este video tiene los comentarios desactivados")
    if not hay_sesion:
        # Traductores: motivo de botón desactivado para comentar.
        return _("Inicia sesión en Configuración de API para comentar")
    return ""


def motivo_lectura_comentarios(hay_librerias, hay_api_key, hay_video) -> str:
    if not hay_librerias:
        # Traductores: motivo de botón desactivado para leer comentarios.
        return _("Faltan las librerías de la API. Instálalas con: pip install "
                 "google-api-python-client google-auth-oauthlib")
    if not hay_api_key:
        # Traductores: motivo de botón desactivado para leer comentarios.
        return _("Falta la API key. Ponla en Preferencias, pestaña API, para leer comentarios.")
    if not hay_video:
        # Traductores: motivo de botón desactivado para leer comentarios.
        return _("Conéctate a un vídeo para poder leer los comentarios")
    return ""


def validar(texto, maximo) -> str:
    texto_limpio = limpiar(texto)
    if not texto_limpio:
        # Traductores: error que se anuncia al validar el texto a enviar.
        return _("Escribe un mensaje antes de enviar")
    if len(texto_limpio) > maximo:
        # Traductores: error que se anuncia al validar el texto a enviar. {largo} es cuántos caracteres tiene y {maximo} el máximo.
        return _("El mensaje tiene {largo} caracteres y el máximo es {maximo}").format(largo=len(texto_limpio), maximo=maximo)
    return ""


def limpiar(texto) -> str:
    return texto.strip()


def etiqueta_con_motivo(base, motivo) -> str:
    if not motivo:
        return base
    return f"{base} ({motivo[0].lower()}{motivo[1:]})"
