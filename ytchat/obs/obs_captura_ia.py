"""Qué se puede capturar de OBS para preguntarle a la IA, y capturarlo.

Recibe un cliente con `pedir(tipo, datos=None, parada=None)` como
`obs_prevuelo` y no crea conexiones. Las otras escenas no se ofrecen:
fuera del aire OBS no las captura.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

from ytchat.core import diagnostico
from ytchat.obs import luz_imagen
from ytchat.obs import obs_prevuelo


logger = diagnostico.obtener_logger(__name__)

_TIPOS_SIN_IMAGEN = ("wasapi_input_capture", "wasapi_output_capture",
                     "wasapi_process_output_capture")


class CapturaFallida(Exception):
    """OBS no pudo entregar la imagen pedida, en palabras para el usuario."""


@dataclass(frozen=True)
class OpcionCaptura:
    fuente: str
    etiqueta: str
    ancho: int
    alto: int


@dataclass(frozen=True)
class Captura:
    jpeg: bytes
    ancho: int
    alto: int
    negra: bool | None


def _datos(cliente, tipo, datos=None, parada=None):
    respuesta = cliente.pedir(tipo, datos, parada=parada)
    return respuesta.get("responseData", {}) or {}


def _entero(valor) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def _texto_fallo(opcion) -> str:
    return (f"No se pudo capturar {opcion.etiqueta}. Comprueba que esté "
            "visible en la escena al aire.")


def _opcion_elemento(elemento, por_nombre):
    nombre = elemento.get("sourceName", "") or ""
    if not nombre or not elemento.get("sceneItemEnabled", True):
        return None
    transformada = elemento.get("sceneItemTransform") or {}
    ancho = _entero(transformada.get("sourceWidth"))
    alto = _entero(transformada.get("sourceHeight"))
    if ancho <= 0 or alto <= 0:
        return None
    clase = por_nombre.get(nombre, "") or ""
    if clase in _TIPOS_SIN_IMAGEN:
        return None
    tipo = obs_prevuelo._TIPOS.get(clase, "")
    etiqueta = f"{nombre} ({tipo})" if tipo else nombre
    return OpcionCaptura(nombre, etiqueta, ancho, alto)


def opciones(cliente, parada=None) -> tuple:
    """Lo que se puede capturar, con la escena al aire primero."""
    escena = _datos(cliente, "GetCurrentProgramScene",
                    parada=parada).get("currentProgramSceneName", "") or ""
    lienzo = _datos(cliente, "GetVideoSettings", parada=parada)
    base = OpcionCaptura(escena, f"Escena al aire: {escena}",
                         _entero(lienzo.get("baseWidth")),
                         _entero(lienzo.get("baseHeight")))
    elementos = _datos(cliente, "GetSceneItemList", {"sceneName": escena},
                       parada).get("sceneItems", ()) or ()
    entradas = _datos(cliente, "GetInputList",
                      parada=parada).get("inputs", ()) or ()
    por_nombre = {entrada.get("inputName", ""): entrada.get("inputKind", "")
                  for entrada in entradas if entrada.get("inputName", "")}
    # Índice más alto primero: lo de adelante tapa lo de atrás.
    ordenados = sorted(elementos,
                       key=lambda e: _entero(e.get("sceneItemIndex", 0)),
                       reverse=True)
    lista = [base]
    for elemento in ordenados:
        opcion = _opcion_elemento(elemento, por_nombre)
        if opcion is not None:
            lista.append(opcion)
    return tuple(lista)


def _parametros_lado(opcion, lado) -> dict:
    """Un solo lado para no deformar: el largo, o el ancho si no hay."""
    if opcion.ancho <= 0 or opcion.alto <= 0:
        return {"imageWidth": lado}
    if opcion.ancho >= opcion.alto:
        return {"imageWidth": min(lado, opcion.ancho)}
    return {"imageHeight": min(lado, opcion.alto)}


def _tamano_salida(opcion, lado) -> tuple:
    pedido = _parametros_lado(opcion, lado)
    if "imageHeight" in pedido:
        alto = pedido["imageHeight"]
        return (round(opcion.ancho * alto / opcion.alto), alto)
    ancho = pedido["imageWidth"]
    if opcion.ancho <= 0 or opcion.alto <= 0:
        # Sin referencia no se calcula la proporción: se informa el lado
        # pedido y cero en el otro eje.
        return (ancho, 0)
    return (ancho, round(opcion.alto * ancho / opcion.ancho))


def _decodificar(texto) -> bytes:
    texto = str(texto or "")
    if "," in texto:
        texto = texto.split(",", 1)[1]
    return base64.b64decode(texto)


def _medir(cliente, opcion, parada) -> bool | None:
    parametros = _parametros_lado(opcion, 160)
    parametros["imageFormat"] = "bmp"
    try:
        datos = _datos(cliente, "GetSourceScreenshot",
                       {"sourceName": opcion.fuente, **parametros}, parada)
        return luz_imagen.es_negra(_decodificar(datos.get("imageData", "")))
    except Exception as error:
        # Medir no es motivo para perder la captura.
        logger.warning("obs_captura_ia: no se pudo medir la luz de %r: %s",
                       opcion.fuente, error)
        return None


def capturar(cliente, opcion, lado=1280, calidad=75, parada=None) -> Captura:
    """Captura la opción en JPEG acotado y avisa si salió negra."""
    parametros = _parametros_lado(opcion, lado)
    parametros["imageFormat"] = "jpg"
    parametros["imageCompressionQuality"] = calidad
    try:
        datos = _datos(cliente, "GetSourceScreenshot",
                       {"sourceName": opcion.fuente, **parametros}, parada)
        jpeg = _decodificar(datos.get("imageData", ""))
    except Exception as error:
        raise CapturaFallida(_texto_fallo(opcion)) from error
    (ancho, alto) = _tamano_salida(opcion, lado)
    return Captura(jpeg, ancho, alto, _medir(cliente, opcion, parada))


def vista_previa(cliente, opcion, lado=320, parada=None) -> bytes:
    """JPEG chico de la opción para la subventana con resto visual."""
    parametros = _parametros_lado(opcion, lado)
    parametros["imageFormat"] = "jpg"
    parametros["imageCompressionQuality"] = 60
    try:
        datos = _datos(cliente, "GetSourceScreenshot",
                       {"sourceName": opcion.fuente, **parametros}, parada)
        return _decodificar(datos.get("imageData", ""))
    except Exception as error:
        raise CapturaFallida(_texto_fallo(opcion)) from error
