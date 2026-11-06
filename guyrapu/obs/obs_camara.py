"""La cámara de la escena al aire de OBS, y un cuadro chico en BMP.

Recibe un cliente con `pedir(tipo, datos=None, parada=None)` como
`obs_captura_ia` y no crea conexiones. La lectura de `responseData` y la
decodificación del base64 se reutilizan de `obs_captura_ia`.
"""

from __future__ import annotations

from dataclasses import dataclass

from guyrapu.core import diagnostico
from guyrapu.core.idioma import _
from guyrapu.obs import obs_captura_ia


logger = diagnostico.obtener_logger(__name__)


class CamaraNoEncontrada(Exception):
    """No hay cámara visible para encuadrar, en palabras para el usuario."""


@dataclass(frozen=True)
class CamaraObs:
    nombre: str
    espejo: bool


@dataclass(frozen=True)
class ElementoCamara:
    """La escena o grupo que tiene a la cámara, su id y si se ve."""

    contenedor: str
    id: int
    visible: bool


def _indice(elemento) -> int:
    try:
        return int(elemento.get("sceneItemIndex", 0))
    except (TypeError, ValueError):
        return 0


def _id_elemento(elemento) -> int:
    try:
        return int(elemento.get("sceneItemId", 0))
    except (TypeError, ValueError):
        return 0


def _factor_espejo(elemento) -> float:
    """Signo horizontal del elemento: `scaleX` o 1 sin transformación."""
    transformada = elemento.get("sceneItemTransform") or {}
    try:
        return float(transformada.get("scaleX", 1.0))
    except (TypeError, ValueError):
        return 1.0


def _hijos(cliente, fuente, es_grupo, parada):
    if es_grupo:
        datos = obs_captura_ia.datos_respuesta(
            cliente, "GetGroupSceneItemList", {"sceneName": fuente}, parada)
    else:
        datos = obs_captura_ia.datos_respuesta(
            cliente, "GetSceneItemList", {"sceneName": fuente}, parada)
    return datos.get("sceneItems", ()) or ()


def _hijos_seguros(cliente, elemento, fuente, parada):
    try:
        return _hijos(cliente, fuente, bool(elemento.get("isGroup")), parada)
    except Exception as error:
        # Lo que no es escena ni grupo no tiene hijos.
        logger.warning("obs_camara: no se pudieron leer los hijos de %r: %s",
                       fuente, error)
        return None


def _buscar_en(elementos, cliente, por_nombre, nombre, nivel, acumulado,
               parada, contenedor="", incluir_oculta=False):
    # Índice más alto primero: lo de adelante tapa lo de atrás.
    ordenados = sorted(elementos, key=_indice, reverse=True)
    for elemento in ordenados:
        fuente = elemento.get("sourceName", "") or ""
        if not fuente:
            continue
        visible = bool(elemento.get("sceneItemEnabled", True))
        signo = acumulado * _factor_espejo(elemento)
        es_camara = (fuente == nombre if nombre
                     else por_nombre.get(fuente, "") == "dshow_input")
        if es_camara:
            if not visible and not incluir_oculta:
                continue
            if incluir_oculta:
                return ElementoCamara(contenedor, _id_elemento(elemento),
                                      visible)
            return CamaraObs(fuente, signo < 0)
        # Una escena o grupo oculto no sale al aire: no se recorre.
        if not visible or nivel >= 3 or fuente in por_nombre:
            continue
        hijos = _hijos_seguros(cliente, elemento, fuente, parada)
        if hijos is None:
            continue
        hallada = _buscar_en(hijos, cliente, por_nombre, nombre,
                             nivel + 1, signo, parada, contenedor=fuente,
                             incluir_oculta=incluir_oculta)
        if hallada is not None:
            return hallada
    return None


def fuentes_video(cliente, parada=None) -> tuple:
    """Nombres de las cámaras de OBS, en el orden de OBS."""
    entradas = obs_captura_ia.datos_respuesta(
        cliente, "GetInputList", parada=parada).get("inputs", ()) or ()
    return tuple(entrada.get("inputName", "")
                 for entrada in entradas
                 if entrada.get("inputKind", "") == "dshow_input"
                 and entrada.get("inputName", ""))


def buscar_camara(cliente, nombre="", parada=None) -> CamaraObs:
    """La cámara visible en la escena al aire, y si sale en espejo.

    Con `nombre` vacío trae la primera fuente `dshow_input` de adelante
    hacia atrás. Con `nombre` trae esa fuente, de cualquier clase.
    """
    escena = obs_captura_ia.datos_respuesta(
        cliente, "GetCurrentProgramScene", parada=parada).get(
            "currentProgramSceneName", "") or ""
    entradas = obs_captura_ia.datos_respuesta(
        cliente, "GetInputList", parada=parada).get("inputs", ()) or ()
    por_nombre = {entrada.get("inputName", ""): entrada.get("inputKind", "")
                  for entrada in entradas if entrada.get("inputName", "")}
    elementos = obs_captura_ia.datos_respuesta(
        cliente, "GetSceneItemList", {"sceneName": escena},
        parada).get("sceneItems", ()) or ()
    if nombre:
        hallada = _buscar_en(elementos, cliente, por_nombre, nombre, 1,
                             1.0, parada, contenedor=escena)
        if hallada is None:
            raise CamaraNoEncontrada(
                _("La fuente {nombre} no está en la escena actual.").format(
                    nombre=nombre))
        return hallada
    if "dshow_input" not in por_nombre.values():
        raise CamaraNoEncontrada(_("No hay ninguna cámara en OBS."))
    hallada = _buscar_en(elementos, cliente, por_nombre, "", 1, 1.0,
                         parada, contenedor=escena)
    if hallada is None:
        raise CamaraNoEncontrada(
            _("La cámara de OBS no está en la escena actual."))
    return hallada


def _datos_de_escena(cliente, parada=None):
    """La escena al aire, sus elementos y las clases de las fuentes."""
    escena = obs_captura_ia.datos_respuesta(
        cliente, "GetCurrentProgramScene", parada=parada).get(
            "currentProgramSceneName", "") or ""
    entradas = obs_captura_ia.datos_respuesta(
        cliente, "GetInputList", parada=parada).get("inputs", ()) or ()
    por_nombre = {entrada.get("inputName", ""): entrada.get("inputKind", "")
                  for entrada in entradas if entrada.get("inputName", "")}
    elementos = obs_captura_ia.datos_respuesta(
        cliente, "GetSceneItemList", {"sceneName": escena},
        parada).get("sceneItems", ()) or ()
    return escena, por_nombre, elementos


def elemento_camara(cliente, nombre="", parada=None) -> ElementoCamara:
    """La escena o grupo que tiene a la cámara, su id y si se ve.

    A diferencia de `buscar_camara`, la cámara cuenta aunque esté oculta.
    Las escenas y grupos que la contienen sí tienen que estar visibles.
    """
    escena, por_nombre, elementos = _datos_de_escena(cliente, parada)
    if not nombre and "dshow_input" not in por_nombre.values():
        raise CamaraNoEncontrada(_("No hay ninguna cámara en OBS."))
    hallada = _buscar_en(elementos, cliente, por_nombre, nombre, 1, 1.0,
                         parada, contenedor=escena, incluir_oculta=True)
    if hallada is None:
        if nombre:
            raise CamaraNoEncontrada(
                _("La fuente {nombre} no está en la escena actual.").format(
                    nombre=nombre))
        raise CamaraNoEncontrada(
            _("La cámara de OBS no está en la escena actual."))
    return hallada


def alternar_camara(cliente, nombre="", parada=None) -> bool:
    """Oculta o muestra la cámara y devuelve si quedó visible."""
    camara = elemento_camara(cliente, nombre, parada)
    visible = not camara.visible
    obs_captura_ia.datos_respuesta(
        cliente, "SetSceneItemEnabled",
        {"sceneName": camara.contenedor, "sceneItemId": camara.id,
         "sceneItemEnabled": visible}, parada)
    return visible


def capturar_cuadro(cliente, camara, lado=320, parada=None) -> bytes:
    """Cuadro chico en BMP de la cámara, ya decodificado."""
    try:
        datos = obs_captura_ia.datos_respuesta(
            cliente, "GetSourceScreenshot",
            {"sourceName": camara.nombre, "imageFormat": "bmp",
             "imageWidth": lado}, parada)
        return obs_captura_ia.decodificar(datos.get("imageData", ""))
    except Exception as error:
        opcion = obs_captura_ia.OpcionCaptura(camara.nombre, camara.nombre,
                                              0, 0)
        raise obs_captura_ia.CapturaFallida(
            obs_captura_ia.texto_fallo(opcion)) from error
