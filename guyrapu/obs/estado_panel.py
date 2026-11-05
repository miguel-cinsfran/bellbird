"""Resumen del estado de OBS para el panel de transmisión, sin wx.

Su única razón para cambiar es cómo se resume el estado de OBS en el panel.
"""

from __future__ import annotations

from dataclasses import dataclass

from guyrapu.core.idioma import _
from guyrapu.obs.obs_estado import _duracion


@dataclass(frozen=True, slots=True)
class EstadoPanel:
    titular: str
    tono: str
    lineas: tuple


def _titular(destino, transmision, problemas) -> tuple:
    if bool(transmision.get("outputActive", False)):
        duracion = _duracion(int(transmision.get("outputDuration", 0) or 0))
        if not destino:
            return _("Transmitiendo desde hace {duracion}").format(
                duracion=duracion), "activo"
        return (_("Transmitiendo a {destino} desde hace {duracion}").format(
            destino=destino, duracion=duracion), "activo")
    if not destino:
        return _("Elige a dónde transmitir"), "listo"
    if problemas:
        return (_("Revisa antes de transmitir: {primer_problema}").format(
            primer_problema=problemas[0]), "aviso")
    return _("Preparado para transmitir a {destino}").format(destino=destino), "listo"


def _lineas(escena, microfono, silenciado, grabacion) -> tuple:
    lineas = []
    if escena:
        lineas.append(_("Escena actual: {escena}").format(escena=escena))
    if microfono:
        estado = _("silenciado") if silenciado else _("activado")
        lineas.append(_("Micrófono {nombre}: {estado}").format(
            nombre=microfono, estado=estado))
    if bool(grabacion.get("outputActive", False)):
        tiempo = str(grabacion.get("outputTimecode", "")).split(".", 1)[0]
        if bool(grabacion.get("outputPaused", False)):
            lineas.append(_("Grabación: en pausa, {tiempo}").format(tiempo=tiempo))
        else:
            lineas.append(_("Grabación: en curso, {tiempo}").format(tiempo=tiempo))
    else:
        lineas.append(_("Grabación: detenida"))
    return tuple(lineas)


def resumir(destino, transmision, grabacion, escena, microfono, silenciado,
            problemas) -> EstadoPanel:
    """Resume en un titular, un tono y las líneas que lo acompañan."""
    transmision = transmision or {}
    grabacion = grabacion or {}
    problemas = tuple(problemas or ())
    titular, tono = _titular(destino, transmision, problemas)
    return EstadoPanel(
        titular=titular, tono=tono,
        lineas=_lineas(escena, microfono, silenciado, grabacion))
