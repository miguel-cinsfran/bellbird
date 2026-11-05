"""El nombre de la pestaña se anuncia desde una sola función, en toda la app."""

import unittest
from pathlib import Path
from unittest import mock

from guyrapu.ui import accesibilidad

RAIZ_UI = Path(accesibilidad.__file__).resolve().parent


class _NotebookFalso:
    def __init__(self, textos):
        self._textos = textos
        self.manejador = None

    def Bind(self, evento, manejador):
        self.manejador = manejador

    def GetPageText(self, indice):
        return self._textos[indice]

    def GetPageCount(self):
        return len(self._textos)


class _EventoFalso:
    def __init__(self, seleccion):
        self._seleccion = seleccion
        self.skip = False

    def GetSelection(self):
        return self._seleccion

    def Skip(self):
        self.skip = True


class AnuncioDePestanaTest(unittest.TestCase):
    def _enlazado(self, textos):
        nb = _NotebookFalso(textos)
        accesibilidad.enlazar_anuncio_de_pestana(nb)
        return nb

    def test_anuncia_el_nombre_de_la_pestana_elegida(self):
        nb = self._enlazado(["Chat del directo", "Comentarios"])
        evento = _EventoFalso(1)
        with mock.patch.object(accesibilidad, "anunciar") as anunciar:
            nb.manejador(evento)
        anunciar.assert_called_once_with("Comentarios")
        self.assertTrue(evento.skip)

    def test_un_indice_fuera_de_rango_no_anuncia(self):
        nb = self._enlazado(["Chat del directo"])
        evento = _EventoFalso(2)
        with mock.patch.object(accesibilidad, "anunciar") as anunciar:
            nb.manejador(evento)
        anunciar.assert_not_called()
        self.assertTrue(evento.skip)


class TodoNotebookAnunciaTest(unittest.TestCase):
    def test_cada_notebook_de_la_interfaz_usa_la_funcion_comun(self):
        sin_anuncio = []
        for ruta in sorted(RAIZ_UI.rglob("*.py")):
            texto = ruta.read_text(encoding="utf-8")
            if ("wx.Notebook(" in texto
                    and "enlazar_anuncio_de_pestana(" not in texto):
                sin_anuncio.append(ruta.name)
        self.assertEqual(sin_anuncio, [])


if __name__ == "__main__":
    unittest.main()
