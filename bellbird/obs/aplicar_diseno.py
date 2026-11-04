"""Lleva un diseño calculado de `disenos_escena` a una escena de OBS."""

from __future__ import annotations

from bellbird.obs import disenos_escena
from bellbird.obs.fuente_chat import NOMBRE_FUENTE

_TIPO_CAMARA = "dshow_input"


def fuentes_de_escena(gestor, escena):
    """Las fuentes de la escena con el tipo y el tamaño de origen."""
    return [
        disenos_escena.Fuente(
            nombre=elemento.get("sourceName", ""),
            tipo=_tipo(elemento),
            ancho=elemento.get("sceneItemTransform", {}).get("sourceWidth", 0) or 0,
            alto=elemento.get("sceneItemTransform", {}).get("sourceHeight", 0) or 0)
        for elemento in gestor.elementos(escena)]


def _tipo(elemento):
    if elemento.get("sourceName") == NOMBRE_FUENTE:
        return "chat"
    if elemento.get("inputKind") == _TIPO_CAMARA:
        return "camara"
    return "otra"


def aplicar_diseno(gestor, registro, escena, diseno):
    """Calcula el diseño con el lienzo de la escena y lo aplica."""
    fuentes = fuentes_de_escena(gestor, escena)
    if not fuentes:
        raise ValueError("La escena no tiene fuentes")
    lienzo = gestor.instantanea(escena, fuente=fuentes[0].nombre)
    colocaciones = disenos_escena.calcular(
        lienzo.lienzo_ancho, lienzo.lienzo_alto, fuentes, diseno)
    return aplicar(gestor, registro, escena, colocaciones)


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
