"""Peticiones de escenas a OBS, sin interfaz.

`pedir(tipo, datos, parada)` devuelve el `responseData` de la petición, como
`GestorPanelObs._pedir`. `contar_fuentes` e `inventario` leen del gestor, que
es quien ya sabe listar los elementos de una escena.
"""

from __future__ import annotations


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

    DuplicateSceneItem reutiliza la misma fuente, así que una cámara no se
    abre dos veces. El índice, la transformación y la visibilidad se copian
    aparte para conservar el orden y la presentación.
    """
    crear(pedir, destino, parada)
    for elemento in _elementos(pedir, origen, parada):
        _duplicar_elemento(pedir, origen, destino, elemento, parada)


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
    transformacion = elemento.get("sceneItemTransform")
    if transformacion:
        pedir("SetSceneItemTransform", {
            "sceneName": destino, "sceneItemId": identificador,
            "sceneItemTransform": transformacion}, parada)
    pedir("SetSceneItemEnabled", {
        "sceneName": destino, "sceneItemId": identificador,
        "sceneItemEnabled": elemento.get("sceneItemEnabled", True)}, parada)
