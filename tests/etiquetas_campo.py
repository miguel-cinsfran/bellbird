"""Etiquetas de campo sin los dos puntos finales.

`etiquetas_sin_dos_puntos` recorre los hijos de la ventana en orden de
creación y devuelve cada `wx.StaticText` cuyo siguiente hermano es un
campo y cuyo texto, sin `&`, no termina en dos puntos.
"""

import wx

_TIPOS_CAMPO = (wx.TextCtrl, wx.SpinCtrl, wx.Choice, wx.ComboBox,
                wx.ListBox, wx.ListCtrl)


def _es_campo(control):
    return isinstance(control, _TIPOS_CAMPO)


def etiquetas_sin_dos_puntos(ventana):
    """Etiquetas de campo que no terminan en dos puntos.

    Recorre cada contenedor y mira hermanos seguidos: si un
    `wx.StaticText` tiene justo después un campo, es su etiqueta y
    tiene que terminar en dos puntos.
    """
    faltan = []
    pendientes = [ventana]
    while pendientes:
        actual = pendientes.pop()
        try:
            hijos = list(actual.GetChildren())
        except Exception:
            continue
        for indice, hijo in enumerate(hijos):
            if isinstance(hijo, wx.StaticText):
                siguiente = hijos[indice + 1] if indice + 1 < len(hijos) else None
                if siguiente is not None and _es_campo(siguiente):
                    texto = hijo.GetLabel() or ""
                    sin_marca = texto.replace("&", "")
                    if not sin_marca.rstrip().endswith(":"):
                        faltan.append(texto)
        pendientes.extend(hijos)
    return faltan
