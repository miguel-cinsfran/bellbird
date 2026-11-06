"""Crear fuentes en OBS y leer o aplicar sus propiedades.

Recibe un `pedir(tipo, datos=None, parada=None)` como `escenas_obs` y no
crea conexiones. Las listas que da OBS se leen con una fuente sonda oculta
que se borra siempre, también si la lectura falla.
"""

from __future__ import annotations

import time

from guyrapu.core.idioma import N_
from guyrapu.obs import obs_cliente, tipos_fuente, transformar_fuente


NOMBRE_SONDA = N_("Guyrapu, sonda de propiedades")


def _datos(pedir, tipo, datos=None, parada=None):
    respuesta = pedir(tipo, datos, parada)
    if isinstance(respuesta, dict) and "responseData" in respuesta:
        return respuesta.get("responseData", {}) or {}
    return respuesta or {}


def _tipo_obs(pedir, tipo, parada=None) -> str:
    if tipo.clave != "texto":
        return tipo.tipo_obs
    tipos = _datos(pedir, "GetInputKindList", {"unversioned": False},
                   parada).get("inputKinds", ()) or ()
    return tipos_fuente.tipo_de_texto(tipos)


def nombres_ocupados(pedir, parada=None) -> set:
    """Los nombres de fuente de OBS, estén o no en alguna escena."""
    entradas = _datos(pedir, "GetInputList", parada=parada).get(
        "inputs", ()) or ()
    nombres = {entrada.get("inputName", "") for entrada in entradas
               if entrada.get("inputName", "")}
    escenas = _datos(pedir, "GetSceneList", parada=parada).get(
        "scenes", ()) or ()
    for escena in escenas:
        nombre_escena = escena.get("sceneName", "") or ""
        if not nombre_escena:
            continue
        elementos = _datos(
            pedir, "GetSceneItemList", {"sceneName": nombre_escena},
            parada).get("sceneItems", ()) or ()
        nombres.update(elemento.get("sourceName", "") for elemento in elementos
                       if elemento.get("sourceName", ""))
    return nombres


def fuentes_de_otras(pedir, escena, parada=None) -> tuple:
    """Fuentes de otras escenas que esta no tiene, sin repetirlas."""
    propias = {elemento.get("sourceName", "") for elemento in _datos(
        pedir, "GetSceneItemList", {"sceneName": escena}, parada).get(
            "sceneItems", ()) or ()}
    escenas = _datos(pedir, "GetSceneList", parada=parada).get(
        "scenes", ()) or ()
    encontradas = []
    for otra in escenas:
        nombre_escena = otra.get("sceneName", "") or ""
        if not nombre_escena or nombre_escena == escena:
            continue
        elementos = _datos(
            pedir, "GetSceneItemList", {"sceneName": nombre_escena},
            parada).get("sceneItems", ()) or ()
        for elemento in elementos:
            nombre = elemento.get("sourceName", "") or ""
            if nombre and nombre not in propias and nombre not in encontradas:
                encontradas.append(nombre)
    return tuple(encontradas)


def opciones_de(pedir, fuente, propiedad, parada=None) -> tuple:
    """Las opciones de una lista de propiedades de una fuente que ya existe."""
    items = _datos(
        pedir, "GetInputPropertiesListPropertyItems",
        {"inputName": fuente, "propertyName": propiedad},
        parada).get("propertyItems", ()) or ()
    return tipos_fuente.filtrar_items(items)


def _sonda_en_lista(pedir, parada=None) -> bool:
    entradas = _datos(pedir, "GetInputList", parada=parada).get(
        "inputs", ()) or ()
    return any(entrada.get("inputName", "") == NOMBRE_SONDA
               for entrada in entradas)


def _sonda_visible(pedir, escena, parada=None) -> bool:
    if _sonda_en_lista(pedir, parada):
        return True
    elementos = _datos(pedir, "GetSceneItemList", {"sceneName": escena},
                       parada).get("sceneItems", ()) or ()
    return any(elemento.get("sourceName", "") == NOMBRE_SONDA
               for elemento in elementos)


def _quitar_sonda(pedir, escena, parada=None) -> None:
    # RemoveInput no quita las entradas que están en una escena (en OBS
    # 32.2.2 responde éxito sin borrarlas, medido el 13/10/2026); por eso la
    # sonda se quita con RemoveSceneItem y RemoveInput solo cubre el resto de
    # que viva en otra escena.
    elementos = _datos(pedir, "GetSceneItemList", {"sceneName": escena},
                       parada).get("sceneItems", ()) or ()
    for elemento in elementos:
        if (elemento.get("sourceName", "") == NOMBRE_SONDA
                and elemento.get("sceneItemId") is not None):
            pedir("RemoveSceneItem",
                  {"sceneName": escena,
                   "sceneItemId": elemento.get("sceneItemId")},
                  parada)
    presentes = {entrada.get("inputName", "") for entrada in
                 (_datos(pedir, "GetInputList", parada=parada).get(
                     "inputs", ()) or ())}
    if NOMBRE_SONDA not in presentes:
        return
    try:
        pedir("RemoveInput", {"inputName": NOMBRE_SONDA}, parada)
    except obs_cliente.ObsError:
        if _sonda_en_lista(pedir, parada):
            raise


def _esperar_sonda_fuera(pedir, escena, parada=None, espera=3.0,
                         intervalo=0.05, dormir=time.sleep,
                         reloj=time.monotonic):
    # OBS aplica el borrado de forma asincrónica: la entrada puede seguir en
    # GetInputList y el elemento en la escena justo después de borrarlos
    # (medido el 13/10/2026). Si vence el plazo se sigue igual, porque la
    # sonda se reutiliza si quedó suelta.
    inicio = reloj()
    while True:
        if not _sonda_visible(pedir, escena, parada):
            return
        if reloj() - inicio >= espera:
            return
        dormir(intervalo)


def opciones_lista(pedir, escena, clave, propiedad, parada=None,
                   dormir=time.sleep, reloj=time.monotonic) -> tuple:
    """Las opciones de una lista de OBS, leídas con una sonda oculta."""
    tipo = tipos_fuente.por_clave(clave)
    if tipo is None:
        return ()
    tipo_obs = _tipo_obs(pedir, tipo, parada)
    _quitar_sonda(pedir, escena, parada)
    _esperar_sonda_fuera(pedir, escena, parada, dormir=dormir, reloj=reloj)
    # OBS no borra la sonda suelta aunque RemoveInput responda éxito, y
    # crearla de nuevo falla con 601 (medido el 14/10/2026): se reutiliza.
    if not _sonda_en_lista(pedir, parada):
        pedir("CreateInput", {"sceneName": escena,
                              "inputName": NOMBRE_SONDA,
                              "inputKind": tipo_obs,
                              "sceneItemEnabled": False}, parada)
    try:
        items = _datos(
            pedir, "GetInputPropertiesListPropertyItems",
            {"inputName": NOMBRE_SONDA, "propertyName": propiedad},
            parada).get("propertyItems", ()) or ()
    finally:
        _quitar_sonda(pedir, escena, parada)
        _esperar_sonda_fuera(pedir, escena, parada, dormir=dormir,
                             reloj=reloj)
    return tipos_fuente.filtrar_items(items)


def _identificador(pedir, escena, nombre, parada=None):
    elementos = _datos(pedir, "GetSceneItemList", {"sceneName": escena},
                       parada).get("sceneItems", ()) or ()
    for elemento in elementos:
        if elemento.get("sourceName", "") == nombre:
            return elemento.get("sceneItemId")
    return None


def _ubicar(pedir, escena, identificador, clave, lienzo, parada):
    ancho = lienzo.get("baseWidth", 0)
    alto = lienzo.get("baseHeight", 0)
    if clave == "texto":
        forma = tipos_fuente.transformacion_texto(ancho, alto)
    else:
        forma = transformar_fuente.limpiar_transformacion(
            transformar_fuente.ajustar({}, ancho, alto))
    pedir("SetSceneItemTransform",
          {"sceneName": escena, "sceneItemId": identificador,
           "sceneItemTransform": forma}, parada)
    if clave != "texto":
        pedir("SetSceneItemIndex",
              {"sceneName": escena, "sceneItemId": identificador,
               "sceneItemIndex": 0}, parada)


def crear(pedir, escena, clave, nombre, valores, parada=None) -> str:
    """Crea la fuente con los ajustes ya elegidos y la deja en su lugar."""
    tipo = tipos_fuente.por_clave(clave)
    if tipo is None:
        return ""
    respuesta = _datos(
        pedir, "CreateInput",
        {"sceneName": escena, "inputName": nombre,
         "inputKind": _tipo_obs(pedir, tipo, parada),
         "inputSettings": tipos_fuente.ajustes(clave, valores),
         "sceneItemEnabled": True}, parada)
    identificador = respuesta.get("sceneItemId")
    if identificador is None:
        identificador = _identificador(pedir, escena, nombre, parada)
    lienzo = _datos(pedir, "GetVideoSettings", parada=parada)
    if identificador is not None:
        _ubicar(pedir, escena, identificador, clave, lienzo, parada)
    return nombre


def _primera_transformacion(pedir, fuente, parada=None) -> dict:
    escenas = _datos(pedir, "GetSceneList", parada=parada).get(
        "scenes", ()) or ()
    for escena in escenas:
        nombre_escena = escena.get("sceneName", "") or ""
        if not nombre_escena:
            continue
        elementos = _datos(
            pedir, "GetSceneItemList", {"sceneName": nombre_escena},
            parada).get("sceneItems", ()) or ()
        for elemento in elementos:
            if elemento.get("sourceName", "") == fuente:
                return elemento.get("sceneItemTransform", {}) or {}
    return {}


def agregar_de_otra(pedir, escena, fuente, parada=None) -> str:
    """Pone en esta escena una fuente de otra, con su forma de allí."""
    # La forma se lee antes de crear: después, la fuente ya está en esta
    # escena y la primera que aparece puede ser este elemento sin forma.
    forma = transformar_fuente.limpiar_transformacion(
        _primera_transformacion(pedir, fuente, parada))
    respuesta = _datos(
        pedir, "CreateSceneItem",
        {"sceneName": escena, "sourceName": fuente}, parada)
    identificador = respuesta.get("sceneItemId")
    if identificador is not None and forma:
        pedir("SetSceneItemTransform",
              {"sceneName": escena, "sceneItemId": identificador,
               "sceneItemTransform": forma}, parada)
    return fuente


def propiedades(pedir, fuente, parada=None) -> tuple:
    """La clave del tipo de la fuente y los valores actuales de sus ajustes."""
    datos = _datos(pedir, "GetInputSettings", {"inputName": fuente}, parada)
    clave = tipos_fuente.clave_de_obs(datos.get("inputKind", ""))
    if not clave:
        return "", {}
    return clave, tipos_fuente.valores(
        clave, datos.get("inputSettings", {}) or {})


def aplicar_propiedades(pedir, fuente, clave, valores, parada=None) -> None:
    """Aplica solo los ajustes del tipo, sin tocar la transformación."""
    actual = _datos(pedir, "GetInputSettings", {"inputName": fuente},
                    parada).get("inputSettings", {}) or {}
    ajustes = tipos_fuente.ajustes(clave, valores, actual)
    if ajustes:
        pedir("SetInputSettings",
              {"inputName": fuente, "inputSettings": ajustes,
               "overlay": True}, parada)
