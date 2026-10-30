"""Letras de acceso repetidas dentro de una página o un cuadro.

`letras_repetidas` recorre los hijos del contenedor de forma recursiva,
salvo los que son un `wx.Notebook` o un `wx.Listbook` o una página de
ellos, que tienen su propio ámbito y se miran aparte. Junta la letra
que sigue al primer `&` de cada rótulo (ignorando `&&`) y devuelve
solo las letras que aparecen más de una vez, en minúscula, con los
rótulos que las usan.
"""

import wx

import shutil
import tempfile
from pathlib import Path

from scripts import traducciones
from bellbird.core import idioma

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


def letras_de_contenedor(contenedor):
    """Todas las letras de acceso bajo `contenedor`, con sus rótulos.

    Mismo recorrido que `letras_repetidas`: lo que tiene ámbito propio
    (un libro o una página de un libro) se mira aparte y aquí no entra.
    """
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
    return por_letra


def letras_repetidas(contenedor):
    """Letras de acceso repetidas bajo `contenedor`, con sus rótulos."""
    por_letra = letras_de_contenedor(contenedor)
    return {letra: rotulos for letra, rotulos in por_letra.items()
            if len(rotulos) > 1}


class ingles:
    """El catálogo inglés del repositorio, instalado y después retirado.

    Compila el `.po` inglés a una carpeta temporal con
    `scripts/traducciones.py` y lo instala con `idioma.instalar("en",
    carpeta)`. Al salir deja el español con `idioma._reiniciar()`.
    Sirve como gestor de contexto o desde `setUpClass` y
    `tearDownClass`::

        with ingles():
            ...

        @classmethod
        def setUpClass(cls):
            cls._ingles = ingles()
            cls._ingles.__enter__()

        @classmethod
        def tearDownClass(cls):
            cls._ingles.__exit__(None, None, None)
    """

    def __init__(self):
        self._temporal = None

    def __enter__(self):
        self._temporal = tempfile.TemporaryDirectory()
        carpeta = Path(self._temporal.name)
        destino = traducciones.ruta_po(carpeta, "en")
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(traducciones.ruta_po(
            traducciones.CARPETA_IDIOMAS, "en"), destino)
        traducciones.compilar(carpeta_idiomas=carpeta)
        idioma.instalar("en", carpeta)
        return self

    def __exit__(self, *exc):
        try:
            idioma._reiniciar()
        finally:
            if self._temporal is not None:
                self._temporal.cleanup()
                self._temporal = None
        return False
