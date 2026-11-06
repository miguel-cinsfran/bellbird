"""Pruebas de los textos y nombres de escena, sin interfaz ni OBS."""

import unittest

from guyrapu.obs import nombres_escena


class TestTextoDeFila(unittest.TestCase):

    def test_sin_fuentes(self):
        self.assertEqual(
            nombres_escena.texto_de_fila("Vacía", 0), "Vacía, sin fuentes")

    def test_una_fuente(self):
        self.assertEqual(
            nombres_escena.texto_de_fila("Charla", 1), "Charla, 1 fuente")

    def test_tres_fuentes_y_es_la_actual(self):
        self.assertEqual(
            nombres_escena.texto_de_fila("Juego", 3, actual=True),
            "Juego, escena actual, 3 fuentes")

    def test_tres_fuentes_y_no_es_la_actual(self):
        self.assertEqual(
            nombres_escena.texto_de_fila("Juego", 3),
            "Juego, 3 fuentes")


class TestNombreLibre(unittest.TestCase):

    def test_sin_ocupados_propone_el_primero(self):
        self.assertEqual(nombres_escena.nombre_libre(set()), "Escena 1")

    def test_con_escena_2_ocupada_propone_la_1(self):
        self.assertEqual(
            nombres_escena.nombre_libre({"Escena 2"}), "Escena 1")

    def test_con_las_dos_primeras_ocupadas_propone_la_3(self):
        self.assertEqual(
            nombres_escena.nombre_libre({"Escena 1", "Escena 2"}),
            "Escena 3")


class TestNombreDeCopia(unittest.TestCase):

    def test_sin_copia_ocupada_usa_el_sufijo(self):
        self.assertEqual(
            nombres_escena.nombre_de_copia("Juego", set()), "Juego - copia")

    def test_con_copia_ocupada_suma_el_numero(self):
        self.assertEqual(
            nombres_escena.nombre_de_copia("Juego", {"Juego - copia"}),
            "Juego - copia 2")

    def test_con_dos_copias_ocupadas_suma_el_siguiente(self):
        self.assertEqual(
            nombres_escena.nombre_de_copia(
                "Juego", {"Juego - copia", "Juego - copia 2"}),
            "Juego - copia 3")


class TestValidarNombre(unittest.TestCase):

    def test_un_nombre_vacio_no_sirve(self):
        self.assertEqual(
            nombres_escena.validar_nombre("  ", set()),
            nombres_escena.NOMBRE_VACIO)

    def test_un_nombre_repetido_no_sirve(self):
        self.assertEqual(
            nombres_escena.validar_nombre("Juego", {"Juego"}),
            nombres_escena.NOMBRE_REPETIDO)

    def test_un_nombre_libre_sirve(self):
        self.assertEqual(
            nombres_escena.validar_nombre("Charla", {"Juego"}), "")

    def test_renombrar_con_el_mismo_nombre_sirve(self):
        self.assertEqual(
            nombres_escena.validar_nombre(
                "Juego", {"Juego"}, excepto="Juego"), "")


if __name__ == "__main__":
    unittest.main()
