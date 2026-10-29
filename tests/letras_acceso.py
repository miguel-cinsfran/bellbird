"""Letras de acceso repetidas dentro de una página o un cuadro.

`letras_repetidas` recorre los hijos del contenedor de forma recursiva,
salvo los que son un `wx.Notebook` o un `wx.Listbook` o una página de
ellos, que tienen su propio ámbito y se miran aparte. Junta la letra
que sigue al primer `&` de cada rótulo (ignorando `&&`) y devuelve
solo las letras que aparecen más de una vez, en minúscula, con los
rótulos que las usan.
"""

import wx

_TIPOS_CON_ROTULO = (wx.StaticText, wx.Button, wx.CheckBox, wx.RadioButton,
                     wx.StaticBox)


def _letra_de_acceso(rotulo):
    """La letra tras el primer `&` simple, en minúscula, o nada."""
    indice = 0
    while indice < len(rotulo):
        if rotulo[indice] == "&":
            siguiente = rotulo[indice + 1] if indice + 1 < len(rotulo) else ""
            if siguiente == "&":
                indice += 2
                continue
            return siguiente.lower() if siguiente else None
        indice += 1
    return None


def _con_ambito_propio(ventana):
    """Si la ventana es un libro o una página de un libro."""
    if isinstance(ventana, (wx.Notebook, wx.Listbook)):
        return True
    return isinstance(ventana.GetParent(), (wx.Notebook, wx.Listbook))


def letras_repetidas(contenedor):
    """Letras de acceso repetidas bajo `contenedor`, con sus rótulos."""
    por_letra = {}
    pendientes = list(reversed(contenedor.GetChildren()))
    while pendientes:
        actual = pendientes.pop()
        if _con_ambito_propio(actual):
            continue
        if isinstance(actual, _TIPOS_CON_ROTULO):
            rotulo = actual.GetLabel() or ""
            letra = _letra_de_acceso(rotulo)
            if letra:
                por_letra.setdefault(letra, []).append(rotulo)
        pendientes.extend(reversed(actual.GetChildren()))
    return {letra: rotulos for letra, rotulos in por_letra.items()
            if len(rotulos) > 1}
