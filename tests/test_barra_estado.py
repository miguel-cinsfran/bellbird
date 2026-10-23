"""Pruebas de los anchos de la barra de estado (sin ventanas)."""

import unittest

from ytchat.ui.barra_estado import anchos_barra_estado


def medir(texto):
    return len(texto) * 7


class TestAnchosBarraEstado(unittest.TestCase):

    def test_devuelve_siete_anchos(self):
        self.assertEqual(len(anchos_barra_estado(medir)), 7)

    def test_proporcionales_en_estado_voz_y_total(self):
        anchos = anchos_barra_estado(medir)
        self.assertEqual((anchos[0], anchos[2], anchos[6]), (-3, -3, -2))

    def test_fijos_miden_la_muestra_mas_el_margen(self):
        anchos = anchos_barra_estado(medir)
        muestras = {1: "Voz vel: 100", 3: "Cola: 9999",
                    4: "Leídos: 99999", 5: "Voz vol: 100%"}
        for indice, muestra in muestras.items():
            self.assertEqual(anchos[indice], medir(muestra) + 24)

    def test_ningun_fijo_mas_angosto_que_su_muestra(self):
        anchos = anchos_barra_estado(medir)
        for indice, muestra in ((1, "Voz vel: 100"), (3, "Cola: 9999"),
                                (4, "Leídos: 99999"), (5, "Voz vol: 100%")):
            self.assertGreaterEqual(anchos[indice], medir(muestra))

    def test_usa_la_funcion_medir_recibida(self):
        anchos = anchos_barra_estado(len)
        self.assertEqual(anchos[5], len("Voz vol: 100%") + 24)


if __name__ == "__main__":
    unittest.main()
