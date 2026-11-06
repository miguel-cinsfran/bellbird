"""Peticiones de escenas a OBS, sin interfaz.

`pedir(tipo, datos, parada)` devuelve el `responseData` de la petición, como
`GestorPanelObs._pedir`. `contar_fuentes` e `inventario` leen del gestor, que
es quien ya sabe listar los elementos de una escena.
"""

from __future__ import annotations

from guyrapu.core import diagnostico
from guyrapu.obs import obs_cliente

logger = diagnostico.obtener_logger(__name__)


def crear(pedir, nombre, parada=None) -> None:
    pedir("CreateScene", {"sceneName": nombre}, parada)


def renombrar(pedir, antes, nombre, parada=None) -> None:
    pedir("SetSceneName", {"sceneName": antes, "newSceneName": nombre},
          parada)


def eliminar(pedir, nombre, parada=None) -> None:
    pedir("RemoveScene", {"sceneName": nombre}, parada)


def contar_fuentes(gestor, escena, parada=None) -> int:
    return len(gestor.elementos(escena, parada))


def inventario(gestor, escenas, parada=None) -> tuple:
    """Cada escena con la cantidad de fuentes que tiene, en su orden."""
    return tuple((escena, contar_fuentes(gestor, escena, parada))
                 for escena in escenas)


def duplicar(pedir, origen, destino, parada=None) -> None:
    """Crea la escena de destino y copia ahí las fuentes de la de origen.

    DuplicateSceneItem reutiliza la misma fuente y ya copia su transformación,
    así que una cámara no se abre dos veces. El índice y la visibilidad se
    copian aparte para conservar el orden. Si algo falla después de crear la
    escena, se la quita para no dejar una copia a medias.
    """
    crear(pedir, destino, parada)
    try:
        for elemento in _elementos(pedir, origen, parada):
            _duplicar_elemento(pedir, origen, destino, elemento, parada)
    except Exception:
        _quitar_destino(pedir, destino, parada)
        raise


def _elementos(pedir, escena, parada):
    datos = pedir("GetSceneItemList", {"sceneName": escena}, parada) or {}
    return sorted(datos.get("sceneItems", ()),
                  key=lambda elemento: elemento.get("sceneItemIndex", 0))


def _duplicar_elemento(pedir, origen, destino, elemento, parada):
    respuesta = pedir("DuplicateSceneItem", {
        "sceneName": origen,
        "sceneItemId": elemento["sceneItemId"],
        "destinationSceneName": destino,
    }, parada) or {}
    identificador = respuesta.get("sceneItemId")
    if identificador is None:
        return
    _copiar_presentacion(pedir, destino, identificador, elemento, parada)


def _copiar_presentacion(pedir, destino, identificador, elemento, parada):
    indice = elemento.get("sceneItemIndex")
    if indice is not None:
        pedir("SetSceneItemIndex", {
            "sceneName": destino, "sceneItemId": identificador,
            "sceneItemIndex": indice}, parada)
    pedir("SetSceneItemEnabled", {
        "sceneName": destino, "sceneItemId": identificador,
        "sceneItemEnabled": elemento.get("sceneItemEnabled", True)}, parada)


def _quitar_destino(pedir, destino, parada):
    try:
        eliminar(pedir, destino, parada)
    except obs_cliente.ObsError as error:
        # El fallo de la copia es el que importa: si tampoco se puede quitar
        # la escena a medias, no se tapa el motivo original.
        logger.debug("no se pudo quitar la copia de la escena: %s", error)
