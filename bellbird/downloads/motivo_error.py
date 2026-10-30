"""Causa en llano de un fallo de yt-dlp, sin interfaz.

Mira la última línea que empezó con «ERROR:» y dice por qué no se pudo
descargar, con los textos que oye el usuario. Lo desconocido da None para
que quien llama conserve su mensaje de hoy. Función pura.
"""

from __future__ import annotations

from bellbird.core.idioma import _


def motivo_de_error(linea) -> str | None:
    """El motivo en llano de esa línea de error de yt-dlp, o None.

    No distingue mayúsculas. None si la línea es vacía, no es texto o la
    causa no es conocida.
    """
    if not isinstance(linea, str) or not linea.strip():
        return None
    texto = linea.casefold()
    causa = _motivo_youtube(texto)
    if causa is None and "unable to obtain file audio codec" in texto:
        return _("El vídeo no tiene audio.")
    return causa or _motivo_plataforma(texto)


def _motivo_youtube(texto: str) -> str | None:
    """Causas propias de YouTube, en el orden en que se miraban acá."""
    if "confirm your age" in texto or "age-restricted" in texto:
        return (_("El vídeo tiene restricción de edad y YouTube pide "
                  "iniciar sesión."))
    if "private video" in texto:
        return _("El vídeo es privado.")
    if "members-only" in texto or "join this channel" in texto:
        return _("El vídeo es solo para miembros del canal.")
    if "not a bot" in texto:
        return (_("YouTube pide confirmar que no eres un robot. Vuelve a "
                  "intentarlo más tarde."))
    if "video unavailable" in texto or "this video is not available" in texto:
        return _("El vídeo no está disponible.")
    return None


def _motivo_plataforma(texto: str) -> str | None:
    if any(clave in texto for clave in (
            "logged-in", "authentication", "--cookies", "login required")):
        return _("Esta plataforma pide iniciar sesión.")
    if "unsupported url" in texto:
        return _("Este enlace no es compatible con la descarga.")
    return None


def frase_aviso_descarga(estado: str, mensaje: str, nombre: str) -> str:
    """Devuelve el aviso accesible de un fin de descarga."""
    if estado == "completado":
        if mensaje:
            return _("Descarga completada: {nombre}, {mensaje}").format(
                nombre=nombre, mensaje=mensaje)
        return (_("Descarga completada: {nombre}").format(nombre=nombre)
                if nombre else _("Descarga completada"))
    if estado == "parcial":
        return _("Descarga con errores: {nombre}, {mensaje}").format(
            nombre=nombre, mensaje=mensaje)
    if estado == "error":
        return (_("Error en la descarga: {mensaje}").format(mensaje=mensaje) if mensaje else _("Error en la descarga"))
    if estado == "cancelado":
        return _("Descarga cancelada")
    return ""
