"""Pruebas puras de las cuentas del fundido cruzado (`cruce.py`)."""

import math
import unittest

from ytchat.music import cruce
from ytchat.music.bordes import Bordes
from ytchat.music.modelo import Tema


def _amplitud(db):
    return 10.0 ** (db / 20.0)


class TestGanancias(unittest.TestCase):

    def test_extremos_y_medio(self):
        self.assertAlmostEqual(cruce.ganancias_db(0)[0], 0.0, places=6)
        self.assertEqual(cruce.ganancias_db(0)[1], -120.0)
        self.assertEqual(cruce.ganancias_db(1)[0], -120.0)
        self.assertAlmostEqual(cruce.ganancias_db(1)[1], 0.0, places=6)
        sale, entra = cruce.ganancias_db(0.5)
        self.assertAlmostEqual(sale, -3.0, delta=0.1)
        self.assertAlmostEqual(entra, -3.0, delta=0.1)

    def test_el_progreso_se_recorta(self):
        self.assertEqual(cruce.ganancias_db(-1.0), cruce.ganancias_db(0.0))
        self.assertEqual(cruce.ganancias_db(2.0), cruce.ganancias_db(1.0))

    def test_las_amplitudes_suman_uno(self):
        for paso in range(21):
            progreso = paso / 20.0
            sale, entra = cruce.ganancias_db(progreso)
            suma = _amplitud(sale) ** 2 + _amplitud(entra) ** 2
            self.assertAlmostEqual(suma, 1.0, delta=1e-9)


class TestPuntoDeCruce(unittest.TestCase):

    def test_sin_bordes(self):
        self.assertEqual(cruce.punto_de_cruce(10000, None, 6000),
                         (5000, 5000))

    def test_con_bordes_el_fin_es_el_del_sonido(self):
        bordes = Bordes(0, 3000)
        self.assertEqual(cruce.punto_de_cruce(10000, bordes, 6000),
                         (3500, 3500))

    def test_la_duracion_se_recorta_a_la_mitad_del_sonido(self):
        self.assertEqual(cruce.punto_de_cruce(4000, None, 6000),
                         (2000, 2000))

    def test_devuelve_none_sin_material(self):
        self.assertIsNone(cruce.punto_de_cruce(0, None, 6000))
        self.assertIsNone(cruce.punto_de_cruce(-10, None, 6000))
        self.assertIsNone(cruce.punto_de_cruce(10000, None, 0))
        self.assertIsNone(cruce.punto_de_cruce(100, Bordes(0, 100), 50))

    def test_el_inicio_mas_la_duracion_no_pasa_del_fin_del_sonido(self):
        casos = [
            (10000, None, 6000),
            (10000, Bordes(0, 3000), 6000),
            (4000, None, 6000),
            (4000, Bordes(1000, 1000), 6000),
            (3000, Bordes(0, 0), 1000),
        ]
        for largo, bordes, cruce_ms in casos:
            with self.subTest(largo=largo, bordes=bordes, cruce_ms=cruce_ms):
                punto = cruce.punto_de_cruce(largo, bordes, cruce_ms)
                self.assertIsNotNone(punto)
                inicio, duracion = punto
                fin = largo - (bordes.silencio_final_ms if bordes else 0)
                self.assertLessEqual(inicio + duracion, fin)
                self.assertGreaterEqual(inicio, 0)


class TestSaltoInicial(unittest.TestCase):

    def test_sin_bordes_no_salta(self):
        self.assertEqual(cruce.salto_inicial_ms(None), 0)

    def test_bajo_el_minimo_no_salta(self):
        self.assertEqual(cruce.salto_inicial_ms(Bordes(499, 0)), 0)

    def test_sobre_el_minimo_salta(self):
        self.assertEqual(cruce.salto_inicial_ms(Bordes(500, 0)), 500)
        self.assertEqual(cruce.salto_inicial_ms(Bordes(1500, 0)), 1500)


class TestSiguienteLocal(unittest.TestCase):

    def setUp(self):
        self.local = Tema("C:/musica/a.mp3", "A")
        self.local2 = Tema("C:/musica/b.mp3", "B")
        self.enlace = Tema("https://ejemplo/b", "B")
        self.cola = (self.local, self.local2, self.enlace)
        self.orden = [0, 1, 2]

    def test_sin_cursor_no_hay_siguiente(self):
        self.assertFalse(cruce.hay_siguiente_local(
            self.cola, self.orden, None, "no"))
        self.assertFalse(cruce.hay_siguiente_local(
            self.cola, self.orden, None, "tema"))

    def test_repetir_tema(self):
        self.assertTrue(cruce.hay_siguiente_local(
            self.cola, self.orden, 0, "tema"))
        self.assertFalse(cruce.hay_siguiente_local(
            (self.enlace,), [0], 0, "tema"))

    def test_siguiente_local_en_el_orden(self):
        self.assertTrue(cruce.hay_siguiente_local(
            self.cola, self.orden, 0, "no"))
        self.assertFalse(cruce.hay_siguiente_local(
            self.cola, self.orden, 1, "no"))

    def test_al_final_no_hay_siguiente_aunque_repita_todo(self):
        self.assertFalse(cruce.hay_siguiente_local(
            self.cola, self.orden, 2, "no"))
        self.assertFalse(cruce.hay_siguiente_local(
            self.cola, self.orden, 2, "todo"))

    def test_orden_mezclado_usa_el_siguiente_del_orden(self):
        self.assertTrue(cruce.hay_siguiente_local(
            self.cola, [2, 0, 1], 0, "no"))
        self.assertTrue(cruce.hay_siguiente_local(
            self.cola, [2, 0, 1], 1, "no"))
        self.assertFalse(cruce.hay_siguiente_local(
            self.cola, [2, 0, 1], 2, "no"))


class TestConstantes(unittest.TestCase):

    def test_valores(self):
        self.assertEqual(cruce.CRUCE_FABRICA_S, 6)
        self.assertEqual(cruce.CRUCE_MAXIMO_S, 12)
        self.assertEqual(cruce.CRUCE_MANUAL_MS, 500)
        self.assertEqual(cruce.SALTO_MINIMO_MS, 500)


if __name__ == "__main__":
    unittest.main()
