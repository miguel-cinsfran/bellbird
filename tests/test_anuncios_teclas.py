"""Pruebas de los avisos de silencio y salto de la música."""

import unittest

from tests.pseudo_prueba import con_pseudo
from bellbird.core.idioma import _
from bellbird.music import anuncios_teclas


class TestConstantes(unittest.TestCase):

    def test_constantes_con_el_texto_que_oye_el_usuario(self):
        self.assertEqual(anuncios_teclas.TEXTO_SILENCIADA, "Música silenciada")
        self.assertEqual(anuncios_teclas.TEXTO_RESTAURADA,
                         "Sonido de la música activado")


class TestPseudoTextos(unittest.TestCase):
    """Bajo pseudotraducción, cada frase al usuario sale marcada."""

    def test_avisos_salen_marcados(self):
        with con_pseudo():
            marcados = [
                anuncios_teclas.aviso_silencio(True).texto,
                anuncios_teclas.aviso_silencio(False).texto,
                _(anuncios_teclas.TEXTO_SILENCIADA),
                _(anuncios_teclas.TEXTO_RESTAURADA),
            ]
        for texto in marcados:
            with self.subTest(texto=texto):
                self.assertTrue(texto.startswith("[¡"), texto)


if __name__ == "__main__":
    unittest.main()
