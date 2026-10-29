"""Elegir qué ventana captura una escena de OBS.

Recibe un cliente con `pedir(tipo, datos=None, parada=None)` como
`obs_destinos` y no crea conexiones.
"""

from __future__ import annotations

import time

from bellbird.core.idioma import N_, _
from bellbird.obs import obs_cliente


NOMBRE_CAPTURA = N_("Captura de ventana")
NOMBRE_SONDA = N_("YTChat, lista de ventanas")

_TIPOS_CAPTURA = ("window_capture", "game_capture")


def ventana_legible(item_name) -> str:
    """Texto para leer en voz alta a partir del nombre que da OBS."""
    texto = str(item_name or "").strip()
    if not texto.startswith("["):
        return texto
    cierre = texto.find("]")
    if cierre < 0:
        return texto
    programa = texto[1:cierre].strip()
    resto = texto[cierre + 1:].strip()
    if resto.startswith(":"):
        resto = resto[1:].strip()
    if not resto:
        return programa
    if not programa:
        return resto
    # Traductores: {resto} es el título de la ventana y {programa} su programa.
    return _("{resto}, de {programa}").format(resto=resto,
                                              programa=programa)


def es_ventana_sin_titulo(item_name) -> bool:
    """Dice si el nombre que da OBS es de una ventana sin título."""
    texto = str(item_name or "").strip()
    if not texto:
        return True
    if not texto.startswith("["):
        return False
    cierre = texto.find("]")
    if cierre < 0:
        return False
    resto = texto[cierre + 1:].strip()
    if resto.startswith(":"):
        resto = resto[1:].strip()
    if not resto:
        return True
    return resto.lower() == "(null)"


def _legible_desde_valor(item_value) -> str:
    # El valor trae lo mismo que el nombre pero en otro orden,
    # "Título:Clase:programa.exe"; así la frase sale sin pedir la lista.
    texto = str(item_value or "").strip()
    partes = [parte.strip() for parte in texto.split(":")]
    if len(partes) < 2:
        return texto
    titulo = partes[0]
    programa = partes[-1]
    if not titulo:
        return programa
    if not programa:
        return titulo
    # Traductores: {titulo} es el título de la ventana y {programa} su programa.
    return _("{titulo}, de {programa}").format(titulo=titulo,
                                                programa=programa)


def _datos(cliente, tipo, datos=None, parada=None):
    respuesta = cliente.pedir(tipo, datos, parada=parada)
    return respuesta.get("responseData", {}) or {}


def _clase(elemento, por_nombre) -> str:
    clase = elemento.get("inputKind", "") or ""
    if clase:
        return clase
    return por_nombre.get(elemento.get("sourceName", "") or "", "")


def captura_de_escena(cliente, escena, parada=None):
    """Primera captura de la escena, prefiriendo las habilitadas."""
    elementos = _datos(cliente, "GetSceneItemList", {"sceneName": escena},
                       parada).get("sceneItems", ()) or ()
    entradas = _datos(cliente, "GetInputList", parada=parada).get(
        "inputs", ()) or ()
    por_nombre = {entrada.get("inputName", ""): entrada.get("inputKind", "")
                  for entrada in entradas if entrada.get("inputName", "")}
    candidatas = []
    for elemento in elementos:
        if elemento.get("sourceName", "") == NOMBRE_SONDA:
            continue
        if not elemento.get("sourceName", ""):
            continue
        clase = _clase(elemento, por_nombre)
        if clase not in _TIPOS_CAPTURA:
            continue
        copia = dict(elemento)
        copia["inputKind"] = clase
        candidatas.append(copia)
    if not candidatas:
        return None
    for candidata in candidatas:
        if candidata.get("sceneItemEnabled", True):
            return candidata
    return candidatas[0]


def _opciones(items, conservar="") -> tuple:
    opciones = []
    for item in items or ():
        if item.get("itemEnabled", True) is False:
            continue
        valor = item.get("itemValue", "") or ""
        if not valor:
            continue
        if valor != conservar and es_ventana_sin_titulo(item.get("itemName", "")):
            continue
        opciones.append((ventana_legible(item.get("itemName", "")), valor))
    return tuple(opciones)


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
    # (medido el 13/10/2026). Sin esta espera captura_de_escena encuentra la
    # sonda y usar_ventana la configura y habilita. Si vence el plazo se
    # sigue igual, porque captura_de_escena ya la ignora.
    inicio = reloj()
    while True:
        if not _sonda_visible(cliente, escena, parada):
            return
        if reloj() - inicio >= espera:
            return
        dormir(intervalo)


def ventanas(cliente, escena, parada=None, dormir=time.sleep,
             reloj=time.monotonic):
    """Ventanas abiertas y cuál captura la escena, si tiene captura."""
    captura = captura_de_escena(cliente, escena, parada)
    if captura is not None:
        nombre = captura.get("sourceName", "")
        items = _datos(
            cliente, "GetInputPropertiesListPropertyItems",
            {"inputName": nombre, "propertyName": "window"},
            parada).get("propertyItems", ()) or ()
        ajustes = _datos(cliente, "GetInputSettings", {"inputName": nombre},
                         parada).get("inputSettings", {}) or {}
        actual = str(ajustes.get("window", "") or "")
        return _opciones(items, conservar=actual), actual
    _quitar_sonda(cliente, escena, parada)
    _esperar_sonda_fuera(cliente, escena, parada, dormir=dormir,
                         reloj=reloj)
    # OBS no borra la sonda suelta aunque RemoveInput responda éxito, y
    # crearla de nuevo falla con 601 (medido el 14/10/2026): se reutiliza.
    if not _sonda_en_lista(cliente, parada):
        cliente.pedir("CreateInput", {"sceneName": escena,
                                      "inputName": NOMBRE_SONDA,
                                      "inputKind": "window_capture",
                                      "sceneItemEnabled": False},
                      parada=parada)
    try:
        items = _datos(
            cliente, "GetInputPropertiesListPropertyItems",
            {"inputName": NOMBRE_SONDA, "propertyName": "window"},
            parada).get("propertyItems", ()) or ()
    finally:
        _quitar_sonda(cliente, escena, parada)
        _esperar_sonda_fuera(cliente, escena, parada, dormir=dormir,
                             reloj=reloj)
    return _opciones(items), ""


def _nombre_libre(ocupados) -> str:
    """Nombre para la fuente nueva: el base o el primero con número libre."""
    nombre = _(NOMBRE_CAPTURA)
    contador = 2
    while nombre in ocupados:
        # Traductores: {nombre} es el nombre base y {contador} el número libre.
        nombre = _("{nombre} {contador}").format(nombre=_(NOMBRE_CAPTURA),
                                                 contador=contador)
        contador += 1
    return nombre


def usar_ventana(cliente, escena, item_value, parada=None) -> str:
    """Hace que la escena capture la ventana indicada y lo anuncia."""
    captura = captura_de_escena(cliente, escena, parada)
    legible = _legible_desde_valor(item_value)
    if captura is not None:
        nombre = captura.get("sourceName", "")
        ajustes = {"window": item_value, "overlay": True}
        if captura.get("inputKind", "") == "game_capture":
            ajustes["capture_mode"] = "window"
        cliente.pedir("SetInputSettings",
                      {"inputName": nombre, "inputSettings": ajustes},
                      parada=parada)
        if not captura.get("sceneItemEnabled", True):
            cliente.pedir("SetSceneItemEnabled",
                          {"sceneName": escena,
                           "sceneItemId": captura.get("sceneItemId"),
                           "sceneItemEnabled": True}, parada=parada)
        # Traductores: {legible} es «título, de programa».
        return _("Ahora se captura {legible}.").format(legible=legible)
    entradas = _datos(cliente, "GetInputList", parada=parada).get(
        "inputs", ()) or ()
    ocupados = {entrada.get("inputName", "") for entrada in entradas}
    nombre = _nombre_libre(ocupados)
    respuesta = cliente.pedir(
        "CreateInput", {"sceneName": escena, "inputName": nombre,
                        "inputKind": "window_capture",
                        "inputSettings": {"window": item_value},
                        "sceneItemEnabled": True}, parada=parada)
    identificador = (respuesta.get("responseData", {}) or {}).get(
        "sceneItemId")
    if identificador is None:
        elementos = _datos(cliente, "GetSceneItemList", {"sceneName": escena},
                           parada).get("sceneItems", ()) or ()
        for elemento in elementos:
            if elemento.get("sourceName", "") == nombre:
                identificador = elemento.get("sceneItemId")
                break
    cliente.pedir("SetSceneItemIndex",
                  {"sceneName": escena, "sceneItemId": identificador,
                   "sceneItemIndex": 0}, parada=parada)
    lienzo = _datos(cliente, "GetVideoSettings", parada=parada)
    cliente.pedir(
        "SetSceneItemTransform",
        {"sceneName": escena, "sceneItemId": identificador,
         "sceneItemTransform": {"positionX": 0, "positionY": 0,
                                "alignment": 5,
                                "boundsType": "OBS_BOUNDS_SCALE_INNER",
                                "boundsAlignment": 0,
                                "boundsWidth": lienzo.get("baseWidth", 0),
                                "boundsHeight": lienzo.get("baseHeight", 0)}},
        parada=parada)
    # Traductores: {legible} es «título, de programa».
    return _("Ahora se captura {legible}.").format(legible=legible)
