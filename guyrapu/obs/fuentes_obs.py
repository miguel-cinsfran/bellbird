"""Eliminar, renombrar, duplicar y transformar fuentes de una escena de OBS."""

from __future__ import annotations

from guyrapu.core.idioma import _
from guyrapu.obs import obs_cliente
from guyrapu.obs.obs_panel import NOMBRE_FUENTE
from guyrapu.obs.transformar_fuente import (
    limpiar_transformacion, nombre_de_copia)


class NoSePuedeDuplicar(obs_cliente.ObsError):
    """La fuente no se puede duplicar, y se explica por qué."""


def motivo_para_no_duplicar(fuente, tipo) -> str:
    """El motivo para no duplicar, o vacío si se puede."""
    if fuente == NOMBRE_FUENTE:
        return _("Solo puede haber un chat en el vídeo.")
    if str(tipo or "").casefold() == _("cámara").casefold():
        return _("Una cámara no se puede abrir dos veces. Para usarla en "
                 "otra escena, duplica la escena.")
    return ""


def eliminar(gestor, escena, fuente, parada=None) -> None:
    """Saca la fuente de esta escena, sin borrar la entrada de OBS."""
    elemento = _elemento(gestor, escena, fuente, parada)
    _datos(gestor, "RemoveSceneItem", {
        "sceneName": escena, "sceneItemId": elemento["sceneItemId"],
    }, parada)


def renombrar(gestor, escena, fuente, nuevo, parada=None) -> None:
    """Cambia el nombre de la entrada, que es el mismo en todas las escenas."""
    _datos(gestor, "SetInputName", {
        "inputName": fuente, "newInputName": nuevo,
    }, parada)


def duplicar(gestor, escena, fuente, tipo="", parada=None) -> str:
    """Duplica la fuente justo delante de la original y devuelve el nombre."""
    motivo = motivo_para_no_duplicar(fuente, tipo)
    if motivo:
        raise NoSePuedeDuplicar(motivo)
    entradas = _datos(gestor, "GetInputList", parada=parada).get("inputs", ())
    entrada = _entrada(entradas, fuente)
    if entrada is None:
        raise obs_cliente.ObsError(
            obs_cliente.mensaje_de_fallo_obs("not found"))
    if entrada.get("inputKind") == "dshow_input":
        raise NoSePuedeDuplicar(motivo_para_no_duplicar(fuente, _("cámara")))
    elemento = _elemento(gestor, escena, fuente, parada)
    ajustes = _datos(gestor, "GetInputSettings", {
        "inputName": fuente,
    }, parada).get("inputSettings", {})
    nuevo = nombre_de_copia(
        [candidata.get("inputName", "") for candidata in entradas], fuente)
    respuesta = _datos(gestor, "CreateInput", {
        "sceneName": escena, "inputName": nuevo,
        "inputKind": entrada.get("inputKind", ""),
        "inputSettings": ajustes,
        "sceneItemEnabled": bool(elemento.get("sceneItemEnabled", True)),
    }, parada)
    identificador = respuesta.get("sceneItemId")
    if identificador is None:
        creada = _elemento(gestor, escena, nuevo, parada)
        identificador = creada["sceneItemId"]
    _copiar_forma(gestor, escena, identificador, elemento, parada)
    return nuevo


def aplicar_transformacion(gestor, escena, fuente, calculo, parada=None):
    """Lee el lienzo, calcula la transformación nueva y la aplica."""
    elemento = _elemento(gestor, escena, fuente, parada)
    lienzo = _datos(gestor, "GetVideoSettings", parada=parada)
    nueva = calculo(elemento.get("sceneItemTransform", {}),
                    lienzo.get("baseWidth", 0), lienzo.get("baseHeight", 0))
    nueva = limpiar_transformacion(nueva)
    gestor.transformar(escena, nueva, parada=parada, fuente=fuente)
    return nueva


def _copiar_forma(gestor, escena, identificador, elemento, parada):
    forma = limpiar_transformacion(elemento.get("sceneItemTransform", {}))
    if forma:
        _datos(gestor, "SetSceneItemTransform", {
            "sceneName": escena, "sceneItemId": identificador,
            "sceneItemTransform": forma,
        }, parada)
    _datos(gestor, "SetSceneItemIndex", {
        "sceneName": escena, "sceneItemId": identificador,
        "sceneItemIndex": elemento.get("sceneItemIndex", 0) + 1,
    }, parada)


def _elemento(gestor, escena, fuente, parada):
    elemento = next(
        (candidato for candidato in gestor.elementos(escena, parada)
         if candidato.get("sourceName") == fuente), None)
    if elemento is None:
        raise obs_cliente.ObsError(
            obs_cliente.mensaje_de_fallo_obs("not found"))
    return elemento


def _entrada(entradas, fuente):
    return next(
        (entrada for entrada in entradas
         if entrada.get("inputName") == fuente), None)


def _datos(gestor, tipo, datos=None, parada=None):
    return gestor._pedir(tipo, datos, parada) or {}
