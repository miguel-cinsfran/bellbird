"""Registro de lo que hay que restablecer en OBS."""

from __future__ import annotations

from bellbird.obs.obs_panel import NOMBRE_FUENTE


class RegistroRestablecimiento:
    """Guarda una instantánea por pareja de escena y fuente y la reaplica."""

    def __init__(self):
        self._datos = {}

    def guardar(self, gestor, escena, fuente) -> None:
        clave = escena, fuente
        if not fuente or clave in self._datos:
            return
        snap = gestor.instantanea(escena, fuente=fuente)
        fuentes = gestor.fuentes(escena)
        capa = (len(fuentes) - 1 - fuentes.index(fuente)
                if fuente in fuentes else None)
        self._datos[clave] = {
            "transformacion": gestor.transformacion(escena, fuente=fuente),
            "ancho": snap.ancho, "alto": snap.alto, "visible": snap.visible,
            "bloqueada": snap.bloqueada, "capa": capa,
        }

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
        transformacion = datos["transformacion"]
        if transformacion:
            gestor.posicionar(escena, transformacion["positionX"],
                              transformacion["positionY"],
                              transformacion["alignment"], fuente=fuente)
        if fuente == NOMBRE_FUENTE:
            gestor.redimensionar(escena, datos["ancho"], datos["alto"])
        else:
            gestor.escalar(escena, datos["ancho"], datos["alto"], fuente=fuente)
        gestor.mostrar(escena, datos["visible"], fuente=fuente)
        gestor.fijar(escena, datos["bloqueada"], fuente=fuente)
