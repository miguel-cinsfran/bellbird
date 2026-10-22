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

    def test_reconoce_aiff_aif_mka_y_webm_tambien_en_mayusculas(self):
        for nombre in ("Tema.aiff", "Tema.aif", "Tema.mka", "clip.webm",
                       "OTRO.WEBM", "notas2.txt"):
            (self.raiz / nombre).write_bytes(b"x")
        bib = Biblioteca(self.raiz)
        self.assertEqual(bib.indexar(), 9)
        nombres = [Path(t.origen).name for t in bib.temas()]
        for nombre in ("Tema.aiff", "Tema.aif", "Tema.mka", "clip.webm",
                       "OTRO.WEBM"):
            self.assertIn(nombre, nombres)
        self.assertNotIn("notas2.txt", nombres)

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

    def test_leer_etiquetas_trae_la_duracion(self):
        def etiquetas(ruta):
            return {"titulo": "Tema X", "duracion_ms": 222000}

        bib = Biblioteca(self.raiz, leer_etiquetas=etiquetas)
        bib.indexar()
        self.assertEqual(bib.temas()[0].duracion_ms, 222000)

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
        self.assertEqual(temas[0].duracion_ms, 123000)
        self.assertEqual(temas[2].duracion_ms, 0)

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


class TestBibliotecaConCache(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        (self.raiz / "a.mp3").write_bytes(b"aaa")
        (self.raiz / "b.mp3").write_bytes(b"bbb")
        from ytchat.music.etiquetas import CacheEtiquetas
        self.ruta_cache = self.raiz / "cache" / "etiquetas.json"
        self.cache = CacheEtiquetas(self.ruta_cache)

    def tearDown(self):
        self.tmp.cleanup()

    def _poner_en_cache(self, nombre, datos):
        ruta = (self.raiz / nombre).resolve()
        info = ruta.stat()
        self.cache.poner(str(ruta), info.st_mtime_ns, info.st_size, datos)

    def test_indexar_usa_las_etiquetas_de_la_cache(self):
        self._poner_en_cache(
            "a.mp3", {"titulo": "Tema A", "artista": "Ana", "duracion_ms": 93000})
        bib = Biblioteca(self.raiz, cache=self.cache)
        self.assertEqual(bib.indexar(), 2)
        por_nombre = {Path(t.origen).name: t for t in bib.temas()}
        self.assertEqual(
            (por_nombre["a.mp3"].titulo, por_nombre["a.mp3"].artista),
            ("Tema A", "Ana"))
        self.assertEqual(por_nombre["b.mp3"].titulo, "b")

    def test_indexar_usa_la_duracion_de_la_cache(self):
        self._poner_en_cache("a.mp3", {"titulo": "Tema A", "duracion_ms": 93000})
        bib = Biblioteca(self.raiz, cache=self.cache)
        bib.indexar()
        por_nombre = {Path(t.origen).name: t for t in bib.temas()}
        self.assertEqual(por_nombre["a.mp3"].duracion_ms, 93000)
        self.assertEqual(por_nombre["b.mp3"].duracion_ms, 0)

    def test_pendientes_devuelve_solo_lo_que_falta(self):
        self._poner_en_cache(
            "a.mp3", {"titulo": "Tema A", "duracion_ms": 93000})
        bib = Biblioteca(self.raiz, cache=self.cache)
        bib.indexar()
        pendientes = bib.pendientes()
        self.assertEqual([Path(t.origen).name for t in pendientes], ["b.mp3"])

    def test_pendientes_vacio_cuando_todo_esta_en_cache(self):
        self._poner_en_cache(
            "a.mp3", {"titulo": "Tema A", "duracion_ms": 93000})
        self._poner_en_cache("b.mp3", {"duracion_ms": 95000})
        bib = Biblioteca(self.raiz, cache=self.cache)
        bib.indexar()
        self.assertEqual(bib.pendientes(), ())

    def test_pendientes_incluye_entrada_con_duracion_cero(self):
        self._poner_en_cache(
            "a.mp3", {"titulo": "Tema A", "duracion_ms": 93000})
        self._poner_en_cache("b.mp3", {})
        bib = Biblioteca(self.raiz, cache=self.cache)
        bib.indexar()
        pendientes = bib.pendientes()
        self.assertEqual([Path(t.origen).name for t in pendientes], ["b.mp3"])

    def test_sin_cache_pendientes_son_todos(self):
        bib = Biblioteca(self.raiz)
        bib.indexar()
        self.assertEqual(len(bib.pendientes()), 2)

    def test_si_el_archivo_cambio_vuelve_a_ser_pendiente(self):
        self._poner_en_cache(
            "a.mp3", {"titulo": "Tema A", "duracion_ms": 93000})
        (self.raiz / "a.mp3").write_bytes(b"aaa-modificado-distinto")
        bib = Biblioteca(self.raiz, cache=self.cache)
        bib.indexar()
        por_nombre = {Path(t.origen).name: t for t in bib.temas()}
        self.assertEqual(por_nombre["a.mp3"].titulo, "a")
        self.assertEqual(
            [Path(t.origen).name for t in bib.pendientes()], ["a.mp3", "b.mp3"])

    def test_actualizar_conserva_orden_y_cantidad(self):
        bib = Biblioteca(self.raiz)
        bib.indexar()
        antes = [t.origen for t in bib.temas()]
        nuevos = [Tema(t.origen, "Nuevo " + Path(t.origen).stem)
                  for t in bib.temas()]
        self.assertEqual(bib.actualizar(nuevos), 2)
        despues = bib.temas()
        self.assertEqual([t.origen for t in despues], antes)
        self.assertEqual(len(despues), 2)
        self.assertEqual([t.titulo for t in despues], ["Nuevo a", "Nuevo b"])

    def test_actualizar_ignora_lo_que_no_esta_en_el_indice(self):
        bib = Biblioteca(self.raiz)
        bib.indexar()
        fantasma = Tema("C:/musica/fantasma.mp3", "Fantasma")
        self.assertEqual(bib.actualizar([fantasma]), 0)
        self.assertEqual(len(bib.temas()), 2)

    def test_actualizar_vacio_no_hace_nada(self):
        bib = Biblioteca(self.raiz)
        bib.indexar()
        self.assertEqual(bib.actualizar([]), 0)
        self.assertEqual(len(bib.temas()), 2)


if __name__ == "__main__":
    unittest.main()
