"""Pruebas de las opciones de salida de audio de la página Música.

Puras, sin wx ni libVLC: cubren las cuatro reglas de `opciones_salida` y la
propiedad general de que la selección siempre es un índice válido.
"""

import unittest

from tests.pseudo_prueba import con_pseudo
from bellbird.ui.opciones_musica import ETIQUETA_PREDETERMINADA, opciones_salida


class TestOpcionesSalida(unittest.TestCase):
    def test_sin_nada_solo_la_predeterminada(self):
        etiquetas, identificadores, seleccion = opciones_salida("", "", [])
        self.assertEqual(etiquetas, ["Salida predeterminada"])
        self.assertEqual(identificadores, [""])
        self.assertEqual(seleccion, 0)

    def test_lista_las_encontradas_despues_de_la_predeterminada(self):
        etiquetas, identificadores, seleccion = opciones_salida(
            "", "", [("altavoces", "Altavoces"), ("auriculares", "Auriculares")])
        self.assertEqual(etiquetas,
                         ["Salida predeterminada", "Altavoces", "Auriculares"])
        self.assertEqual(identificadores, ["", "altavoces", "auriculares"])
        self.assertEqual(seleccion, 0)

    def test_salta_el_id_vacio_que_lista_libvlc_para_el_predeterminado(self):
        etiquetas, identificadores, _ = opciones_salida(
            "", "", [("", "Predeterminado"), ("altavoces", "Altavoces")])
        self.assertEqual(etiquetas, ["Salida predeterminada", "Altavoces"])
        self.assertEqual(identificadores, ["", "altavoces"])

    def test_salta_los_identificadores_repetidos(self):
        etiquetas, identificadores, _ = opciones_salida(
            "", "", [("altavoces", "Altavoces"), ("altavoces", "Altavoces")])
        self.assertEqual(etiquetas, ["Salida predeterminada", "Altavoces"])
        self.assertEqual(identificadores, ["", "altavoces"])

    def test_la_guardada_ausente_se_agrega_con_su_nombre(self):
        etiquetas, identificadores, seleccion = opciones_salida(
            "vieja", "Salida vieja", [("altavoces", "Altavoces")])
        self.assertEqual(etiquetas,
                         ["Salida predeterminada", "Altavoces", "Salida vieja"])
        self.assertEqual(identificadores, ["", "altavoces", "vieja"])
        self.assertEqual(seleccion, 2)

    def test_la_guardada_ausente_sin_nombre_usa_el_id(self):
        etiquetas, identificadores, seleccion = opciones_salida(
            "vieja", "", [("altavoces", "Altavoces")])
        self.assertEqual(etiquetas[-1], "vieja")
        self.assertEqual(identificadores[-1], "vieja")
        self.assertEqual(seleccion, len(etiquetas) - 1)

    def test_la_guardada_presente_no_se_duplica_y_queda_seleccionada(self):
        etiquetas, identificadores, seleccion = opciones_salida(
            "auriculares", "Auriculares viejos",
            [("altavoces", "Altavoces"), ("auriculares", "Auriculares")])
        self.assertEqual(etiquetas.count("Auriculares"), 1)
        self.assertEqual(identificadores, ["", "altavoces", "auriculares"])
        self.assertEqual(seleccion, 2)

    def test_sin_guardada_la_seleccion_es_la_predeterminada(self):
        _, _, seleccion = opciones_salida(
            "", "Nombre huérfano", [("altavoces", "Altavoces")])
        self.assertEqual(seleccion, 0)

    def test_predeterminada_sale_marcada(self):
        with con_pseudo():
            etiquetas, _, _ = opciones_salida("", "", [])
        self.assertTrue(etiquetas[0].startswith("[¡"), etiquetas[0])

    def test_la_seleccion_siempre_es_un_indice_valido(self):
        casos = [
            ("", "", []),
            ("", "", [("", "Predeterminado")]),
            ("altavoces", "Altavoces", [("altavoces", "Altavoces")]),
            ("vieja", "", []),
            ("vieja", "Salida vieja",
             [("", "X"), ("a", "A"), ("a", "A"), ("b", "")]),
        ]
        for guardada_id, guardada_nombre, encontradas in casos:
            with self.subTest(guardada=guardada_id, encontradas=encontradas):
                etiquetas, identificadores, seleccion = opciones_salida(
                    guardada_id, guardada_nombre, encontradas)
                self.assertEqual(len(etiquetas), len(identificadores))
                self.assertGreaterEqual(seleccion, 0)
                self.assertLess(seleccion, len(etiquetas))
                self.assertEqual(etiquetas[0], ETIQUETA_PREDETERMINADA)
                self.assertEqual(etiquetas[0], "Salida predeterminada")
                self.assertEqual(identificadores[0], "")


if __name__ == "__main__":
    unittest.main()
