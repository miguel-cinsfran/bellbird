"""Cuándo y cómo existe el chat en el vídeo en OBS.

Su razón para cambiar: la fuente que dibuja el chat dentro de la escena y el
servicio que la sirve cuando OBS la tiene. No habla con wx ni con la
preferencia guardada.
"""

from __future__ import annotations

from guyrapu.obs import overlay_servidor
from guyrapu.obs.fuente_chat import NOMBRE_FUENTE, TIPO_FUENTE

RUTA_PANEL = "/chat"
PUERTO_DEFECTO = 8730
ANCHO = 460
ALTO = 620

ENCENDER = "encender"
APAGAR = "apagar"
NADA = "nada"


def puerto_del_panel(config=None) -> int:
    """El puerto del servicio encendido, el guardado o el de fábrica."""
    config = config or {}
    return (overlay_servidor.puerto_actual()
            or config.get("overlay_puerto", PUERTO_DEFECTO))


def agregar_fuente(gestor, escena, puerto) -> bool:
    """Agrega la fuente del chat a la escena si no está. Devuelve si la agregó."""
    if NOMBRE_FUENTE in gestor.fuentes(escena):
        return False
    url = f"http://127.0.0.1:{puerto}{RUTA_PANEL}"
    gestor.asegurar_fuente(escena, url, ANCHO, ALTO)
    return True


def tiene_fuente(entradas) -> bool:
    """Si la lista de `GetInputList` trae la fuente del chat como navegador."""
    return any(entrada.get("inputName") == NOMBRE_FUENTE
               and entrada.get("inputKind") == TIPO_FUENTE
               for entrada in entradas or ())


def decidir(tiene_la_fuente, servicio_encendido, obs_conectado) -> str:
    """Qué hacer con el servicio: encender, apagar o nada."""
    if not obs_conectado:
        return NADA
    if tiene_la_fuente and not servicio_encendido:
        return ENCENDER
    if not tiene_la_fuente and servicio_encendido:
        return APAGAR
    return NADA
