"""La cámara de la escena al aire de OBS, y un cuadro chico en BMP.

Recibe un cliente con `pedir(tipo, datos=None, parada=None)` como
`obs_captura_ia` y no crea conexiones. La lectura de `responseData` y la
decodificación del base64 se reutilizan de `obs_captura_ia`.
"""

from __future__ import annotations

from dataclasses import dataclass

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.obs import obs_captura_ia


logger = diagnostico.obtener_logger(__name__)


class CamaraNoEncontrada(Exception):
    """No hay cámara visible para encuadrar, en palabras para el usuario."""


@dataclass(frozen=True)
class CamaraObs:
    nombre: str
    espejo: bool


def _indice(elemento) -> int:
    try:
        return int(elemento.get("sceneItemIndex", 0))
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


def _buscar_en(elementos, cliente, por_nombre, nombre, nivel, acumulado,
               parada):
    # Índice más alto primero: lo de adelante tapa lo de atrás.
    ordenados = sorted(elementos, key=_indice, reverse=True)
    for elemento in ordenados:
        if not elemento.get("sceneItemEnabled", True):
            continue
        fuente = elemento.get("sourceName", "") or ""
        if not fuente:
            continue
        signo = acumulado * _factor_espejo(elemento)
        if nombre:
            if fuente == nombre:
                return CamaraObs(fuente, signo < 0)
        elif por_nombre.get(fuente, "") == "dshow_input":
            return CamaraObs(fuente, signo < 0)
        if nivel >= 3 or fuente in por_nombre:
            continue
        try:
            hijos = _hijos(cliente, fuente,
                           bool(elemento.get("isGroup")), parada)
        except Exception as error:
            # Lo que no es escena ni grupo no tiene hijos.
            logger.warning("obs_camara: no se pudieron leer los hijos "
                           "de %r: %s", fuente, error)
            continue
        hallada = _buscar_en(hijos, cliente, por_nombre, nombre,
                             nivel + 1, signo, parada)
        if hallada is not None:
            return hallada
    return None


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
                             1.0, parada)
        if hallada is None:
            raise CamaraNoEncontrada(
                _("La fuente {nombre} no está en la escena al aire.").format(
                    nombre=nombre))
        return hallada
    if "dshow_input" not in por_nombre.values():
        raise CamaraNoEncontrada(_("No hay ninguna cámara en OBS."))
    hallada = _buscar_en(elementos, cliente, por_nombre, "", 1, 1.0,
                         parada)
    if hallada is None:
        raise CamaraNoEncontrada(
            _("La cámara de OBS no está en la escena al aire."))
    return hallada


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
