"""Modelo de la lista de mensajes del chat (lógica pura, sin wx).

Mantiene sincronizados el historial completo (`todos`) y las filas visibles
(`visibles`: índices dentro de `todos`, en el orden en que se muestran), con
recorte al superar el máximo y filtrado por autor/tipo. Aislado aquí para poder
probarlo sin GUI: la desincronización entre estas dos listas hacía que copiar,
silenciar o banear actuaran sobre el mensaje equivocado pasados 500 mensajes.

La GUI (gui.py) es quien toca el wx.ListBox: `agregar` le dice cuántas filas
debe borrar por arriba y si debe añadir la nueva; `reconstruir` le devuelve los
mensajes visibles para repoblarla de cero.
"""

from __future__ import annotations

from dataclasses import dataclass

from ytchat.core.config import (
    TIPO_SUPERCHAT, TIPO_STICKER, TIPO_MIEMBRO, TIPO_ENTRADA,
    TIPO_SEGUIR, TIPO_COMPARTIR, TIPO_COFRE,
)


@dataclass(frozen=True, slots=True)
class MensajeChat:
    """Registro inmutable de una fila del chat con identidad estable."""

    plataforma: str
    autor: str
    identificador: str
    texto: str
    hora: str
    tipo: str
    monto: str
    rol: str = ""


class ListaChat:
    """Historial + filas visibles del chat, con recorte y filtro coherentes."""

    def __init__(self, max_items: int = 500):
        self.max_items = int(max_items)
        # Cada mensaje es un MensajeChat.
        self.todos: list[MensajeChat] = []
        # Índices en `todos` de las filas mostradas, en orden.
        self.visibles: list[int] = []

    def agregar(self, item: MensajeChat, es_visible: bool) -> int:
        """Añade un mensaje al historial (y a las filas si `es_visible`).

        Devuelve cuántas filas debe borrar la GUI POR ARRIBA de su ListBox
        (mensajes viejos recortados que estaban visibles). El recorte quita de
        `todos` y de `visibles` el MISMO mensaje una sola vez, manteniendo la
        correspondencia fila ↔ mensaje.
        """
        borrar_arriba = 0
        while len(self.todos) >= self.max_items:
            self.todos.pop(0)
            if self.visibles and self.visibles[0] == 0:
                self.visibles.pop(0)
                borrar_arriba += 1
            self.visibles = [i - 1 for i in self.visibles]
        idx = len(self.todos)
        self.todos.append(item)
        if es_visible:
            self.visibles.append(idx)
        return borrar_arriba

    def dato_en_fila(self, fila: int) -> MensajeChat | None:
        """Mensaje que corresponde a una fila del ListBox. None si no hay."""
        if 0 <= fila < len(self.visibles):
            idx = self.visibles[fila]
            if 0 <= idx < len(self.todos):
                return self.todos[idx]
        return None

    def reconstruir(self, es_visible) -> list[MensajeChat]:
        """Recalcula `visibles` con el predicado dado y devuelve, en orden, los
        mensajes que la GUI debe volver a pintar (tras un Clear())."""
        self.visibles = [i for i, it in enumerate(self.todos) if es_visible(it)]
        return [self.todos[i] for i in self.visibles]

    def limpiar(self) -> None:
        self.todos.clear()
        self.visibles.clear()


def texto_fila(autor, msg, hora, tipo, monto) -> str:
    """Texto de una fila del chat según su tipo, con los mismos emojis."""
    if tipo == TIPO_SUPERCHAT and monto:
        return f"💲 [{monto}] {autor}: {msg}, {hora}"
    if tipo == TIPO_STICKER and monto:
        return f"🎨 [{monto}] {autor}, {hora}"
    if tipo == TIPO_MIEMBRO:
        return f"⭐ NUEVO MIEMBRO: {autor}, {hora}"
    if tipo == TIPO_ENTRADA:
        return f"👋 {autor} entró, {hora}"
    if tipo == TIPO_SEGUIR:
        return f"{autor} sigue el canal, {hora}"
    if tipo == TIPO_COMPARTIR:
        return f"{autor} compartió el directo, {hora}"
    if tipo == TIPO_COFRE:
        return f"{autor} envió un cofre, {hora}"
    return f"{autor}: {msg}, {hora}"


def texto_reciente(filas, n: int) -> str:
    """Texto de la fila `n` desde el final, tal como se ve en la lista.

    `filas` es la secuencia de textos de las filas en orden y `n` va de 1
    a 10: 1 es la última. Con menos de `n` filas dice cuántas hay.
    """
    total = len(filas)
    if total == 0:
        return "Todavía no hay mensajes en el chat."
    if n > total:
        if total == 1:
            return "El chat tiene 1 mensaje."
        return f"El chat tiene {total} mensajes."
    return filas[total - n]
