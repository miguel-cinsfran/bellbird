"""Seguimiento y frases de las batallas de un directo de TikTok.

Puro y sin wx ni TikTokLive. Única razón para cambiar: cómo se sigue y se
nombra una batalla. Las frases son funciones puras; el registro guarda el
estado con un candado porque lo escribe el hilo de la captura y lo lee F2
desde el hilo de la interfaz.
"""

from __future__ import annotations

import threading

from guyrapu.core.idioma import _, ngettext


def _unir(textos: list[str]) -> str:
    """Lista con comas y «y» final, en formatos completos traducibles."""
    if not textos:
        return ""
    if len(textos) == 1:
        return textos[0]
    if len(textos) == 2:
        return _("{a} y {b}").format(a=textos[0], b=textos[1])
    return _("{primeros} y {ultimo}").format(
        primeros=", ".join(textos[:-1]), ultimo=textos[-1])


def _puntos(cantidad: int) -> str:
    return ngettext("{n} punto", "{n} puntos", cantidad).format(n=cantidad)


def frase_inicio(anfitriones) -> str:
    """Frase que se lee al empezar una batalla."""
    apodos = [apodo for _ident, apodo in anfitriones]
    if not apodos:
        return _("Batalla")
    if len(apodos) == 1:
        return _("Batalla: {nombre}").format(nombre=apodos[0])
    if len(apodos) == 2:
        # Traductores: {primero} y {segundo} son los dos anfitriones.
        return _("Batalla: {primero} contra {segundo}").format(
            primero=apodos[0], segundo=apodos[1])
    # Traductores: {nombres} es la lista de anfitriones.
    return _("Batalla: {nombres}").format(nombres=_unir(apodos))


def frase_fin(anfitriones, puntajes) -> str:
    """Frase que se lee al terminar una batalla, sin decir quién ganó."""
    if not anfitriones or not puntajes:
        return _("Batalla terminada")
    partes = []
    for ident, apodo in anfitriones:
        cantidad = int(puntajes.get(str(ident), 0))
        # Traductores: {nombre} es el anfitrión y {puntos} su puntaje.
        partes.append(_("{nombre} con {puntos}").format(
            nombre=apodo, puntos=_puntos(cantidad)))
    # Traductores: {lista} son los anfitriones con sus puntajes.
    return _("Batalla terminada: {lista}").format(lista=", ".join(partes))


def frase_en_curso(anfitriones, puntajes) -> str:
    """Frase de F2 con los puntajes de la batalla en curso."""
    if not anfitriones:
        return ""
    partes = []
    for ident, apodo in anfitriones:
        cantidad = int(puntajes.get(str(ident), 0))
        # Traductores: {nombre} es el anfitrión y {puntos} su puntaje.
        partes.append(_("{nombre} {puntos}").format(
            nombre=apodo, puntos=_puntos(cantidad)))
    # Traductores: {lista} son los anfitriones con sus puntajes.
    return _("Batalla en curso: {lista}").format(lista=", ".join(partes))


def _anfitriones_normalizados(anfitriones):
    return [(str(ident), str(apodo)) for ident, apodo in (anfitriones or [])]


def _puntajes_normalizados(puntajes):
    return {str(ident): int(cantidad)
            for ident, cantidad in (puntajes or {}).items()}


class RegistroBatallas:
    """Batallas vistas, con un candado para captura e interfaz."""

    def __init__(self):
        self._candado = threading.Lock()
        self._batallas: dict[str, dict] = {}
        self._orden: list[str] = []

    @staticmethod
    def _clave(id_batalla) -> str:
        return str(id_batalla if id_batalla is not None else "").strip()

    def _nueva(self, clave: str) -> dict:
        estado = {"anfitriones": [], "puntajes": {},
                  "inicio_anunciado": False, "fin_anunciado": False}
        self._batallas[clave] = estado
        self._orden.append(clave)
        return estado

    def _mover_al_final(self, clave: str) -> None:
        if clave in self._orden:
            self._orden.remove(clave)
        self._orden.append(clave)

    def abrir(self, id_batalla, anfitriones, puntajes=None) -> bool:
        """Guarda el comienzo. Verdadero solo la primera vez que se anuncia."""
        clave = self._clave(id_batalla)
        with self._candado:
            estado = self._batallas.get(clave) or self._nueva(clave)
            self._mover_al_final(clave)
            anfitriones = _anfitriones_normalizados(anfitriones)
            if anfitriones:
                estado["anfitriones"] = anfitriones
            if puntajes:
                estado["puntajes"] = _puntajes_normalizados(puntajes)
            if estado["inicio_anunciado"]:
                return False
            estado["inicio_anunciado"] = True
            return True

    def actualizar_puntajes(self, id_batalla, puntajes) -> None:
        """Actualiza los puntajes sin anunciar nada."""
        clave = self._clave(id_batalla)
        with self._candado:
            estado = self._batallas.get(clave) or self._nueva(clave)
            estado["puntajes"].update(_puntajes_normalizados(puntajes))

    def cerrar(self, id_batalla, anfitriones, puntajes) -> bool:
        """Guarda el fin. Verdadero solo la primera vez que se anuncia."""
        clave = self._clave(id_batalla)
        with self._candado:
            estado = self._batallas.get(clave) or self._nueva(clave)
            self._mover_al_final(clave)
            anfitriones = _anfitriones_normalizados(anfitriones)
            if anfitriones:
                estado["anfitriones"] = anfitriones
            if puntajes:
                estado["puntajes"] = _puntajes_normalizados(puntajes)
            if estado["fin_anunciado"]:
                return False
            estado["fin_anunciado"] = True
            return True

    def anfitriones_de(self, id_batalla) -> list:
        with self._candado:
            estado = self._batallas.get(self._clave(id_batalla))
            return list(estado["anfitriones"]) if estado else []

    def puntajes_de(self, id_batalla) -> dict:
        with self._candado:
            estado = self._batallas.get(self._clave(id_batalla))
            return dict(estado["puntajes"]) if estado else {}

    def en_curso(self) -> str:
        """Frase de la batalla en curso, o vacío si no hay ninguna."""
        with self._candado:
            for clave in reversed(self._orden):
                estado = self._batallas[clave]
                if (estado["inicio_anunciado"] and not estado["fin_anunciado"]
                        and estado["anfitriones"]):
                    return frase_en_curso(estado["anfitriones"],
                                          estado["puntajes"])
            return ""

    def reiniciar(self) -> None:
        """Olvida todo, para una conexión nueva del directo."""
        with self._candado:
            self._batallas.clear()
            self._orden.clear()


registro = RegistroBatallas()
