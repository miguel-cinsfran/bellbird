"""Roles de autor del chat de YouTube y sonido de cada mensaje.

Puro y sin wx: decide qué sonido suena para un mensaje común según el rol
de su autor (pytchat ya lo da en `author`, se leía solo nombre y canal).
Un mensaje suena UNA sola vez: el sonido de rol reemplaza al común.

Los regalos de TikTok llegan como superchat con el monto en diamantes
(«250 diamantes») y suenan según el tramo; el resto de eventos de TikTok
suena con el evento del mismo nombre.
"""

import re

from ytchat.core.config import (
    TIPO_SUPERCHAT, TIPO_STICKER, TIPO_MIEMBRO, TIPO_ENTRADA,
    TIPO_SEGUIR, TIPO_COMPARTIR, TIPO_COFRE, TIPO_ME_GUSTA,
)

ROL_PROPIETARIO = "propietario"
ROL_MODERADOR = "moderador"
ROL_VERIFICADO = "verificado"
ROL_MIEMBRO = "miembro"

# Códigos de flecha de wx (wx.WXK_UP / wx.WXK_DOWN) con nombre, para no
# importar wx en este módulo puro.
TECLA_FLECHA_ARRIBA = 315
TECLA_FLECHA_ABAJO = 317


def es_orilla(tecla, seleccion, total) -> bool:
    """¿La flecha intenta salir de la lista por un borde?

    Verdadero si es flecha arriba con la selección en la primera fila, o
    flecha abajo con la selección en la última, o cualquiera de las dos
    con la lista vacía. Con nada elegido (-1) y lista no vacía, falso.
    Nunca lanza: lo no numérico también es falso.
    """
    if tecla not in (TECLA_FLECHA_ARRIBA, TECLA_FLECHA_ABAJO):
        return False
    try:
        total = int(total)
    except (TypeError, ValueError):
        return False
    if total <= 0:
        return True
    try:
        seleccion = int(seleccion)
    except (TypeError, ValueError):
        return False
    if tecla == TECLA_FLECHA_ARRIBA:
        return seleccion == 0
    return seleccion == total - 1

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


def sonido_de_mensaje(tipo: str, rol: str = "", monto: str = "",
                      plataforma: str = "") -> str:
    """Nombre del evento de sonido para un mensaje ya clasificado.

    `monto` y `plataforma` solo importan para el regalo de TikTok: llega
    como superchat con «N diamantes» y suena según su tramo; el Super Chat
    y el sticker de YouTube siguen siendo «superchat».
    """
    if tipo == TIPO_SUPERCHAT or tipo == TIPO_STICKER:
        if (plataforma or "").lower() == "tiktok" and tipo == TIPO_SUPERCHAT:
            return tramo_regalo(_diamantes_de_monto(monto))
        return "superchat"
    if tipo == TIPO_MIEMBRO:
        return "nuevo_miembro"
    if tipo == TIPO_SEGUIR:
        return "seguir"
    if tipo == TIPO_COMPARTIR:
        return "compartir"
    if tipo == TIPO_COFRE:
        return "cofre"
    if tipo == TIPO_ME_GUSTA:
        return "me_gusta"
    if tipo == TIPO_ENTRADA:
        return "entrada"
    return _SONIDO_POR_ROL.get(rol or "", "mensaje_nuevo")


def tramo_regalo(diamantes: int) -> str:
    """Tramo de sonido de un regalo de TikTok según sus diamantes."""
    try:
        total = int(diamantes)
    except (TypeError, ValueError):
        return "regalo_chico"
    if total >= 1000:
        return "regalo_grande"
    if total >= 100:
        return "regalo_mediano"
    return "regalo_chico"


def _diamantes_de_monto(monto: str) -> int:
    """Número de diamantes del texto del monto («250 diamantes»); 0 si no hay."""
    m = re.search(r"(\d+)", monto or "")
    if not m:
        return 0
    try:
        return int(m.group(1))
    except (TypeError, ValueError):
        return 0
