"""Pruebas de la búsqueda de ítems de menú de la sonda, sin ventanas.

Se importa `qa/sonda.py` por ruta, como `tests/test_qa_conducir.py` hace
con el suyo: importarla no arranca nada ni abre ventanas. La barra y sus
ítems son falsos con la misma forma que `wx` expone.
"""

import importlib.util
import unittest
from pathlib import Path

_RUTA = Path(__file__).resolve().parent.parent / "qa" / "sonda.py"
_paquete = importlib.util.spec_from_file_location("sonda_qa", _RUTA)
sonda = importlib.util.module_from_spec(_paquete)
_paquete.loader.exec_module(sonda)


class ItemFalso:
    """Un ítem de menú con etiqueta completa y limpia, como `wx`."""

    def __init__(self, identificador, etiqueta):
        self._id = identificador
        self._etiqueta = etiqueta

    def IsSeparator(self):
        return False

    def GetItemLabelText(self):
        return self._etiqueta.split("\t", 1)[0].replace("&", "")

    def GetItemLabel(self):
        return self._etiqueta

    def IsEnabled(self):
        return True

    def IsCheckable(self):
        return False

    def GetId(self):
        return self._id

    def GetSubMenu(self):
        return None


class MenuFalso:
    def __init__(self, titulo, items):
        self._titulo = titulo
        self._items = items

    def GetMenuItems(self):
        return self._items


class BarraFalsa:
    """Una barra con el menú Voz antes que el Música, como en la app."""

    def __init__(self, menues):
        self._menues = menues

    def GetMenuCount(self):
        return len(self._menues)

    def GetMenuLabelText(self, indice):
        return self._menues[indice]._titulo

    def IsEnabledTop(self, indice):
        return True

    def GetMenu(self, indice):
        return self._menues[indice]


def _barra_volumenes():
    return BarraFalsa([
        MenuFalso("Voz", [ItemFalso(11, "&Subir volumen de la voz"),
                          ItemFalso(12, "&Bajar volumen de la voz")]),
        MenuFalso("Música", [ItemFalso(21, "Subir &volumen"),
                             ItemFalso(22, "&Bajar volumen")]),
    ])


def _barra_repetida():
    return BarraFalsa([
        MenuFalso("Reproductor", [ItemFalso(11, "&Reproducir o pausar")]),
        MenuFalso("Música", [ItemFalso(21, "Reproducir o &pausar")]),
    ])


class BuscarItemMenuTest(unittest.TestCase):

    def test_ruta_elige_el_menu_pedido(self):
        self.assertEqual(
            sonda._buscar_item_menu(_barra_repetida(),
                                    "música > reproducir o pausar"),
            (21, "Reproducir o pausar"))

    def test_sin_ruta_elige_el_primero_como_hoy(self):
        self.assertEqual(
            sonda._buscar_item_menu(_barra_repetida(),
                                    "reproducir o pausar"),
            (11, "Reproducir o pausar"))

    def test_prefiere_la_etiqueta_exacta_antes_que_la_que_contiene(self):
        self.assertEqual(
            sonda._buscar_item_menu(_barra_volumenes(), "subir volumen"),
            (21, "Subir volumen"))

    def test_sin_exacta_cae_a_la_primera_que_contiene(self):
        self.assertEqual(
            sonda._buscar_item_menu(_barra_volumenes(), "volumen de la voz"),
            (11, "Subir volumen de la voz"))

    def test_sin_coincidencia_devuelve_none(self):
        self.assertIsNone(
            sonda._buscar_item_menu(_barra_volumenes(), "silenciar todo"))


if __name__ == "__main__":
    unittest.main()
