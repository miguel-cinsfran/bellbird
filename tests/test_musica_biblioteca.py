"""Pruebas de la biblioteca de música (biblioteca.py)."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ytchat.music.biblioteca import Biblioteca, ErrorBiblioteca
from ytchat.music.modelo import Tema


class TestModelo(unittest.TestCase):

    def test_es_enlace(self):
        self.assertTrue(Tema("http://ejemplo.test/a.mp3", "a").es_enlace)
        self.assertTrue(Tema("HTTPS://EJEMPLO.TEST/a.mp3", "a").es_enlace)
        self.assertFalse(Tema(r"C:\musica\a.mp3", "a").es_enlace)

    def test_actual(self):
        from ytchat.music.modelo import EstadoMusica

        a, b = Tema("a.mp3", "a"), Tema("b.mp3", "b")
        vacio = EstadoMusica((), None, False, False, 100, False)
        self.assertIsNone(vacio.actual)
        con_posicion = EstadoMusica((a, b), 1, False, False, 100, False)
        self.assertEqual(con_posicion.actual, b)


class TestBiblioteca(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        (self.raiz / "Rock").mkdir()
        (self.raiz / "Rock" / "Cancion.mp3").write_bytes(b"x")
        (self.raiz / "Rock" / "Otra.wav").write_bytes(b"x")
        (self.raiz / "notas.txt").write_text("no es audio", encoding="utf-8")
        (self.raiz / "sub").mkdir()
        (self.raiz / "sub" / "zeta.flac").write_bytes(b"x")
        (self.raiz / "sub" / "Alfa.ogg").write_bytes(b"x")

    def tearDown(self):
        self.tmp.cleanup()

    def test_indexa_subcarpetas_y_orden_estable(self):
        bib = Biblioteca(self.raiz)
        self.assertEqual(bib.indexar(), 4)
        nombres = [Path(t.origen).name for t in bib.temas()]
        self.assertEqual(nombres, ["Cancion.mp3", "Otra.wav", "Alfa.ogg", "zeta.flac"])
        for tema in bib.temas():
            self.assertTrue(Path(tema.origen).is_absolute())

    def test_ignora_extensiones_que_no_son_audio(self):
        bib = Biblioteca(self.raiz)
        bib.indexar()
        self.assertNotIn("notas.txt", [Path(t.origen).name for t in bib.temas()])

    def test_volver_a_indexar_reemplaza_el_indice(self):
        bib = Biblioteca(self.raiz)
        self.assertEqual(bib.indexar(), 4)
        (self.raiz / "Nuevo.m4a").write_bytes(b"x")
        self.assertEqual(bib.indexar(), 5)

    def test_carpeta_inexistente_lanza(self):
        bib = Biblioteca(self.raiz / "no-existe")
        with self.assertRaises(ErrorBiblioteca):
            bib.indexar()

    def test_sin_indexar_temas_vacio(self):
        self.assertEqual(Biblioteca(self.raiz).temas(), ())

    def test_leer_etiquetas_que_lanza_usa_el_nombre(self):
        def explota(ruta):
            raise RuntimeError("sin etiquetas")

        bib = Biblioteca(self.raiz, leer_etiquetas=explota)
        bib.indexar()
        por_nombre = {Path(t.origen).name: t for t in bib.temas()}
        self.assertEqual(por_nombre["Cancion.mp3"].titulo, "Cancion")
        self.assertEqual(len(bib.temas()), 4)

    def test_leer_etiquetas_con_titulo_vacio_usa_el_nombre(self):
        bib = Biblioteca(self.raiz, leer_etiquetas=lambda ruta: {"titulo": "", "artista": "X"})
        bib.indexar()
        tema = next(t for t in bib.temas() if Path(t.origen).name == "Alfa.ogg")
        self.assertEqual(tema.titulo, "Alfa")

    def test_leer_etiquetas_completas(self):
        def etiquetas(ruta):
            return {"titulo": "Tema X", "artista": "Artista Y", "album": "Album Z"}

        bib = Biblioteca(self.raiz, leer_etiquetas=etiquetas)
        bib.indexar()
        tema = bib.temas()[0]
        self.assertEqual((tema.titulo, tema.artista, tema.album), ("Tema X", "Artista Y", "Album Z"))

    def test_buscar_sin_tildes_ni_mayusculas(self):
        def etiquetas(ruta):
            if Path(ruta).name == "Cancion.mp3":
                return {"titulo": "Canción de verano", "artista": "José", "album": "Álbum Ñandú"}
            return {}

        bib = Biblioteca(self.raiz, leer_etiquetas=etiquetas)
        bib.indexar()
        self.assertEqual([Path(t.origen).name for t in bib.buscar("cancion")], ["Cancion.mp3"])
        self.assertEqual([Path(t.origen).name for t in bib.buscar("JOSE")], ["Cancion.mp3"])
        self.assertEqual([Path(t.origen).name for t in bib.buscar("nandu")], ["Cancion.mp3"])
        self.assertEqual([Path(t.origen).name for t in bib.buscar("verano")], ["Cancion.mp3"])
        self.assertEqual(bib.buscar("no-existe"), ())

    def test_buscar_vacio_no_lanza(self):
        bib = Biblioteca(self.raiz)
        bib.indexar()
        self.assertEqual(bib.buscar(""), ())
        self.assertEqual(bib.buscar("   "), ())
        self.assertEqual(bib.buscar(None), ())

    def test_buscar_no_toca_el_disco(self):
        bib = Biblioteca(self.raiz)
        bib.indexar()
        with mock.patch("os.walk", side_effect=AssertionError("no debe recorrer el disco")), \
                mock.patch("os.scandir", side_effect=AssertionError("no debe recorrer el disco")):
            encontrados = bib.buscar("cancion")
        self.assertEqual([Path(t.origen).name for t in encontrados], ["Cancion.mp3"])

    def test_m3u8_relativas_absolutas_extinf_y_bom(self):
        listas = self.raiz / "listas"
        listas.mkdir()
        absoluto = self.raiz / "Rock" / "Otra.wav"
        contenido = (
            "#EXTM3U\n"
            "#EXTINF:123,Primera\n"
            "../Rock/Cancion.mp3\n"
            f"{absoluto}\n"
            "#EXTINF:-1,Segunda\n"
            "../sub/Alfa.ogg\n"
        )
        lista = listas / "mi lista.m3u8"
        lista.write_text(contenido, encoding="utf-8-sig")
        temas, saltadas = Biblioteca(self.raiz).cargar_m3u8(lista)
        self.assertEqual(saltadas, 0)
        self.assertEqual([Path(t.origen).name for t in temas],
                         ["Cancion.mp3", "Otra.wav", "Alfa.ogg"])
        self.assertEqual(temas[0].titulo, "Primera")
        self.assertEqual(temas[1].titulo, "Otra")
        self.assertEqual(temas[2].titulo, "Segunda")

    def test_m3u8_salta_web_inexistente_y_otra_extension(self):
        lista = self.raiz / "mezcla.m3u8"
        lista.write_text(
            "https://ejemplo.test/cancion.mp3\n"
            "no-existe.mp3\n"
            "notas.txt\n"
            "Rock/Cancion.mp3\n",
            encoding="utf-8",
        )
        temas, saltadas = Biblioteca(self.raiz).cargar_m3u8(lista)
        self.assertEqual(saltadas, 3)
        self.assertEqual([Path(t.origen).name for t in temas], ["Cancion.mp3"])

    def test_m3u8_con_enlace_de_youtube_entra_y_las_demas_web_se_saltan(self):
        lista = self.raiz / "enlaces.m3u8"
        lista.write_text(
            "#EXTM3U\n"
            "#EXTINF:-1,Una canción\n"
            "https://www.youtube.com/watch?v=abc123\n"
            "https://ejemplo.test/cancion.mp3\n"
            "https://youtu.be/def456\n",
            encoding="utf-8",
        )
        temas, saltadas = Biblioteca(self.raiz).cargar_m3u8(lista)
        self.assertEqual(saltadas, 1)
        self.assertEqual([t.origen for t in temas],
                         ["https://www.youtube.com/watch?v=abc123",
                          "https://youtu.be/def456"])
        self.assertEqual(temas[0].titulo, "Una canción")
        self.assertEqual(temas[1].titulo, "https://youtu.be/def456")

    def test_m3u8_archivo_inexistente(self):
        with self.assertRaises(ErrorBiblioteca):
            Biblioteca(self.raiz).cargar_m3u8(self.raiz / "nada.m3u8")

    def test_m3u8_extension_incorrecta(self):
        with self.assertRaises(ErrorBiblioteca):
            Biblioteca(self.raiz).cargar_m3u8(self.raiz / "Rock" / "Cancion.mp3")

    def test_m3u8_no_se_puede_leer(self):
        lista = self.raiz / "ilegible.m3u8"
        lista.write_text("#EXTM3U\n", encoding="utf-8")
        with mock.patch("pathlib.Path.read_text", side_effect=OSError("boom")):
            with self.assertRaises(ErrorBiblioteca):
                Biblioteca(self.raiz).cargar_m3u8(lista)


if __name__ == "__main__":
    unittest.main()
