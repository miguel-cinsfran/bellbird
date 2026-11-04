"""Tamaño de una fuente medido como parte del vídeo."""

import unittest

from bellbird.obs import tamano_relativo as tamano


class ComunesTest(unittest.TestCase):

    def test_cada_comun_da_su_porcentaje(self):
        esperados = {
            "un_quinto": 20, "un_cuarto": 25, "un_tercio": 33,
            "la_mitad": 50, "dos_tercios": 67, "todo": 100,
        }
        for clave, _nombre, fraccion in tamano.COMUNES:
            with self.subTest(clave=clave):
                self.assertEqual(tamano.comun_de(round(fraccion * 100)), clave)
                self.assertEqual(esperados[clave], round(fraccion * 100))

    def test_comun_de_acepta_un_punto_de_diferencia(self):
        self.assertEqual(tamano.comun_de(19), "un_quinto")
        self.assertEqual(tamano.comun_de(21), "un_quinto")
        self.assertEqual(tamano.comun_de(26), "un_cuarto")
        self.assertEqual(tamano.comun_de(32), "un_tercio")
        self.assertEqual(tamano.comun_de(34), "un_tercio")
        self.assertEqual(tamano.comun_de(68), "dos_tercios")
        self.assertEqual(tamano.comun_de(99), "todo")

    def test_comun_de_rechaza_dos_puntos_de_diferencia(self):
        self.assertIsNone(tamano.comun_de(22))
        self.assertIsNone(tamano.comun_de(28))
        self.assertIsNone(tamano.comun_de(35))
        self.assertIsNone(tamano.comun_de(65))
        self.assertIsNone(tamano.comun_de(98))
        self.assertIsNone(tamano.comun_de(0))


class PorcentajesTest(unittest.TestCase):

    def test_porcentajes_redondea_al_entero(self):
        self.assertEqual(tamano.porcentajes(400, 300, 1600, 900), (25, 33))
        self.assertEqual(tamano.porcentajes(460, 620, 1600, 900), (29, 69))

    def test_sin_lienzo_no_informa(self):
        self.assertEqual(tamano.porcentajes(400, 300, 0, 0), (0, 0))


class PixelesTest(unittest.TestCase):

    def test_proporcion_mantenida_conserva_la_actual(self):
        self.assertEqual(
            tamano.a_pixeles(50, None, 1600, 900, 400, 300), (800, 600))

    def test_alto_propio_usa_el_alto_del_video(self):
        self.assertEqual(
            tamano.a_pixeles(50, 50, 1600, 900, 400, 300), (800, 450))

    def test_tamano_actual_cero_usa_la_proporcion_del_video(self):
        self.assertEqual(
            tamano.a_pixeles(50, None, 1600, 900, 0, 0), (800, 450))

    def test_nunca_devuelve_cero_pixeles(self):
        self.assertEqual(tamano.a_pixeles(5, 5, 10, 10, 0, 0), (1, 1))

    def test_ida_y_vuelta_con_porcentajes_pierde_un_punto_como_mucho(self):
        for porcentaje in (5, 20, 25, 33, 50, 67, 100):
            with self.subTest(porcentaje=porcentaje):
                ancho, alto = tamano.a_pixeles(
                    porcentaje, porcentaje, 1600, 900, 800, 450)
                pancho, palto = tamano.porcentajes(ancho, alto, 1600, 900)
                self.assertLessEqual(abs(pancho - porcentaje), 1)
                self.assertLessEqual(abs(palto - porcentaje), 1)


if __name__ == "__main__":
    unittest.main()
