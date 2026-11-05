"""Pruebas puras del comando !clip del chat."""

import unittest

from guyrapu.core import comando_clip


class TestPedidoDeClip(unittest.TestCase):
    def test_reconoce_el_comando_al_principio(self):
        for texto in ("!clip", "!CLIP ahora", "!Clip  ya", "  !clip"):
            with self.subTest(texto=texto):
                self.assertTrue(comando_clip.es_pedido(texto))

    def test_no_reconoce_el_comando_dentro_del_texto(self):
        self.assertFalse(comando_clip.es_pedido("hola !clip"))

    def test_otra_palabra_que_empieza_igual_no_es_el_comando(self):
        self.assertFalse(comando_clip.es_pedido("!clipper"))


class TestEsperaDelComando(unittest.TestCase):
    def test_sin_clip_anterior_pasa(self):
        self.assertTrue(comando_clip.decidir("!clip", 100.0, None, 1))

    def test_justo_antes_del_minuto_no_pasa(self):
        self.assertFalse(comando_clip.decidir("!clip", 159.999, 100.0, 1))

    def test_justo_en_el_borde_del_minuto_pasa(self):
        self.assertTrue(comando_clip.decidir("!clip", 160.0, 100.0, 1))

    def test_la_espera_se_mide_en_minutos(self):
        self.assertFalse(comando_clip.decidir("!clip", 219.0, 100.0, 2))
        self.assertTrue(comando_clip.decidir("!clip", 220.0, 100.0, 2))

    def test_un_texto_que_no_es_el_comando_no_pasa(self):
        self.assertFalse(comando_clip.decidir("hola !clip", 999.0, None, 1))


if __name__ == "__main__":
    unittest.main()
