"""Agregar a una escena de OBS una cámara de Windows.

Recibe un cliente con `pedir(tipo, datos=None, parada=None)` como
`obs_camara` y no crea conexiones.
"""

from __future__ import annotations

import time

from bellbird.core.idioma import N_, _
from bellbird.obs import obs_cliente, obs_disposicion


NOMBRE_CAMARA = N_("Cámara")
NOMBRE_SONDA = N_("Bellbird, lista de cámaras")


def _datos(cliente, tipo, datos=None, parada=None):
    respuesta = cliente.pedir(tipo, datos, parada=parada)
    return respuesta.get("responseData", {}) or {}


def _sonda_en_lista(cliente, parada=None) -> bool:
    entradas = _datos(cliente, "GetInputList", parada=parada).get(
        "inputs", ()) or ()
    return any(entrada.get("inputName", "") == NOMBRE_SONDA
               for entrada in entradas)


def _quitar_sonda(cliente, escena, parada=None) -> None:
    # RemoveInput no quita las entradas que están en una escena (en OBS
    # 32.2.2 responde éxito sin borrarlas, medido el 13/10/2026); por eso la
    # sonda se quita con RemoveSceneItem y RemoveInput solo cubre el resto de
    # que viva en otra escena.
    elementos = _datos(cliente, "GetSceneItemList", {"sceneName": escena},
                       parada).get("sceneItems", ()) or ()
    for elemento in elementos:
        if (elemento.get("sourceName", "") == NOMBRE_SONDA
                and elemento.get("sceneItemId") is not None):
            cliente.pedir("RemoveSceneItem",
                          {"sceneName": escena,
                           "sceneItemId": elemento.get("sceneItemId")},
                          parada=parada)
    if _sonda_en_lista(cliente, parada):
        try:
            cliente.pedir("RemoveInput", {"inputName": NOMBRE_SONDA},
                          parada=parada)
        except obs_cliente.ObsError:
            if _sonda_en_lista(cliente, parada):
                raise


def _sonda_visible(cliente, escena, parada=None) -> bool:
    if _sonda_en_lista(cliente, parada):
        return True
    elementos = _datos(cliente, "GetSceneItemList", {"sceneName": escena},
                       parada).get("sceneItems", ()) or ()
    return any(elemento.get("sourceName", "") == NOMBRE_SONDA
               for elemento in elementos)


def _esperar_sonda_fuera(cliente, escena, parada=None, espera=3.0,
                         intervalo=0.05, dormir=time.sleep,
                         reloj=time.monotonic):
    # OBS aplica el borrado de forma asincrónica: la entrada puede seguir en
    # GetInputList y el elemento en la escena justo después de borrarlos
    # (medido el 13/10/2026). Si vence el plazo se sigue igual, porque la
    # sonda se reutiliza si quedó suelta.
    inicio = reloj()
    while True:
        if not _sonda_visible(cliente, escena, parada):
            return
        if reloj() - inicio >= espera:
            return
        dormir(intervalo)


def camaras_disponibles(cliente, escena, parada=None, dormir=time.sleep,
                        reloj=time.monotonic):
    """Cámaras de Windows que OBS ofrece, como pares (nombre, valor)."""
    _quitar_sonda(cliente, escena, parada)
    _esperar_sonda_fuera(cliente, escena, parada, dormir=dormir,
                         reloj=reloj)
    # OBS no borra la sonda suelta aunque RemoveInput responda éxito, y
    # crearla de nuevo falla con 601 (medido el 14/10/2026): se reutiliza.
    if not _sonda_en_lista(cliente, parada):
        cliente.pedir("CreateInput", {"sceneName": escena,
                                      "inputName": NOMBRE_SONDA,
                                      "inputKind": "dshow_input",
                                      "sceneItemEnabled": False},
                      parada=parada)
    try:
        items = _datos(
            cliente, "GetInputPropertiesListPropertyItems",
            {"inputName": NOMBRE_SONDA,
             "propertyName": "video_device_id"},
            parada).get("propertyItems", ()) or ()
    finally:
        _quitar_sonda(cliente, escena, parada)
        _esperar_sonda_fuera(cliente, escena, parada, dormir=dormir,
                             reloj=reloj)
    return tuple((item.get("itemName", ""), item.get("itemValue", ""))
                 for item in items
                 if item.get("itemEnabled", True) is not False
                 and item.get("itemValue", ""))


def _camara_existente(cliente, valor, parada=None) -> str:
    entradas = _datos(cliente, "GetInputList", parada=parada).get(
        "inputs", ()) or ()
    for entrada in entradas:
        if entrada.get("inputKind", "") != "dshow_input":
            continue
        nombre = entrada.get("inputName", "")
        if not nombre:
            continue
        ajustes = _datos(cliente, "GetInputSettings",
                         {"inputName": nombre}, parada).get(
                             "inputSettings", {}) or {}
        if str(ajustes.get("video_device_id", "") or "") == valor:
            return nombre
    return ""


def _nombre_libre(ocupados) -> str:
    """Nombre para la fuente nueva: el base o el primero con número libre."""
    nombre = _(NOMBRE_CAMARA)
    contador = 2
    while nombre in ocupados:
        # Traductores: {nombre} es el nombre base y {contador} el número libre.
        nombre = _("{nombre} {contador}").format(nombre=_(NOMBRE_CAMARA),
                                                 contador=contador)
        contador += 1
    return nombre


def _identificador(cliente, escena, nombre, parada=None):
    elementos = _datos(cliente, "GetSceneItemList", {"sceneName": escena},
                       parada).get("sceneItems", ()) or ()
    for elemento in elementos:
        if elemento.get("sourceName", "") == nombre:
            return elemento.get("sceneItemId")
    return None


def _indice_mas_alto(cliente, escena, parada=None) -> int:
    elementos = _datos(cliente, "GetSceneItemList", {"sceneName": escena},
                       parada).get("sceneItems", ()) or ()
    return max((elemento.get("sceneItemIndex", 0)
                for elemento in elementos), default=0)


def _transformacion(base_ancho, base_alto) -> dict:
    x, y, _mascara = obs_disposicion.coordenadas(
        "inferior-derecha", base_ancho, base_alto)
    alineacion = obs_disposicion.ANCLAJES["inferior-derecha"]
    return {"positionX": x, "positionY": y, "alignment": alineacion,
            "boundsType": "OBS_BOUNDS_SCALE_INNER",
            "boundsAlignment": alineacion,
            "boundsWidth": base_ancho / 2, "boundsHeight": base_alto / 2}


def agregar(cliente, escena, valor, parada=None):
    """Agrega la cámara y devuelve su nombre y si era nueva."""
    existente = _camara_existente(cliente, valor, parada)
    if existente:
        return existente, False
    entradas = _datos(cliente, "GetInputList", parada=parada).get(
        "inputs", ()) or ()
    nombre = _nombre_libre({entrada.get("inputName", "")
                            for entrada in entradas})
    respuesta = cliente.pedir(
        "CreateInput", {"sceneName": escena, "inputName": nombre,
                        "inputKind": "dshow_input",
                        "inputSettings": {"video_device_id": valor},
                        "sceneItemEnabled": True}, parada=parada)
    identificador = (respuesta.get("responseData", {}) or {}).get(
        "sceneItemId")
    if identificador is None:
        identificador = _identificador(cliente, escena, nombre, parada)
    cliente.pedir("SetSceneItemIndex",
                  {"sceneName": escena, "sceneItemId": identificador,
                   "sceneItemIndex": _indice_mas_alto(cliente, escena,
                                                      parada)},
                  parada=parada)
    lienzo = _datos(cliente, "GetVideoSettings", parada=parada)
    cliente.pedir(
        "SetSceneItemTransform",
        {"sceneName": escena, "sceneItemId": identificador,
         "sceneItemTransform": _transformacion(
             lienzo.get("baseWidth", 0), lienzo.get("baseHeight", 0))},
        parada=parada)
    return nombre, True
