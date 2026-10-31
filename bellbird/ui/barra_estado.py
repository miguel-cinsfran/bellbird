"""Anchos de los campos de la barra de estado (lógica pura, sin wx).

Orden de los 7 campos: 0 estado, 1 velocidad de la voz, 2 voz, 3 cola,
4 leídos, 5 volumen de la voz y 6 total de Super Chats. Los proporcionales
reparten lo que sobra; los fijos se miden con la fuente real más un margen.
"""

_MARGEN = 24

# Campo fijo: índice en la barra y muestra que siempre entra entera.
_FIJOS = (
    (1, "Velocidad: 100"),
    (3, "Cola: 9999"),
    (4, "Leídos: 99999"),
    (5, "Volumen: 100 %"),
    (6, "Super Chats: 999 (US$99999.99)"),
)


def anchos_barra_estado(medir):
    """Lista de 7 anchos para SetStatusWidths; medir(texto) da píxeles."""
    anchos = [-5, 0, -3, 0, 0, 0, 0]
    for indice, muestra in _FIJOS:
        anchos[indice] = medir(muestra) + _MARGEN
    return anchos
