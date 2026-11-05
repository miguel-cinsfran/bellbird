"""Seguimiento y frases de las metas de un directo de TikTok.

Puro y sin wx ni TikTokLive. Única razón para cambiar: cómo se sigue y se
nombra una meta. Las frases son funciones puras; el registro guarda el
estado con un candado porque lo escribe el hilo de la captura y lo lee F2
desde el hilo de la interfaz.
"""

from __future__ import annotations

import threading

from bellbird.core.idioma import _


def frase_cumplida(descripcion: str) -> str:
    """Frase que se lee al cumplirse una meta."""
    descripcion = (descripcion or "").strip()
    if descripcion:
        return _("Meta cumplida: {descripcion}").format(
            descripcion=descripcion)
    return _("Meta cumplida")


def frase_meta(descripcion: str, progreso: int, objetivo: int) -> str:
    """Frase de F2 con el avance de una meta sin cumplir."""
    descripcion = (descripcion or "").strip()
    if descripcion:
        # Traductores: {descripcion} es la meta, {progreso} lo logrado y
        # {objetivo} lo que falta para cumplirla.
        return _("Meta: {descripcion}, {progreso} de {objetivo}").format(
            descripcion=descripcion, progreso=progreso, objetivo=objetivo)
    # Traductores: {progreso} es lo logrado y {objetivo} la meta.
    return _("Meta: {progreso} de {objetivo}").format(
        progreso=progreso, objetivo=objetivo)


def _cumplida(submetas) -> bool:
    """Alguna submeta con objetivo mayor que cero llegó a su objetivo."""
    return any(objetivo > 0 and progreso >= objetivo
               for progreso, objetivo in submetas)


def _primera_sin_cumplir(submetas):
    for progreso, objetivo in submetas:
        if objetivo > 0 and progreso < objetivo:
            return progreso, objetivo
    return None


class RegistroMetas:
    """Metas vistas, con un candado para captura e interfaz."""

    def __init__(self):
        self._candado = threading.Lock()
        self._metas: dict[str, dict] = {}
        self._orden: list[str] = []

    @staticmethod
    def _clave(id_meta) -> str:
        return str(id_meta if id_meta is not None else "").strip()

    def _nueva(self, clave: str) -> dict:
        estado = {"descripcion": "", "submetas": [],
                  "cumplida_anunciada": False}
        self._metas[clave] = estado
        self._orden.append(clave)
        return estado

    def actualizar(self, id_meta, descripcion, submetas) -> bool:
        """Guarda el avance. Verdadero solo la primera vez que se cumple."""
        clave = self._clave(id_meta)
        submetas = [(int(progreso), int(objetivo))
                    for progreso, objetivo in (submetas or [])]
        with self._candado:
            estado = self._metas.get(clave) or self._nueva(clave)
            if (descripcion or "").strip():
                estado["descripcion"] = (descripcion or "").strip()
            estado["submetas"] = submetas
            if clave in self._orden:
                self._orden.remove(clave)
            self._orden.append(clave)
            if not estado["cumplida_anunciada"] and _cumplida(submetas):
                estado["cumplida_anunciada"] = True
                return True
            return False

    def en_curso(self) -> str:
        """Frase de la última meta sin cumplir, o vacío si no hay ninguna."""
        with self._candado:
            for clave in reversed(self._orden):
                estado = self._metas[clave]
                if estado["cumplida_anunciada"]:
                    continue
                submeta = _primera_sin_cumplir(estado["submetas"])
                if submeta is None:
                    continue
                return frase_meta(estado["descripcion"], *submeta)
            return ""

    def reiniciar(self) -> None:
        """Olvida todo, para una conexión nueva del directo."""
        with self._candado:
            self._metas.clear()
            self._orden.clear()


registro = RegistroMetas()
