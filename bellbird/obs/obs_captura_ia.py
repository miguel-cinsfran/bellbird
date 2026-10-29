"""Qué se puede capturar de OBS para preguntarle a la IA, y capturarlo.

Recibe un cliente con `pedir(tipo, datos=None, parada=None)` como
`obs_prevuelo` y no crea conexiones. Las otras escenas no se ofrecen:
fuera del aire OBS no las captura.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.obs import luz_imagen
from bellbird.obs import obs_prevuelo


logger = diagnostico.obtener_logger(__name__)

_TIPOS_SIN_IMAGEN = ("wasapi_input_capture", "wasapi_output_capture",
                     "wasapi_process_output_capture")

TIPOS_CAPTURA = ("monitor_capture", "window_capture", "game_capture",
                 "dshow_input")


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
    motivo: str = ""
    fuente_motivo: str = ""


def sin_elegir(clase, ajustes) -> bool:
    """Si la fuente de captura no tiene elegido qué capturar.

    `GetInputSettings` solo devuelve lo que difiere del valor por
    defecto, así que lo ausente cuenta como vacío.
    """
    ajustes = ajustes or {}
    if clase == "monitor_capture":
        return ajustes.get("monitor_id", "") in ("", "DUMMY", None)
    if clase == "window_capture":
        return not (ajustes.get("window") or "")
    if clase == "game_capture":
        return (ajustes.get("capture_mode") == "window"
                and not (ajustes.get("window") or ""))
    if clase == "dshow_input":
        return not (ajustes.get("video_device_id") or "")
    return False


def motivo_negra(clases, ajustes_por_nombre) -> tuple:
    """Causa probable de la captura negra.

    Recibe los elementos visibles en el orden de la escena como pares
    (nombre, clase), y los ajustes de cada fuente de captura por
    nombre. Devuelve (motivo, fuente), con motivo vacío si no hay
    nada que decir.
    """
    ajustes_por_nombre = ajustes_por_nombre or {}
    pares = [(nombre, clase) for (nombre, clase) in clases
             if clase in TIPOS_CAPTURA]
    if not pares:
        return ("sin_fuente", "")
    for (nombre, clase) in pares:
        if sin_elegir(clase, ajustes_por_nombre.get(nombre, {})):
            return ("sin_elegir", nombre)
    return ("", "")


def _datos(cliente, tipo, datos=None, parada=None):
    respuesta = cliente.pedir(tipo, datos, parada=parada)
    return respuesta.get("responseData", {}) or {}


def _entero(valor) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def _texto_fallo(opcion) -> str:
    return (_("No se pudo capturar {etiqueta}. Comprueba que esté "
              "visible en la escena al aire.").format(
                  etiqueta=opcion.etiqueta))


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
    if tipo:
        # Traductores: {nombre} es la fuente y {tipo} su clase, como se lee en la lista.
        etiqueta = _("{nombre} ({tipo})").format(
            nombre=nombre, tipo=_(tipo))
    else:
        etiqueta = nombre
    return OpcionCaptura(nombre, etiqueta, ancho, alto)


def opciones(cliente, parada=None) -> tuple:
    """Lo que se puede capturar, con la escena al aire primero."""
    escena = _datos(cliente, "GetCurrentProgramScene",
                    parada=parada).get("currentProgramSceneName", "") or ""
    lienzo = _datos(cliente, "GetVideoSettings", parada=parada)
    base = OpcionCaptura(escena, _("Escena al aire: {escena}").format(escena=escena),
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


def _pares_visibles(cliente, opcion, parada) -> tuple:
    """Pares (nombre, clase) visibles según la opción a capturar."""
    escena = _datos(cliente, "GetCurrentProgramScene",
                    parada=parada).get("currentProgramSceneName", "") or ""
    por_clase = {
        entrada.get("inputName", ""): entrada.get("inputKind", "")
        for entrada in _datos(cliente, "GetInputList",
                              parada=parada).get("inputs", ()) or ()
        if entrada.get("inputName", "")}
    elementos = _datos(cliente, "GetSceneItemList", {"sceneName": escena},
                       parada).get("sceneItems", ()) or ()
    if opcion.fuente != escena:
        return [(opcion.fuente, por_clase.get(opcion.fuente, "") or "")]
    return [(elemento.get("sourceName", "") or "",
             por_clase.get(elemento.get("sourceName", "") or "", "") or "")
            for elemento in elementos
            if elemento.get("sourceName", "")
            and elemento.get("sceneItemEnabled", True)]


def _ajustes_capturas(cliente, pares, parada) -> dict:
    """Ajustes de cada fuente de captura, pedidos uno por uno."""
    ajustes = {}
    for (nombre, clase) in pares:
        if clase in TIPOS_CAPTURA:
            ajustes[nombre] = _datos(
                cliente, "GetInputSettings",
                {"inputName": nombre}, parada).get(
                    "inputSettings", {}) or {}
    return ajustes


def _averiguar_motivo(cliente, opcion, parada) -> tuple:
    """Causa probable de la captura negra.

    Si la averiguación falla, devuelve motivo vacío con un aviso,
    igual que `_medir`.
    """
    try:
        pares = _pares_visibles(cliente, opcion, parada)
        ajustes = _ajustes_capturas(cliente, pares, parada)
    except Exception as error:
        logger.warning("obs_captura_ia: no se pudo averiguar la causa de "
                       "la captura negra de %r: %s", opcion.fuente, error)
        return ("", "")
    return motivo_negra(pares, ajustes)


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
    negra = _medir(cliente, opcion, parada)
    motivo = ""
    fuente_motivo = ""
    if negra is True:
        (motivo, fuente_motivo) = _averiguar_motivo(cliente, opcion, parada)
    return Captura(jpeg, ancho, alto, negra, motivo, fuente_motivo)


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
