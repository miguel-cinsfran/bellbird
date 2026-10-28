"""Ayudante para comprobar que una ventana no deja textos sin traducir.

`con_pseudo` instala la pseudotraducción, que marca cada texto que pasa por
`_` con `[¡texto!]`, y al salir deja el idioma sin resolver, aunque la prueba
falle. `textos_sin_marcar` recorre una ventana ya construida y devuelve los
textos visibles que no salieron marcados.
"""

from contextlib import contextmanager

import wx

from ytchat.core import idioma


@contextmanager
def con_pseudo():
    idioma.instalar(idioma.IDIOMA_PSEUDO)
    try:
        yield
    finally:
        idioma._reiniciar()


_CON_ROTULO = (wx.StaticText, wx.Button, wx.CheckBox, wx.RadioButton,
                 wx.ToggleButton, wx.StaticBox)


def _opciones(ventana):
    if isinstance(ventana, (wx.RadioBox, wx.Choice, wx.ComboBox)):
        try:
            return ventana.GetStrings()
        except Exception:
            return []
    return []


def textos_sin_marcar(ventana, propios=()):
    """Textos visibles de la ventana y sus hijos que no llevan la marca."""
    propios = set(propios)
    sin_marcar = []
    pendientes = [ventana]
    while pendientes:
        actual = pendientes.pop()
        textos = []
        if isinstance(actual, wx.TopLevelWindow):
            textos.append(actual.GetTitle())
        if isinstance(actual, wx.Notebook):
            textos.extend(actual.GetPageText(i)
                          for i in range(actual.GetPageCount()))
        if isinstance(actual, _CON_ROTULO):
            # Solo estos controles muestran un rótulo: en el resto, como un
            # Panel sin etiqueta, GetLabel() devuelve el nombre interno.
            etiqueta = actual.GetLabel()
            if etiqueta:
                textos.append(etiqueta)
        textos.extend(_opciones(actual))
        for texto in textos:
            if not texto or texto in propios or texto.startswith("[¡"):
                continue
            sin_marcar.append(texto)
        pendientes.extend(actual.GetChildren())
    return sin_marcar
