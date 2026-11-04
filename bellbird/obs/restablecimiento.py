"""Registro de lo que hay que restablecer en OBS."""

from __future__ import annotations

from bellbird.obs.obs_panel import NOMBRE_FUENTE


CLAVES_TRANSFORMACION = (
    "positionX", "positionY", "alignment", "rotation", "scaleX", "scaleY",
    "boundsType", "boundsAlignment", "boundsWidth", "boundsHeight",
    "cropLeft", "cropRight", "cropTop", "cropBottom")

_CLAVES_CUADRO = ("boundsAlignment", "boundsWidth", "boundsHeight")


class RegistroRestablecimiento:
    """Guarda una instantánea por pareja de escena y fuente y la reaplica."""

    def __init__(self):
        self._datos = {}

    def guardar(self, gestor, escena, fuente) -> None:
        clave = escena, fuente
        if not fuente or clave in self._datos:
            return
        self._datos[clave] = _instantanea(gestor, escena, fuente)

    def aplicar(self, gestor) -> None:
        for (escena, fuente), datos in self._datos.items():
            self._restaurar_forma(gestor, escena, fuente, datos)
        capas = sorted(
            (datos["capa"], escena, fuente)
            for (escena, fuente), datos in self._datos.items()
            if datos["capa"] is not None)
        for capa, escena, fuente in capas:
            gestor.mover_capa(escena, capa, fuente=fuente)

    def _restaurar_forma(self, gestor, escena, fuente, datos) -> None:
        _restaurar_transformacion(gestor, escena, fuente, datos)
        if fuente == NOMBRE_FUENTE:
            gestor.redimensionar(escena, datos["ancho"], datos["alto"])
        elif not datos["completa"]:
            gestor.escalar(escena, datos["ancho"], datos["alto"], fuente=fuente)
        gestor.mostrar(escena, datos["visible"], fuente=fuente)
        gestor.fijar(escena, datos["bloqueada"], fuente=fuente)


def _instantanea(gestor, escena, fuente):
    snap = gestor.instantanea(escena, fuente=fuente)
    fuentes = gestor.fuentes(escena)
    capa = (len(fuentes) - 1 - fuentes.index(fuente)
            if fuente in fuentes else None)
    completa = _transformacion_completa(gestor, escena, fuente)
    return {
        "transformacion": (gestor.transformacion(escena, fuente=fuente)
                           if completa is None else completa),
        "completa": completa is not None,
        "ancho": snap.ancho, "alto": snap.alto, "visible": snap.visible,
        "bloqueada": snap.bloqueada, "capa": capa,
    }


def _restaurar_transformacion(gestor, escena, fuente, datos) -> None:
    transformacion = datos["transformacion"]
    if not transformacion:
        return
    if datos["completa"]:
        gestor.transformar(escena, transformacion, fuente=fuente)
        return
    gestor.posicionar(escena, transformacion["positionX"],
                      transformacion["positionY"],
                      transformacion["alignment"], fuente=fuente)


def _transformacion_completa(gestor, escena, fuente):
    elemento = next((elemento for elemento in gestor.elementos(escena)
                     if elemento.get("sourceName") == fuente), None)
    if elemento is None:
        return None
    transformacion = elemento.get("sceneItemTransform", {})
    completa = {clave: transformacion[clave] for clave in CLAVES_TRANSFORMACION
                if clave in transformacion}
    if _sin_cuadro(completa):
        for clave in _CLAVES_CUADRO:
            completa.pop(clave, None)
    return completa


def _sin_cuadro(transformacion):
    return (transformacion.get("boundsType") == "OBS_BOUNDS_NONE"
            or not transformacion.get("boundsWidth")
            or not transformacion.get("boundsHeight"))
