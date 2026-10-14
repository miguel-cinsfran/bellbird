"""Roles de autor del chat de YouTube y sonido de cada mensaje.

Puro y sin wx: decide qué sonido suena para un mensaje común según el rol
de su autor (pytchat ya lo da en `author`, se leía solo nombre y canal).
Un mensaje suena UNA sola vez: el sonido de rol reemplaza al común.
"""

from ytchat.core.config import TIPO_SUPERCHAT, TIPO_STICKER, TIPO_MIEMBRO

ROL_PROPIETARIO = "propietario"
ROL_MODERADOR = "moderador"
ROL_VERIFICADO = "verificado"
ROL_MIEMBRO = "miembro"

_SONIDO_POR_ROL = {
    ROL_PROPIETARIO: "mensaje_propietario",
    ROL_MODERADOR: "mensaje_moderador",
    ROL_VERIFICADO: "mensaje_verificado",
    ROL_MIEMBRO: "mensaje_miembro",
}


def rol_de_autor(autor) -> str:
    """Un rol por precedencia: propietario, moderador, verificado, miembro.

    Con `autor` None o sin esos atributos, cadena vacía. Nunca lanza.
    """
    try:
        if getattr(autor, "isChatOwner", False):
            return ROL_PROPIETARIO
        if getattr(autor, "isChatModerator", False):
            return ROL_MODERADOR
        if getattr(autor, "isVerified", False):
            return ROL_VERIFICADO
        if getattr(autor, "isChatSponsor", False):
            return ROL_MIEMBRO
    except Exception:
        pass
    return ""


def sonido_de_mensaje(tipo: str, rol: str = "") -> str:
    """Nombre del evento de sonido para un mensaje ya clasificado."""
    if tipo in (TIPO_SUPERCHAT, TIPO_STICKER):
        return "superchat"
    if tipo == TIPO_MIEMBRO:
        return "nuevo_miembro"
    return _SONIDO_POR_ROL.get(rol or "", "mensaje_nuevo")
