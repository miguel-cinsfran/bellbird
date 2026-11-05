"""Nombre e identificación de la fuente del chat dentro de OBS."""

from __future__ import annotations

from guyrapu.core import diagnostico
from guyrapu.core.idioma import N_
from guyrapu.obs import obs_cliente

logger = diagnostico.obtener_logger(__name__)

# Traductores: nombre fijo de la fuente en OBS; no se traduce al usarlo.
NOMBRE_FUENTE = N_("Chat en el vídeo")
NOMBRE_ANTERIOR = "Chat YTChat"
TIPO_FUENTE = "browser_source"


def fuente_encima_del_panel(elementos, fuente=NOMBRE_FUENTE):
    """Nombre de la fuente visible que tapa al panel, o None.

    Mira la lista `sceneItems` de `GetSceneItemList` y devuelve la fuente
    visible de índice más alto por encima del panel. Devuelve None si el
    panel está arriba, si está oculto, si no está en la lista o si solo lo
    tapan fuentes ocultas. Ocultar el panel es decisión de la persona.
    """
    panel = next((elemento for elemento in elementos
                  if elemento.get("sourceName") == fuente), None)
    if panel is None:
        return None
    if not panel.get("sceneItemEnabled", True):
        return None
    indice_panel = panel.get("sceneItemIndex", 0)
    encima = [elemento for elemento in elementos
              if elemento is not panel
              and elemento.get("sceneItemIndex", 0) > indice_panel
              and elemento.get("sceneItemEnabled", True)
              and elemento.get("sourceName")]
    if not encima:
        return None
    return max(encima, key=lambda elemento: elemento.get("sceneItemIndex", 0)).get("sourceName")


def renombrar_anterior(pedir, parada=None):
    """Renombra la fuente vieja del chat a la actual, si corresponde.

    `pedir` devuelve la respuesta sin el sobre de OBS. No toca nada si ya
    existe la fuente nueva o si la vieja no es un navegador. SetInputName
    conserva el lugar, el tamaño y los ajustes en todas las escenas.
    """
    try:
        entradas = pedir("GetInputList", parada=parada).get("inputs", ()) or ()
        nombres = {entrada.get("inputName", "") for entrada in entradas}
        if NOMBRE_FUENTE in nombres or NOMBRE_ANTERIOR not in nombres:
            return
        anterior = next(entrada for entrada in entradas
                        if entrada.get("inputName") == NOMBRE_ANTERIOR)
        if anterior.get("inputKind", "") != TIPO_FUENTE:
            return
        pedir("SetInputName", {"inputName": NOMBRE_ANTERIOR,
                               "newInputName": NOMBRE_FUENTE}, parada=parada)
    except obs_cliente.ObsError as exc:
        logger.warning("No se pudo renombrar la fuente del chat en OBS: %s",
                       exc)
