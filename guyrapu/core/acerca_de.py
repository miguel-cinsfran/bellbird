"""Qué dice el cuadro Acerca de.

Función pura, sin wx: arma el texto completo que la ventana muestra con el
mismo `wx.MessageBox` de siempre.
"""

from __future__ import annotations

from guyrapu.core.config import APP_NAME, URL_REPOSITORIO
from guyrapu.core.idioma import _
from guyrapu.core.version_legible import version_legible


def texto(version):
    """El texto de Acerca de para esa versión, en el orden que se lee."""
    return _(
        "{app} {version}\n\n"
        "Lee en voz alta el chat de los directos de YouTube y TikTok. Incluye "
        "moderación, comentarios, reproductor, música, descargas y "
        "control de OBS Studio.\n\n"
        "Autor: Miguel Ángel Insfrán\n\n"
        "Licencia: GPL versión 3, con condiciones adicionales. Los detalles "
        "están en los archivos LICENSE y NOTICE, en la carpeta de la aplicación.\n\n"
        "Repositorio: {url}"
    ).format(app=APP_NAME, version=version_legible(version),
             url=URL_REPOSITORIO)
