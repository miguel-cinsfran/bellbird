"""Reglas puras para redactar mensajes y comentarios."""

from bellbird.core.idioma import N_, _

MAXIMO_CHAT = 200

# Traductores: motivo de botón desactivado para escribir en el chat.
TEXTO_CHAT_SIN_SESION = N_(
    "Inicia sesión en Preferencias, categoría API y sesión, para "
    "escribir en el chat")
# Traductores: motivo de botón desactivado para escribir en el chat.
TEXTO_CHAT_SIN_CREDENCIALES = N_(
    "Falta la clave de API para saber si este directo permite escribir. "
    "Escríbela en Preferencias, categoría API y sesión.")


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
        return _("Este vídeo no tiene chat")
    if not hay_librerias:
        # Traductores: motivo de botón desactivado para escribir en el chat.
        return _("Faltan las bibliotecas de la API para escribir en el chat")
    if not hay_sesion:
        return _(TEXTO_CHAT_SIN_SESION)
    if not hay_live_chat:
        if causa == "sin_credenciales":
            return _(TEXTO_CHAT_SIN_CREDENCIALES)
        if causa == "sin_video":
            # Traductores: motivo de botón desactivado para escribir en el chat.
            return _("No se encontró este vídeo")
        if causa == "no_es_directo":
            # Traductores: motivo de botón desactivado para escribir en el chat.
            return _("Este vídeo no es un directo")
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
        return _("Este vídeo tiene los comentarios desactivados")
    if not hay_sesion:
        # Traductores: motivo de botón desactivado para comentar.
        return _("Inicia sesión en Preferencias, categoría API y sesión, para "
                 "comentar")
    return ""


def motivo_lectura_comentarios(hay_librerias, hay_api_key, hay_video) -> str:
    if not hay_librerias:
        # Traductores: motivo de botón desactivado para leer comentarios.
        return _("Faltan las bibliotecas de la API. Instálalas con: pip install "
                 "google-api-python-client google-auth-oauthlib")
    if not hay_api_key:
        # Traductores: motivo de botón desactivado para leer comentarios.
        return _("Falta la clave de API para leer comentarios. Escríbela en "
                 "Preferencias, categoría API y sesión.")
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
