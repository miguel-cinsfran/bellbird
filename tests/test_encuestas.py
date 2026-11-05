"""Frases y registro de encuestas del directo de TikTok.

Puro y sin wx: fija el texto de apertura, cierre y F2, y que cada encuesta
se anuncie una sola vez por etapa aunque TikTok repita el mensaje.
"""

import random
import unittest

from bellbird.capture import encuestas


class TestFraseApertura(unittest.TestCase):

    def test_con_titulo(self):
        self.assertEqual(
            encuestas.frase_apertura(
                "¿Qué almorzamos?",
                [("pizza", 0), ("empanadas", 0), ("sushi", 0)]),
            "Encuesta: ¿Qué almorzamos? Opciones: pizza, empanadas y sushi")

    def test_sin_titulo(self):
        self.assertEqual(
            encuestas.frase_apertura(
                "",
                [("pizza", 0), ("empanadas", 0), ("sushi", 0)]),
            "Encuesta abierta. Opciones: pizza, empanadas y sushi")


class TestFraseCierre(unittest.TestCase):

    def test_ganador_con_el_resto(self):
        self.assertEqual(
            encuestas.frase_cierre(
                "¿Qué almorzamos?",
                [("pizza", 12), ("empanadas", 8), ("sushi", 3)]),
            "Encuesta terminada: ¿Qué almorzamos? Ganó pizza con 12 votos, "
            "empanadas con 8 votos y sushi con 3 votos")

    def test_empate_en_el_primer_lugar(self):
        self.assertEqual(
            encuestas.frase_cierre(
                "¿Qué almorzamos?",
                [("pizza", 8), ("empanadas", 8), ("sushi", 3)]),
            "Encuesta terminada: ¿Qué almorzamos? Empate entre pizza y "
            "empanadas con 8 votos, sushi con 3 votos")

    def test_sin_votos(self):
        self.assertEqual(
            encuestas.frase_cierre(
                "¿Qué almorzamos?",
                [("pizza", 0), ("empanadas", 0), ("sushi", 0)]),
            "Encuesta terminada: ¿Qué almorzamos? Sin votos")

    def test_un_voto_en_singular_y_opcion_sin_votos(self):
        self.assertEqual(
            encuestas.frase_cierre(
                "¿Qué almorzamos?",
                [("pizza", 1), ("sushi", 0)]),
            "Encuesta terminada: ¿Qué almorzamos? Ganó pizza con 1 voto, "
            "sushi sin votos")

    def test_la_frase_nombra_cada_opcion_una_sola_vez(self):
        generador = random.Random(653)
        for _ in range(200):
            cantidad = generador.randint(1, 6)
            opciones = [(f"opcion{indice}", generador.randint(0, 50))
                        for indice in range(cantidad)]
            frase = encuestas.frase_cierre("Título", opciones)
            if not any(votos for _texto, votos in opciones):
                self.assertTrue(frase.endswith("Sin votos"), frase)
                continue
            for texto, _votos in opciones:
                self.assertEqual(frase.count(texto), 1, frase)


class TestFraseEnCurso(unittest.TestCase):

    def test_con_titulo_y_votos(self):
        self.assertEqual(
            encuestas.frase_en_curso(
                "¿Qué almorzamos?",
                [("Pizza", 5), ("empanadas", 3), ("sushi", 0)]),
            "Encuesta en curso: ¿Qué almorzamos? Pizza con 5 votos, "
            "empanadas con 3 votos y sushi sin votos")

    def test_sin_titulo(self):
        self.assertEqual(
            encuestas.frase_en_curso("", [("pizza", 2), ("sushi", 0)]),
            "Encuesta en curso. pizza con 2 votos y sushi sin votos")


class TestRegistroEncuestas(unittest.TestCase):

    def setUp(self):
        self.registro = encuestas.RegistroEncuestas()

    def test_abrir_es_verdadero_solo_la_primera_vez(self):
        opciones = [("pizza", 0), ("sushi", 0)]
        self.assertTrue(self.registro.abrir("1", "¿Qué almorzamos?", opciones))
        self.assertFalse(self.registro.abrir("1", "¿Qué almorzamos?", opciones))

    def test_cerrar_es_verdadero_solo_la_primera_vez(self):
        opciones = [("pizza", 2), ("sushi", 0)]
        self.registro.abrir("1", "¿Qué almorzamos?", opciones)
        self.assertTrue(self.registro.cerrar("1", "¿Qué almorzamos?", opciones))
        self.assertFalse(self.registro.cerrar("1", "¿Qué almorzamos?", opciones))

    def test_cerrar_sin_haberse_abierto_igual_es_verdadero(self):
        self.assertTrue(
            self.registro.cerrar("9", "Llegó a mitad", [("pizza", 4)]))

    def test_en_curso_vacio_sin_encuesta(self):
        self.assertEqual(self.registro.en_curso(), "")

    def test_en_curso_usa_los_ultimos_votos(self):
        self.registro.abrir(
            "1", "¿Qué almorzamos?", [("Pizza", 1), ("sushi", 0)])
        self.assertEqual(
            self.registro.en_curso(),
            "Encuesta en curso: ¿Qué almorzamos? Pizza con 1 voto y sushi "
            "sin votos")
        self.registro.votos("1", [("Pizza", 5), ("sushi", 2)])
        self.assertEqual(
            self.registro.en_curso(),
            "Encuesta en curso: ¿Qué almorzamos? Pizza con 5 votos y sushi "
            "con 2 votos")

    def test_cerrar_la_saca_de_en_curso(self):
        opciones = [("pizza", 3)]
        self.registro.abrir("1", "Título", opciones)
        self.registro.cerrar("1", "Título", opciones)
        self.assertEqual(self.registro.en_curso(), "")

    def test_votos_de_una_encuesta_nunca_vista_la_dejan_en_curso(self):
        self.registro.votos("7", [("Pizza", 5), ("sushi", 0)])
        self.assertEqual(
            self.registro.en_curso(),
            "Encuesta en curso. Pizza con 5 votos y sushi sin votos")

    def test_votos_despues_de_cerrar_no_la_reabren(self):
        self.registro.cerrar("7", "Título", [("Pizza", 3)])
        self.registro.votos("7", [("Pizza", 9)])
        self.assertEqual(self.registro.en_curso(), "")

    def test_reiniciar_olvida_la_encuesta_y_vuelve_a_anunciar(self):
        opciones = [("pizza", 0)]
        self.registro.abrir("1", "Título", opciones)
        self.registro.reiniciar()
        self.assertEqual(self.registro.en_curso(), "")
        self.assertTrue(self.registro.abrir("1", "Título", opciones))


if __name__ == "__main__":
    unittest.main()
