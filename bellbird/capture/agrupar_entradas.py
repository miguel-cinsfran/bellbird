"""Agrupador de entradas al directo de TikTok (lógica pura, sin wx).

Las entradas llegan de a una: se juntan las personas distintas que entran
durante una ventana y sale una sola fila cuando termina. La clave es el id
del canal, y si no hay, el nombre.
"""

from __future__ import annotations

from bellbird.core.idioma import _


class AgrupadorEntradas:
    """Junta personas distintas desde la primera entrada de la ventana."""

    def __init__(self, ventana: float = 10.0):
        self.ventana = ventana
        # Clave -> [autor, canal_id]. El dict conserva el orden de llegada.
        self._personas: dict[str, list] = {}
        self._primero: float | None = None

    def _segundos(self) -> float:
        """Segundos de la ventana vigentes ahora. `ventana` puede ser un
        número o una función sin argumentos, para que un cambio de
        configuración valga sin reconectar."""
        return float(self.ventana() if callable(self.ventana) else self.ventana)

    def sumar(self, autor: str, canal_id: str, ahora: float) -> None:
        """Anota a la persona si todavía no estaba en el grupo."""
        clave = canal_id if canal_id else autor
        if not self._personas:
            self._primero = ahora
        persona = self._personas.get(clave)
        if persona is None:
            self._personas[clave] = [autor, canal_id]
        else:
            persona[0] = autor

    def vencido(self, ahora: float) -> list[tuple[str, str]]:
        """Saca y devuelve las personas del grupo si pasó la ventana.

        Vuelve vacío mientras no se cumpla, y deja el agrupador listo para
        empezar otro grupo.
        """
        if not self._personas:
            return []
        if ahora - self._primero < self._segundos():
            return []
        personas = [tuple(persona) for persona in self._personas.values()]
        self._personas.clear()
        self._primero = None
        return personas


def nombres_del_grupo(autores) -> str:
    """Nombra hasta tres personas y resume las demás como «y N más»."""
    nombres = list(autores)
    if not nombres:
        return ""
    if len(nombres) == 1:
        return nombres[0]
    if len(nombres) == 2:
        return _("{a} y {b}").format(a=nombres[0], b=nombres[1])
    if len(nombres) == 3:
        return _("{a}, {b} y {c}").format(
            a=nombres[0], b=nombres[1], c=nombres[2])
    return _("{a}, {b}, {c} y {n} más").format(
        a=nombres[0], b=nombres[1], c=nombres[2],
        n=len(nombres) - 3)
