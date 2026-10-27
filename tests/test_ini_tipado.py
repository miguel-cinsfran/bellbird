"""Pruebas de los ayudantes tipados de config.ini (ini_tipado)."""

import unittest

from ytchat.core import config
from ytchat.core import ini_tipado


def _parser(texto: str = ""):
    p = config._mk_parser()
    p.read_string(texto)
    return p


class TestPi(unittest.TestCase):

    def test_recorta_al_minimo(self):
        p = _parser("[ui]\ntamanio_fuente_chat = 2\n")
        self.assertEqual(
            ini_tipado.leer_entero(p, "ui", "tamanio_fuente_chat", lo=8, hi=24), 8)

    def test_recorta_al_maximo(self):
        p = _parser("[ui]\ntamanio_fuente_chat = 40\n")
        self.assertEqual(
            ini_tipado.leer_entero(p, "ui", "tamanio_fuente_chat", lo=8, hi=24), 24)

    def test_valor_no_numerico_usa_el_predeterminado(self):
        p = _parser("[ui]\ntamanio_fuente_chat = grande\n")
        self.assertEqual(
            ini_tipado.leer_entero(p, "ui", "tamanio_fuente_chat", lo=8, hi=24), 12)


class TestPf(unittest.TestCase):

    def test_recorta_al_minimo(self):
        p = _parser("[voz]\nvolumen = -1.5\n")
        self.assertEqual(ini_tipado.leer_decimal(p, "voz", "volumen"), 0.0)

    def test_recorta_al_maximo(self):
        p = _parser("[voz]\nvolumen = 2.5\n")
        self.assertEqual(ini_tipado.leer_decimal(p, "voz", "volumen"), 1.0)

    def test_valor_no_numerico_usa_el_predeterminado(self):
        p = _parser("[voz]\nvolumen = alto\n")
        self.assertEqual(ini_tipado.leer_decimal(p, "voz", "volumen"), 1.0)


class TestPb(unittest.TestCase):

    def test_lee_true_y_false(self):
        for texto, esperado in (("true", True), ("false", False)):
            with self.subTest(texto=texto):
                p = _parser(f"[musica]\naleatorio = {texto}\n")
                self.assertEqual(
                    ini_tipado.leer_booleano(p, "musica", "aleatorio"), esperado)

    def test_clave_ausente_usa_el_predeterminado(self):
        self.assertFalse(ini_tipado.leer_booleano(_parser("[musica]\n"), "musica",
                                        "aleatorio"))
        self.assertTrue(ini_tipado.leer_booleano(_parser("[musica]\n"), "musica",
                                       "retomar"))


class TestLista(unittest.TestCase):

    def test_separa_por_comas_quita_espacios_y_vacios_y_pasa_a_minusculas(self):
        self.assertEqual(
            ini_tipado.separar_por_comas(" Uno, DOS ,,tres "), ["uno", "dos", "tres"])

    def test_texto_vacio_da_lista_vacia(self):
        self.assertEqual(ini_tipado.separar_por_comas(""), [])
