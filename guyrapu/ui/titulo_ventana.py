"""Título de la ventana principal con el estado de OBS."""

from __future__ import annotations

from guyrapu.core.config import APP_NAME, APP_VERSION
from guyrapu.core.idioma import _
from guyrapu.core.version_legible import version_legible


def prefijo_estado(estado_obs) -> str:
    """Estado de OBS que se antepone al título, o vacío si no hay salida."""
    if estado_obs is None:
        return ""
    transmision = bool((estado_obs.transmision or {}).get("outputActive"))
    grabacion = bool((estado_obs.grabacion or {}).get("outputActive"))
    if transmision and grabacion:
        return _("(Transmitiendo y grabando)")
    if transmision:
        return _("(Transmitiendo)")
    if grabacion:
        return _("(Grabando)")
    return ""


def componer(titulo_stream, prefijo) -> str:
    """Arma el título de la ventana con el prefijo de estado delante."""
    titulo = (titulo_stream or "").strip()
    if titulo:
        # Formato tipo navegador: «Nombre del vídeo — Guyrapu».
        # Traductores: {titulo} es el vídeo y {app} la app.
        texto = _("{titulo} — {app}").format(titulo=titulo, app=APP_NAME)
    else:
        # Traductores: título de la ventana: nombre de la app y versión.
        texto = _("{app} {version}").format(
            app=APP_NAME, version=version_legible(APP_VERSION))
    return f"{prefijo} {texto}" if prefijo else texto


def aplicar(frame) -> None:
    """Pone el título que corresponde, solo si cambió."""
    prefijo = ""
    config = getattr(frame, "_config", {}) or {}
    if config.get("titulo_estado_obs", False):
        vigilante = getattr(frame, "_obs_vigilante", None)
        estado = vigilante.estado() if vigilante is not None else None
        prefijo = prefijo_estado(estado)
    texto = componer(getattr(frame, "_titulo_stream", ""), prefijo)
    if frame.GetTitle() != texto:
        frame.SetTitle(texto)
