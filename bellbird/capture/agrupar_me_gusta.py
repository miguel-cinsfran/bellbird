"""Agrupador de me gusta de TikTok por persona (lógica pura, sin wx).

Los me gusta llegan de a montones en ráfagas: cada evento trae solo los
toques de ese momento (`count`), así que se juntan por persona durante una
ventana y sale UN aviso con el total. La clave es el id del canal, y si no
hay, el nombre.
"""

from __future__ import annotations


class AgrupadorMeGusta:
    """Junta toques por persona y suelta los grupos ya vencidos."""

    def __init__(self, ventana: float = 10.0):
        self.ventana = float(ventana)
        # Clave -> [autor, canal_id, total, primer_toque]. El dict conserva
        # el orden del primer toque de cada grupo, que es el orden de salida.
        self._grupos: dict[str, list] = {}

    def sumar(self, autor: str, canal_id: str, cantidad, ahora: float) -> None:
        """Acumula los toques de esa persona. Lo que no es un entero
        positivo cuenta como 1 (la librería a veces manda 0 o nada)."""
        if isinstance(cantidad, bool) or not isinstance(cantidad, int):
            toques = 1
        elif cantidad <= 0:
            toques = 1
        else:
            toques = cantidad
        clave = canal_id if canal_id else autor
        grupo = self._grupos.get(clave)
        if grupo is None:
            self._grupos[clave] = [autor, canal_id, toques, ahora]
        else:
            grupo[0] = autor
            grupo[2] += toques

    def vencidos(self, ahora: float) -> list[tuple[str, str, int]]:
        """Saca y devuelve los grupos cuyo primer toque tiene `ventana`
        segundos o más, como (autor, canal_id, total), en el orden de su
        primer toque. El autor es el último nombre que llegó."""
        listos = []
        por_primer_toque = sorted(self._grupos.items(),
                                  key=lambda kv: kv[1][3])
        for clave, (autor, canal_id, total, primero) in por_primer_toque:
            if ahora - primero >= self.ventana:
                listos.append((autor, canal_id, total))
                del self._grupos[clave]
        return listos
