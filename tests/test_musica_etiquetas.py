"""Pruebas de la caché de etiquetas de música (etiquetas.py)."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from ytchat.music.etiquetas import CacheEtiquetas, leer_con_reintento


def _archivo(tmp, nombre="tema.mp3", contenido=b"audio"):
    ruta = Path(tmp) / nombre
    ruta.write_bytes(contenido)
    info = ruta.stat()
    return str(ruta.resolve()), info.st_mtime_ns, info.st_size


class TestBuscarYPoner(unittest.TestCase):

    def test_buscar_sin_nada_da_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheEtiquetas(Path(tmp) / "etiquetas_musica.json")
            self.assertIsNone(cache.buscar("C:/musica/a.mp3", 1, 2))

    def test_poner_y_buscar_devuelve_las_etiquetas(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheEtiquetas(Path(tmp) / "etiquetas_musica.json")
            origen, mtime_ns, tamano = _archivo(tmp)
            cache.poner(origen, mtime_ns, tamano,
                        {"titulo": "Tema", "artista": "Ana", "album": "Disco",
                         "duracion_ms": 222000})
            self.assertEqual(
                cache.buscar(origen, mtime_ns, tamano),
                {"titulo": "Tema", "artista": "Ana", "album": "Disco",
                 "duracion_ms": 222000})

    def test_mtime_distinto_da_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheEtiquetas(Path(tmp) / "etiquetas_musica.json")
            origen, mtime_ns, tamano = _archivo(tmp)
            cache.poner(origen, mtime_ns, tamano, {"titulo": "Tema"})
            self.assertIsNone(cache.buscar(origen, mtime_ns + 1, tamano))

    def test_tamano_distinto_da_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheEtiquetas(Path(tmp) / "etiquetas_musica.json")
            origen, mtime_ns, tamano = _archivo(tmp)
            cache.poner(origen, mtime_ns, tamano, {"titulo": "Tema"})
            self.assertIsNone(cache.buscar(origen, mtime_ns, tamano + 1))

    def test_duracion_cero_da_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheEtiquetas(Path(tmp) / "etiquetas_musica.json")
            origen, mtime_ns, tamano = _archivo(tmp)
            cache.poner(origen, mtime_ns, tamano, {})
            self.assertIsNone(cache.buscar(origen, mtime_ns, tamano))

    def test_sin_etiquetas_pero_con_duracion_da_la_entrada(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheEtiquetas(Path(tmp) / "etiquetas_musica.json")
            origen, mtime_ns, tamano = _archivo(tmp)
            cache.poner(origen, mtime_ns, tamano, {"duracion_ms": 95540})
            self.assertEqual(
                cache.buscar(origen, mtime_ns, tamano),
                {"titulo": "", "artista": "", "album": "", "duracion_ms": 95540})


class TestGuardarYLeer(unittest.TestCase):

    def test_guarda_y_vuelve_a_leer_de_un_archivo_de_verdad(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta_cache = Path(tmp) / "cache" / "etiquetas_musica.json"
            origen, mtime_ns, tamano = _archivo(tmp)
            cache = CacheEtiquetas(ruta_cache)
            cache.poner(origen, mtime_ns, tamano,
                        {"titulo": "Tema", "artista": "Ana", "album": "Disco",
                         "duracion_ms": 222000})
            self.assertTrue(cache.guardar())
            self.assertTrue(ruta_cache.is_file())
            releida = CacheEtiquetas(ruta_cache)
            self.assertEqual(
                releida.buscar(origen, mtime_ns, tamano),
                {"titulo": "Tema", "artista": "Ana", "album": "Disco",
                 "duracion_ms": 222000})

    def test_guardar_descarta_lo_que_ya_no_existe(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta_cache = Path(tmp) / "etiquetas_musica.json"
            origen, mtime_ns, tamano = _archivo(tmp, "vive.mp3")
            fantasma = str((Path(tmp) / "borrado.mp3").resolve())
            cache = CacheEtiquetas(ruta_cache)
            cache.poner(origen, mtime_ns, tamano, {"titulo": "Vive", "duracion_ms": 93000})
            cache.poner(fantasma, 1, 2, {"titulo": "Fantasma", "duracion_ms": 93000})
            self.assertTrue(cache.guardar())
            releida = CacheEtiquetas(ruta_cache)
            self.assertIsNotNone(releida.buscar(origen, mtime_ns, tamano))
            self.assertIsNone(releida.buscar(fantasma, 1, 2))

    def test_guardar_no_deja_temporales_sueltos(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta_cache = Path(tmp) / "etiquetas_musica.json"
            origen, mtime_ns, tamano = _archivo(tmp)
            cache = CacheEtiquetas(ruta_cache)
            cache.poner(origen, mtime_ns, tamano, {"titulo": "Tema"})
            self.assertTrue(cache.guardar())
            sueltos = list(Path(tmp).glob("*.tmp"))
            self.assertEqual(sueltos, [])

    def test_json_corrupto_da_cache_vacia(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta_cache = Path(tmp) / "etiquetas_musica.json"
            ruta_cache.write_text("{no es json", encoding="utf-8")
            cache = CacheEtiquetas(ruta_cache)
            self.assertIsNone(cache.buscar("C:/musica/a.mp3", 1, 2))

    def test_archivo_vacio_y_ausente_dan_cache_vacia(self):
        with tempfile.TemporaryDirectory() as tmp:
            ausente = CacheEtiquetas(Path(tmp) / "no-existe.json")
            self.assertIsNone(ausente.buscar("C:/musica/a.mp3", 1, 2))
            vacia = Path(tmp) / "vacia.json"
            vacia.write_text("", encoding="utf-8")
            self.assertIsNone(CacheEtiquetas(vacia).buscar("C:/musica/a.mp3", 1, 2))

    def test_forma_inesperada_da_cache_vacia(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta_cache = Path(tmp) / "etiquetas_musica.json"
            for contenido in ("[1, 2]", '"texto"', '{"version": 99, "etiquetas": {}}',
                              '{"version": 1}', '{"version": 1, "etiquetas": []}'):
                with self.subTest(contenido=contenido):
                    ruta_cache.write_text(contenido, encoding="utf-8")
                    cache = CacheEtiquetas(ruta_cache)
                    self.assertIsNone(cache.buscar("C:/musica/a.mp3", 1, 2))

    def test_entradas_rotas_se_saltan_y_las_sanas_quedan(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta_cache = Path(tmp) / "etiquetas_musica.json"
            origen, mtime_ns, tamano = _archivo(tmp)
            ruta_cache.write_text(json.dumps({
                "version": 2,
                "etiquetas": {
                    origen: {"mtime_ns": mtime_ns, "tamano": tamano,
                             "titulo": "Sana", "artista": "", "album": "",
                             "duracion_ms": 5000},
                    "": {"mtime_ns": 1, "tamano": 2},
                    "C:/musica/rota.mp3": {"titulo": "Rota"},
                },
            }), encoding="utf-8")
            cache = CacheEtiquetas(ruta_cache)
            self.assertEqual(
                cache.buscar(origen, mtime_ns, tamano),
                {"titulo": "Sana", "artista": "", "album": "",
                 "duracion_ms": 5000})
            self.assertIsNone(cache.buscar("C:/musica/rota.mp3", 1, 2))

    def test_archivo_de_version_uno_se_descarta(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta_cache = Path(tmp) / "etiquetas_musica.json"
            origen, mtime_ns, tamano = _archivo(tmp)
            ruta_cache.write_text(json.dumps({
                "version": 1,
                "etiquetas": {
                    origen: {"mtime_ns": mtime_ns, "tamano": tamano,
                             "titulo": "Vieja", "artista": "", "album": ""},
                },
            }), encoding="utf-8")
            self.assertIsNone(CacheEtiquetas(ruta_cache).buscar(
                origen, mtime_ns, tamano))

    def test_normaliza_duraciones_basura_a_cero(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheEtiquetas(Path(tmp) / "etiquetas_musica.json")
            origen, mtime_ns, tamano = _archivo(tmp)
            for valor in (-1, True, False, "3000", None, 1.5):
                with self.subTest(valor=valor):
                    cache.poner(origen, mtime_ns, tamano,
                                {"titulo": "T", "duracion_ms": valor})
                    self.assertIsNone(cache.buscar(origen, mtime_ns, tamano))

    def test_normaliza_una_duracion_de_verdad_sin_tocarla(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = CacheEtiquetas(Path(tmp) / "etiquetas_musica.json")
            origen, mtime_ns, tamano = _archivo(tmp)
            cache.poner(origen, mtime_ns, tamano,
                        {"titulo": "T", "duracion_ms": 93000})
            self.assertEqual(
                cache.buscar(origen, mtime_ns, tamano)["duracion_ms"], 93000)


class TestLeerConReintento(unittest.TestCase):

    def test_falla_la_primera_y_acierta_la_segunda_con_mas_plazo(self):
        llamadas = []

        def leer(ruta, plazo_ms=1500):
            llamadas.append(plazo_ms)
            if len(llamadas) == 1:
                return {}
            return {"titulo": "Tema", "duracion_ms": 95540}

        resultado = leer_con_reintento(leer, "C:/musica/a.mp3")
        self.assertEqual(
            resultado, {"titulo": "Tema", "duracion_ms": 95540})
        self.assertEqual(llamadas, [1500, 5000])

    def test_acierta_a_la_primera_con_una_sola_llamada(self):
        llamadas = []

        def leer(ruta, plazo_ms=1500):
            llamadas.append(plazo_ms)
            return {"titulo": "Tema", "duracion_ms": 95540}

        resultado = leer_con_reintento(leer, "C:/musica/a.mp3")
        self.assertEqual(
            resultado, {"titulo": "Tema", "duracion_ms": 95540})
        self.assertEqual(llamadas, [1500])

    def test_falla_las_dos_da_diccionario_vacio(self):
        llamadas = []

        def leer(ruta, plazo_ms=1500):
            llamadas.append(plazo_ms)
            return {}

        self.assertEqual(leer_con_reintento(leer, "C:/musica/a.mp3"), {})
        self.assertEqual(llamadas, [1500, 5000])


class TestHilos(unittest.TestCase):

    def test_poner_y_buscar_desde_varios_hilos_no_rompe(self):
        import threading

        with tempfile.TemporaryDirectory() as tmp:
            ruta_cache = Path(tmp) / "etiquetas_musica.json"
            cache = CacheEtiquetas(ruta_cache)
            origen, mtime_ns, tamano = _archivo(tmp)
            errores = []

            def trabajo(n):
                try:
                    for _ in range(50):
                        cache.poner(origen, mtime_ns, tamano, {"titulo": f"T{n}"})
                        cache.buscar(origen, mtime_ns, tamano)
                except Exception as exc:  # pragma: no cover
                    errores.append(exc)

            hilos = [threading.Thread(target=trabajo, args=(n,)) for n in range(4)]
            for hilo in hilos:
                hilo.start()
            for hilo in hilos:
                hilo.join(timeout=10)
            self.assertEqual(errores, [])
            for hilo in hilos:
                self.assertFalse(hilo.is_alive())
            self.assertTrue(os.path.exists(origen))


if __name__ == "__main__":
    unittest.main()
