"""Lleva un diseño calculado de `disenos_escena` a una escena de OBS."""

from __future__ import annotations

from guyrapu.obs import chat_en_video
from guyrapu.obs import disenos_escena
from guyrapu.obs import overlay_servidor
from guyrapu.obs.fuente_chat import NOMBRE_FUENTE

_TIPO_CAMARA = "dshow_input"
_TIPOS_CAPTURA = ("game_capture", "monitor_capture", "window_capture")
_TIPOS_AUDIO = ("wasapi_input_capture", "wasapi_output_capture",
                "wasapi_process_output_capture")
_ORDEN_TIPOS = {"captura": 0, "otra": 1, "camara": 2, "chat": 3}


def fuentes_de_escena(gestor, escena):
    """Las fuentes de la escena sin las de solo audio, en orden de prioridad.

    Primero las capturas, después las demás, la cámara y el chat. Dentro de
    cada grupo van las visibles antes que las ocultas y, entre iguales, el
    orden de OBS, de abajo hacia arriba.
    """
    fuentes, _nombres = _leer(gestor, escena)
    return fuentes


def _leer(gestor, escena):
    elementos = [
        elemento for elemento in gestor.elementos(escena)
        if elemento.get("inputKind") not in _TIPOS_AUDIO]
    pares = [(_fuente(elemento),
              elemento.get("sceneItemEnabled", True))
             for elemento in elementos]
    pares.sort(key=lambda par: (
        _ORDEN_TIPOS[par[0].tipo], 0 if par[1] else 1))
    return ([fuente for fuente, _visible in pares],
            [elemento.get("sourceName", "") for elemento in elementos
             if elemento.get("sceneItemEnabled", True)])


def _fuente(elemento):
    return disenos_escena.Fuente(
        nombre=elemento.get("sourceName", ""),
        tipo=_tipo(elemento),
        ancho=elemento.get("sceneItemTransform", {}).get("sourceWidth", 0) or 0,
        alto=elemento.get("sceneItemTransform", {}).get("sourceHeight", 0) or 0)


def _tipo(elemento):
    if elemento.get("sourceName") == NOMBRE_FUENTE:
        return "chat"
    clase = elemento.get("inputKind")
    if clase in _TIPOS_CAPTURA:
        return "captura"
    if clase == _TIPO_CAMARA:
        return "camara"
    return "otra"


def aplicar_diseno(gestor, registro, escena, diseno):
    """Calcula el diseño con el lienzo de la escena y lo aplica.

    Devuelve los estados de las fuentes colocadas y los nombres de las que
    quedaron como estaban, en el orden de OBS.
    """
    fuentes, orden_obs = _leer_con_chat(gestor, escena, diseno)
    if not fuentes:
        raise ValueError("La escena no tiene fuentes")
    lienzo = gestor.instantanea(escena, fuente=fuentes[0].nombre)
    colocaciones = disenos_escena.calcular(
        lienzo.lienzo_ancho, lienzo.lienzo_alto, fuentes, diseno)
    estados = aplicar(gestor, registro, escena, colocaciones)
    colocadas = {colocacion["nombre"] for colocacion in colocaciones}
    return estados, [nombre for nombre in orden_obs if nombre not in colocadas]


def _leer_con_chat(gestor, escena, diseno):
    """Las fuentes de la escena, agregando la del chat si el diseño la pide."""
    fuentes, orden_obs = _leer(gestor, escena)
    if diseno.chat != "ninguno" and not any(
            fuente.tipo == "chat" for fuente in fuentes):
        puerto = (overlay_servidor.puerto_actual()
                  or chat_en_video.PUERTO_DEFECTO)
        chat_en_video.agregar_fuente(gestor, escena, puerto)
        fuentes, orden_obs = _leer(gestor, escena)
    return fuentes, orden_obs


def aplicar(gestor, registro, escena, colocaciones):
    """Aplica el diseño a la escena y devuelve el estado de cada fuente."""
    for colocacion in colocaciones:
        registro.guardar(gestor, escena, colocacion["nombre"])
    for colocacion in colocaciones:
        _aplicar_colocacion(gestor, escena, colocacion)
    for colocacion in reversed(colocaciones):
        gestor.al_frente(escena, fuente=colocacion["nombre"])
    return [(colocacion["nombre"],
             "" if _es_chat(colocacion) else colocacion["estado"])
            for colocacion in colocaciones]


def _es_chat(colocacion):
    return colocacion["nombre"] == NOMBRE_FUENTE


def _aplicar_colocacion(gestor, escena, colocacion):
    if _es_chat(colocacion):
        if "ancho" in colocacion:
            gestor.redimensionar(escena, colocacion["ancho"],
                                 colocacion["alto"])
        gestor.posicionar(escena, colocacion["positionX"],
                          colocacion["positionY"],
                          colocacion["alignment"],
                          fuente=colocacion["nombre"])
        return
    gestor.transformar(
        escena,
        {clave: valor for clave, valor in colocacion.items()
         if clave not in ("nombre", "estado")},
        fuente=colocacion["nombre"])
