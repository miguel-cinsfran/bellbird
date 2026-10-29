"""Pruebas del texto de la pregunta por igualar el volumen.

El módulo es puro: no abre ventanas ni toca el disco. Las pruebas cubren
el texto con una canción y con varias, el tamaño en sus tres formas y la
propiedad de que más bytes nunca dan un tamaño menor.
"""

import unittest

from tests.pseudo_prueba import con_pseudo
from ytchat.core.idioma import _
from ytchat.music import pregunta_igualar


MB = 1024 * 1024
GB = 1024 * 1024 * 1024

COLA = ("¿Igualar su volumen ahora? Los archivos no se modifican. "
        "La medición usa el procesador y puede tardar.")


def _bytes_de_texto(texto):
    """El tamaño que representa el texto, en bytes, para poder comparar."""
    if texto.startswith("menos de"):
        return 0
    numero = float(texto.split(" ")[0].replace(",", "."))
    if texto.endswith("MB"):
        return numero * MB
    return numero * GB


class TestTextoTamano(unittest.TestCase):

    def test_menos_de_un_megabyte(self):
        self.assertEqual(pregunta_igualar.texto_tamano(0), "menos de 1 MB")
        self.assertEqual(pregunta_igualar.texto_tamano(1024), "menos de 1 MB")
        self.assertEqual(pregunta_igualar.texto_tamano(MB - 1), "menos de 1 MB")

    def test_un_megabyte_exacto(self):
        self.assertEqual(pregunta_igualar.texto_tamano(MB), "1 MB")

    def test_megabytes_enteros(self):
        self.assertEqual(pregunta_igualar.texto_tamano(350 * MB), "350 MB")
        self.assertEqual(
            pregunta_igualar.texto_tamano(350 * MB + MB // 2), "350 MB")

    def test_el_salto_a_gigabytes(self):
        self.assertEqual(pregunta_igualar.texto_tamano(GB - 1), "1023 MB")
        self.assertEqual(pregunta_igualar.texto_tamano(GB), "1,0 GB")

    def test_gigabytes_con_coma_decimal(self):
        self.assertEqual(
            pregunta_igualar.texto_tamano(int(32.4 * GB)), "32,4 GB")

    def test_un_tamano_ilegible_dice_que_no_llega_a_un_megabyte(self):
        self.assertEqual(pregunta_igualar.texto_tamano(None), "menos de 1 MB")
        self.assertEqual(pregunta_igualar.texto_tamano("abc"), "menos de 1 MB")

    def test_mas_bytes_no_dan_un_texto_de_tamano_menor(self):
        tamanos = [
            0, 1024, MB - 1, MB, MB + 1, 350 * MB, 1023 * MB,
            GB - 1, GB, GB + 1, int(1.5 * GB), int(32.4 * GB),
            100 * GB, 1000 * GB,
        ]
        anterior = -1
        for bases in tamanos:
            with self.subTest(bases=bases):
                texto = pregunta_igualar.texto_tamano(bases)
                actual = _bytes_de_texto(texto)
                self.assertGreaterEqual(actual, anterior)
                anterior = actual


class TestTextoPregunta(unittest.TestCase):

    def test_una_cancion_en_singular(self):
        self.assertEqual(
            pregunta_igualar.texto_pregunta(1, 5 * MB),
            "Hay 1 canción sin medir (5 MB). " + COLA)

    def test_varias_canciones_en_plural(self):
        self.assertEqual(
            pregunta_igualar.texto_pregunta(6635, int(32.4 * GB)),
            "Hay 6635 canciones sin medir (32,4 GB). " + COLA)

    def test_dos_canciones_en_plural(self):
        self.assertTrue(
            pregunta_igualar.texto_pregunta(2, 0).startswith(
                "Hay 2 canciones sin medir (menos de 1 MB). "))

    def test_el_resto_del_texto_es_el_mismo_para_una_y_varias(self):
        uno = pregunta_igualar.texto_pregunta(1, 5 * MB)
        varias = pregunta_igualar.texto_pregunta(4, 5 * MB)
        self.assertTrue(uno.endswith(COLA))
        self.assertTrue(varias.endswith(COLA))

    def test_el_titulo_y_la_casilla_estan_fijos(self):
        self.assertEqual(pregunta_igualar.TITULO, "Igualar volumen")
        self.assertEqual(pregunta_igualar.CASILLA, "&No volver a preguntar")


class TestPseudoPreguntaIgualar(unittest.TestCase):
    """Pseudotraducción de la pregunta por igualar el volumen.

    Sin ventanas: exige el título, la casilla, los tamaños y la pregunta
    marcados, con los números presentes.
    """

    def test_titulo_y_casilla_salen_marcados(self):
        with con_pseudo():
            titulo = _(pregunta_igualar.TITULO)
            casilla = _(pregunta_igualar.CASILLA)
        self.assertTrue(titulo.startswith("[¡"), titulo)
        self.assertTrue(casilla.startswith("[¡"), casilla)

    def test_tamanos_salen_marcados_en_sus_tres_formas(self):
        with con_pseudo():
            chico = pregunta_igualar.texto_tamano(0)
            megas = pregunta_igualar.texto_tamano(350 * MB)
            gigas = pregunta_igualar.texto_tamano(int(32.4 * GB))
        for texto in (chico, megas, gigas):
            with self.subTest(texto=texto):
                self.assertTrue(texto.startswith("[¡"), texto)
        self.assertIn("350", megas)
        self.assertIn("32,4", gigas)

    def test_pregunta_marca_en_singular_y_en_plural_con_los_datos(self):
        with con_pseudo():
            una = pregunta_igualar.texto_pregunta(1, 5 * MB)
            varias = pregunta_igualar.texto_pregunta(6635, int(32.4 * GB))
        for texto in (una, varias):
            with self.subTest(texto=texto):
                self.assertTrue(texto.startswith("[¡"), texto)
        self.assertIn("1", una)
        self.assertIn("5", una)
        self.assertIn("6635", varias)
        self.assertIn("32,4", varias)


if __name__ == "__main__":
    unittest.main()
