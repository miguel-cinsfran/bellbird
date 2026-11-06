"""Aviso de privacidad antes de enviar una captura a la IA.

Sale una sola vez: al aceptar se guarda en `config.ini` y no se vuelve a
preguntar. La ventana no agrega controles, solo este diálogo.
"""

from __future__ import annotations

from guyrapu.ai import ajustes_ia
from guyrapu.core import diagnostico
from guyrapu.core import paths
from guyrapu.core.idioma import _, N_
from guyrapu.ui import confirmar as confirmaciones

logger = diagnostico.obtener_logger(__name__)

# Traductores: aviso antes de enviar la captura a la IA; {proveedor} es el nombre del proveedor.
TEXTO_AVISO = N_("La captura de la escena y lo que escribas se envían "
                 "a {proveedor} para que responda. Este aviso aparece una "
                 "sola vez. ¿Enviar?")
# Traductores: título del aviso de privacidad de la IA.
TITULO_AVISO = N_("Privacidad")


def confirmar(padre, ajustes, nombre_proveedor) -> bool:
    """Si se puede enviar al proveedor, preguntando la primera vez."""
    if ajustes.privacidad_aceptada:
        return True
    if not confirmaciones.preguntar(
            padre, _(TEXTO_AVISO).format(proveedor=nombre_proveedor),
            _(TITULO_AVISO), _("&Enviar"), _("&Cancelar"),
            icono=confirmaciones.ICON_INFORMATION, predeterminado_si=False):
        return False
    try:
        guardado = ajustes_ia.guardar_privacidad_aceptada(
            paths.config_ini(), True)
    except Exception as fallo:
        logger.warning("IA: no se pudo guardar la aceptación: %s", fallo)
        return True
    if not guardado:
        logger.warning("IA: no se pudo guardar la aceptación de privacidad")
    return True
