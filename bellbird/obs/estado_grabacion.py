"""Resumen del estado de la grabación para la ventana Grabación, sin wx.

Su única razón para cambiar es cómo se resume el estado de la grabación.
"""

from __future__ import annotations

from bellbird.core.idioma import _
from bellbird.obs import estado_panel
from bellbird.obs.estado_panel import EstadoPanel
from bellbird.obs.obs_estado import frase_grabacion


def resumir(grabacion, transmision, escena, microfono,
            silenciado) -> EstadoPanel:
    """Resume en un titular, un tono y las líneas que lo acompañan."""
    grabacion = grabacion or {}
    transmision = transmision or {}
    activa = bool(grabacion.get("outputActive", False))
    if activa:
        pausada = bool(grabacion.get("outputPaused", False))
        titular = frase_grabacion(
            True, pausada, grabacion.get("outputTimecode", ""))
        tono = "aviso" if pausada else "activo"
    else:
        titular, tono = _("Sin grabar"), "listo"
    # `_lineas` cierra siempre con el resumen de la grabación, que acá es el
    # titular: se descarta para no repetirlo.
    lineas = list(estado_panel._lineas(
        escena, microfono, silenciado, {})[:-1])
    if bool(transmision.get("outputActive", False)):
        lineas.append(_("También se está transmitiendo."))
    return EstadoPanel(titular=titular, tono=tono, lineas=tuple(lineas))
