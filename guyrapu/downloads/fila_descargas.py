"""Regla de la fila de descargas (lógica pura, sin wx ni hilos)."""


def bloqueado_por_anterior(item_id, orden, empezados, items, eventos) -> bool:
    """Dice si un ítem anterior en la fila, que sigue en cola sin empezar
    y sin cancelar, bloquea a item_id."""
    for previo in orden:
        if previo == item_id:
            return False
        anterior = items.get(previo)
        evento = eventos.get(previo)
        if (previo not in empezados and anterior is not None
                and anterior.estado == "en_cola"
                and not (evento is not None and evento.is_set())):
            return True
    return False
