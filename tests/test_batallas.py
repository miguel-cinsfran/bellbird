"""Frases y registro de las batallas de un directo de TikTok.

Puro y sin wx: las frases de comienzo, fin y batalla en curso, el registro
con candado, el orden de los anfitriones y el anuncio una sola vez por
batalla.
"""

import random
import unittest

from guyrapu.capture import batallas


def _anfitriones(*nombres):
    return [(str(i + 1), nombre) for i, nombre in enumerate(nombres)]


class TestFrases(unittest.TestCase):

    def test_inicio_de_dos(self):
        self.assertEqual(
            batallas.frase_inicio(_anfitriones("Ana", "Fulano")),
            "Batalla: Ana contra Fulano")

    def test_inicio_de_mas_de_dos(self):
        self.assertEqual(
            batallas.frase_inicio(_anfitriones("Ana", "Beto", "Caro")),
            "Batalla: Ana, Beto y Caro")

    def test_fin_con_puntajes(self):
        self.assertEqual(
            batallas.frase_fin(
                _anfitriones("Ana", "Fulano"), {"1": 3200, "2": 2800}),
            "Batalla terminada: Ana con 3200 puntos, Fulano con 2800 puntos")

    def test_fin_con_un_punto(self):
        self.assertEqual(
            batallas.frase_fin(_anfitriones("Ana", "Fulano"),
                               {"1": 1, "2": 0}),
            "Batalla terminada: Ana con 1 punto, Fulano con 0 puntos")

    def test_fin_sin_puntajes(self):
        self.assertEqual(
            batallas.frase_fin(_anfitriones("Ana", "Fulano"), {}),
            "Batalla terminada")

    def test_fin_en_el_orden_de_los_anfitriones(self):
        self.assertEqual(
            batallas.frase_fin(
                _anfitriones("Ana", "Beto", "Caro"),
                {"3": 10, "1": 30, "2": 20}),
            "Batalla terminada: Ana con 30 puntos, Beto con 20 puntos, "
            "Caro con 10 puntos")

    def test_en_curso(self):
        self.assertEqual(
            batallas.frase_en_curso(
                _anfitriones("Ana", "Fulano"), {"1": 1200, "2": 900}),
            "Batalla en curso: Ana 1200 puntos, Fulano 900 puntos")

    def test_en_curso_con_un_punto(self):
        self.assertEqual(
            batallas.frase_en_curso(_anfitriones("Ana"), {"1": 1}),
            "Batalla en curso: Ana 1 punto")

    def test_en_curso_sin_anfitriones_no_dice_nada(self):
        self.assertEqual(batallas.frase_en_curso([], {}), "")

    def test_propiedad_fin_nombra_a_cada_uno_una_vez_y_en_orden(self):
        azar = random.Random(645)
        nombres = ["Ana", "Beto", "Caro", "Dani"]
        for cantidad in range(2, 5):
            for _ in range(50):
                elegidos = nombres[:cantidad]
                anfitriones = _anfitriones(*elegidos)
                puntajes = {str(i + 1): azar.randint(0, 10000)
                            for i in range(cantidad)}
                frase = batallas.frase_fin(anfitriones, puntajes)
                posiciones = []
                for nombre in elegidos:
                    self.assertEqual(frase.count(nombre), 1, frase)
                    posiciones.append(frase.index(nombre))
                self.assertEqual(posiciones, sorted(posiciones), frase)


class TestRegistroBatallas(unittest.TestCase):

    def setUp(self):
        batallas.registro.reiniciar()

    def test_abrir_anuncia_una_sola_vez(self):
        self.assertTrue(batallas.registro.abrir(
            "b1", _anfitriones("Ana", "Fulano")))
        self.assertFalse(batallas.registro.abrir(
            "b1", _anfitriones("Ana", "Fulano")))

    def test_cerrar_anuncia_una_sola_vez(self):
        batallas.registro.abrir("b1", _anfitriones("Ana", "Fulano"))
        self.assertTrue(batallas.registro.cerrar(
            "b1", [], {"1": 3200, "2": 2800}))
        self.assertFalse(batallas.registro.cerrar(
            "b1", [], {"1": 3200, "2": 2800}))

    def test_fin_sin_comienzo_se_anuncia_igual(self):
        self.assertTrue(batallas.registro.cerrar(
            "b1", _anfitriones("Ana", "Fulano"),
            {"1": 3200, "2": 2800}))

    def test_los_puntajes_de_las_armies_no_anuncian(self):
        batallas.registro.abrir("b1", _anfitriones("Ana", "Fulano"))
        batallas.registro.actualizar_puntajes("b1", {"1": 1200, "2": 900})
        self.assertEqual(
            batallas.registro.en_curso(),
            "Batalla en curso: Ana 1200 puntos, Fulano 900 puntos")

    def test_f2_vacio_sin_batalla(self):
        self.assertEqual(batallas.registro.en_curso(), "")

    def test_una_batalla_cerrada_no_sigue_en_curso(self):
        batallas.registro.abrir("b1", _anfitriones("Ana", "Fulano"))
        batallas.registro.cerrar("b1", [], {"1": 1, "2": 0})
        self.assertEqual(batallas.registro.en_curso(), "")

    def test_reiniciar_olvida_todo(self):
        batallas.registro.abrir("b1", _anfitriones("Ana", "Fulano"))
        batallas.registro.reiniciar()
        self.assertEqual(batallas.registro.en_curso(), "")


if __name__ == "__main__":
    unittest.main()
