"""Pruebas del modo de aviso de la música (musica_decir), puro sin wx ni VLC."""

import unittest

from bellbird.core import musica_decir
from bellbird.music.modelo import Tema


class TestNormalizar(unittest.TestCase):

    def test_los_cuatro_modos_valen_tal_cual(self):
        for modo in ("nada", "titulo", "titulo_artista", "artista"):
            with self.subTest(modo=modo):
                self.assertEqual(musica_decir.normalizar(modo), modo)

    def test_ignora_mayusculas_y_espacios(self):
        self.assertEqual(musica_decir.normalizar("  Titulo_Artista "), "titulo_artista")

    def test_cualquier_otra_cosa_da_titulo(self):
        for valor in ("", "   ", "tema", "todo", "sí", None, True, False, 0, 42):
            with self.subTest(valor=valor):
                self.assertEqual(musica_decir.normalizar(valor), "titulo")


class TestDesdeIni(unittest.TestCase):

    def test_decir_presente_manda_sobre_las_viejas(self):
        for modo in ("nada", "titulo", "titulo_artista", "artista"):
            with self.subTest(modo=modo):
                self.assertEqual(musica_decir.desde_ini(modo, False, False), modo)
                self.assertEqual(musica_decir.desde_ini(modo, True, True), modo)

    def test_decir_presente_se_normaliza(self):
        self.assertEqual(musica_decir.desde_ini("  ARTISTA ", False, False), "artista")
        self.assertEqual(musica_decir.desde_ini("otro", False, False), "titulo")

    def test_sin_decir_y_sin_titulo_da_nada(self):
        self.assertEqual(musica_decir.desde_ini("", False, False), "nada")
        self.assertEqual(musica_decir.desde_ini("", False, True), "nada")
        self.assertEqual(musica_decir.desde_ini("   ", False, False), "nada")

    def test_sin_decir_con_titulo_y_artista_da_los_dos(self):
        self.assertEqual(musica_decir.desde_ini("", True, True), "titulo_artista")

    def test_sin_decir_con_titulo_sin_artista_da_titulo(self):
        self.assertEqual(musica_decir.desde_ini("", True, False), "titulo")


class TestIncluyeArtista(unittest.TestCase):

    def test_solo_los_modos_con_artista(self):
        self.assertFalse(musica_decir.incluye_artista("nada"))
        self.assertFalse(musica_decir.incluye_artista("titulo"))
        self.assertTrue(musica_decir.incluye_artista("titulo_artista"))
        self.assertTrue(musica_decir.incluye_artista("artista"))

    def test_lo_desconocido_no_incluye(self):
        self.assertFalse(musica_decir.incluye_artista("otro"))
        self.assertFalse(musica_decir.incluye_artista(""))


class TestModoManual(unittest.TestCase):

    def test_nada_pasa_a_titulo(self):
        self.assertEqual(musica_decir.modo_manual("nada"), "titulo")

    def test_los_demas_valen_tal_cual(self):
        for modo in ("titulo", "titulo_artista", "artista"):
            with self.subTest(modo=modo):
                self.assertEqual(musica_decir.modo_manual(modo), modo)

    def test_lo_desconocido_da_titulo(self):
        self.assertEqual(musica_decir.modo_manual("otro"), "titulo")


class TestTexto(unittest.TestCase):

    def test_nada_calla_con_y_sin_artista(self):
        self.assertEqual(musica_decir.texto("Tema", "Ana", "nada"), "")
        self.assertEqual(musica_decir.texto("Tema", "", "nada"), "")

    def test_titulo_ignora_al_artista(self):
        self.assertEqual(musica_decir.texto("Tema", "Ana", "titulo"), "Tema")

    def test_los_dos_dicen_titulo_de_artista(self):
        self.assertEqual(musica_decir.texto("Tema", "Ana", "titulo_artista"),
                         "Tema, de Ana")

    def test_los_dos_sin_artista_dicen_solo_el_titulo(self):
        self.assertEqual(musica_decir.texto("Tema", "", "titulo_artista"), "Tema")

    def test_artista_dice_solo_el_artista(self):
        self.assertEqual(musica_decir.texto("Tema", "Ana", "artista"), "Ana")

    def test_artista_sin_artista_dice_el_titulo(self):
        self.assertEqual(musica_decir.texto("Tema", "", "artista"), "Tema")

    def test_modo_desconocido_dice_el_titulo(self):
        self.assertEqual(musica_decir.texto("Tema", "Ana", "otro"), "Tema")


class TestTituloRespaldo(unittest.TestCase):

    def test_enlace_da_el_origen_entero(self):
        self.assertEqual(musica_decir.titulo_respaldo("https://ejemplo.test/v.mp3", True),
                         "https://ejemplo.test/v.mp3")

    def test_archivo_da_el_nombre_sin_extension(self):
        self.assertEqual(musica_decir.titulo_respaldo("C:/musica/cancion.mp3", False),
                         "cancion")


class TestTextoTema(unittest.TestCase):

    def test_con_titulo_y_artista_segun_modo(self):
        tema = Tema("C:/musica/a.mp3", "Tema", artista="Ana")
        self.assertEqual(musica_decir.texto_tema(tema, "titulo"), "Tema")
        self.assertEqual(musica_decir.texto_tema(tema, "titulo_artista"), "Tema, de Ana")
        self.assertEqual(musica_decir.texto_tema(tema, "artista"), "Ana")
        self.assertEqual(musica_decir.texto_tema(tema, "nada"), "")

    def test_sin_titulo_usa_el_archivo(self):
        tema = Tema("C:/musica/cancion.mp3", "")
        self.assertEqual(musica_decir.texto_tema(tema, "titulo"), "cancion")

    def test_sin_titulo_de_enlace_usa_el_origen(self):
        tema = Tema("https://ejemplo.test/v.mp3", "")
        self.assertEqual(musica_decir.texto_tema(tema, "titulo"),
                         "https://ejemplo.test/v.mp3")


if __name__ == "__main__":
    unittest.main()
