"""Aviso de privacidad antes de enviar una captura a la IA.

Sale una sola vez: al aceptar se guarda en `config.ini` y no se vuelve a
preguntar. La ventana no agrega controles, solo este diálogo.
"""

from __future__ import annotations

import wx

from ytchat.ai import ajustes_ia
from ytchat.core import diagnostico
from ytchat.core import paths

logger = diagnostico.obtener_logger(__name__)

TEXTO_AVISO = ("La captura de la escena y lo que escribas se envían "
               "a {proveedor} para que responda. Este aviso sale una "
               "sola vez. ¿Enviar?")
TITULO_AVISO = "Privacidad"


def confirmar(padre, ajustes, nombre_proveedor) -> bool:
    """Si se puede enviar al proveedor, preguntando la primera vez."""
    if ajustes.privacidad_aceptada:
        return True
    respuesta = wx.MessageBox(
        TEXTO_AVISO.format(proveedor=nombre_proveedor), TITULO_AVISO,
        wx.YES_NO | wx.NO_DEFAULT | wx.ICON_INFORMATION, padre)
    if respuesta != wx.YES:
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
