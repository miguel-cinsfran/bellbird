"""Pruebas de la memoria de la música (memoria.py), sin wx ni VLC.

Todo pasa por archivos temporales reales: la ida y vuelta y las correcciones
se comprueban contra el disco, no contra un doble.
"""

import json
import tempfile
import unittest
from pathlib import Path

from ytchat.music import memoria
from ytchat.music.modelo import EstadoMusica, Tema


def _estado(temas, posicion):
    return EstadoMusica(tuple(temas), posicion, False, False, 100, False)


class TestIdaYVuelta(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.carpeta = Path(self._tmp.name)
        self.ruta = self.carpeta / "musica_estado.json"

    def test_guarda_y_lee_cola_y_posicion(self):
        a = self.carpeta / "a.mp3"
        b = self.carpeta / "b.mp3"
        a.write_bytes(b"")
        b.write_bytes(b"")
        temas = (Tema(str(a.resolve()), "A", "Ana", "Disco"),
                 Tema(str(b.resolve()), "B"))
        memoria.guardar(self.ruta, _estado(temas, 1))
        leido = memoria.leer(self.ruta)
        self.assertIsNotNone(leido)
        vivos, posicion = leido
        self.assertEqual([t.origen for t in vivos],
                         [str(a.resolve()), str(b.resolve())])
        self.assertEqual(vivos[0].artista, "Ana")
        self.assertEqual(vivos[0].album, "Disco")
        self.assertEqual(posicion, 1)

    def test_lee_lo_que_escribio_en_disco(self):
        memoria.guardar(self.ruta, _estado((Tema("C:/m/a.mp3", "A"),), 0))
        datos = json.loads(self.ruta.read_text(encoding="utf-8"))
        self.assertEqual(datos["version"], memoria.VERSION)
        self.assertEqual(datos["temas"][0]["titulo"], "A")
        self.assertEqual(datos["posicion"], 0)

    def test_enlace_sobrevive_aunque_no_exista(self):
        temas = (Tema("https://ejemplo.test/v.mp3", "Enlace"),)
        memoria.guardar(self.ruta, _estado(temas, 0))
        vivos, posicion = memoria.leer(self.ruta)
        self.assertEqual(vivos[0].origen, "https://ejemplo.test/v.mp3")
        self.assertEqual(posicion, 0)


class TestLeerDefensivo(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.carpeta = Path(self._tmp.name)
        self.ruta = self.carpeta / "musica_estado.json"

    def _escribir(self, datos):
        self.ruta.write_text(json.dumps(datos), encoding="utf-8")

    def _archivo(self, nombre):
        ruta = self.carpeta / nombre
        ruta.write_bytes(b"")
        return str(ruta.resolve())

    def test_falta_el_archivo(self):
        self.assertIsNone(memoria.leer(self.ruta))

    def test_archivo_roto(self):
        self.ruta.write_text("esto no es json", encoding="utf-8")
        self.assertIsNone(memoria.leer(self.ruta))

    def test_version_distinta(self):
        self._escribir({"version": 2, "temas": [{"origen": "x"}], "posicion": 0})
        self.assertIsNone(memoria.leer(self.ruta))

    def test_sin_temas(self):
        self._escribir({"version": 1, "temas": [], "posicion": 0})
        self.assertIsNone(memoria.leer(self.ruta))

    def test_posicion_fuera_de_rango(self):
        self._escribir({"version": 1, "temas": [{"origen": "x"}], "posicion": 3})
        self.assertIsNone(memoria.leer(self.ruta))

    def test_posicion_negativa(self):
        self._escribir({"version": 1, "temas": [{"origen": "x"}], "posicion": -1})
        self.assertIsNone(memoria.leer(self.ruta))

    def test_posicion_no_entera(self):
        self._escribir({"version": 1, "temas": [{"origen": "x"}], "posicion": "0"})
        self.assertIsNone(memoria.leer(self.ruta))

    def test_tema_sin_origen_se_quita(self):
        a = self._archivo("a.mp3")
        self._escribir({"version": 1, "posicion": 1, "temas": [
            {"origen": a, "titulo": "A"},
            {"titulo": "sin origen"},
            {"origen": "", "titulo": "vacío"},
        ]})
        vivos, posicion = memoria.leer(self.ruta)
        self.assertEqual([t.origen for t in vivos], [a])
        self.assertEqual(posicion, 0)

    def test_archivo_borrado_se_quita_y_la_posicion_sigue_al_mismo_tema(self):
        a = self._archivo("a.mp3")
        b = self._archivo("b.mp3")
        c = self._archivo("c.mp3")
        Path(a).unlink()
        self._escribir({"version": 1, "posicion": 2, "temas": [
            {"origen": a, "titulo": "A"},
            {"origen": b, "titulo": "B"},
            {"origen": c, "titulo": "C"},
        ]})
        vivos, posicion = memoria.leer(self.ruta)
        self.assertEqual([t.origen for t in vivos], [b, c])
        self.assertEqual(posicion, 1)

    def test_tema_de_la_posicion_borrado_corrige_a_cero(self):
        a = self._archivo("a.mp3")
        b = self._archivo("b.mp3")
        c = self._archivo("c.mp3")
        Path(b).unlink()
        self._escribir({"version": 1, "posicion": 1, "temas": [
            {"origen": a, "titulo": "A"},
            {"origen": b, "titulo": "B"},
            {"origen": c, "titulo": "C"},
        ]})
        vivos, posicion = memoria.leer(self.ruta)
        self.assertEqual([t.origen for t in vivos], [a, c])
        self.assertEqual(posicion, 0)

    def test_ninguno_vivo_da_none(self):
        a = self._archivo("a.mp3")
        b = self._archivo("b.mp3")
        Path(a).unlink()
        Path(b).unlink()
        self._escribir({"version": 1, "posicion": 0, "temas": [
            {"origen": a, "titulo": "A"},
            {"origen": b, "titulo": "B"},
        ]})
        self.assertIsNone(memoria.leer(self.ruta))

    def test_entrada_no_diccionario_se_ignora(self):
        a = self._archivo("a.mp3")
        self._escribir({"version": 1, "posicion": 0, "temas": [
            "no soy un tema", {"origen": a, "titulo": "A"},
        ]})
        vivos, posicion = memoria.leer(self.ruta)
        self.assertEqual([t.origen for t in vivos], [a])
        self.assertEqual(posicion, 0)

    def test_leer_una_carpeta_no_lanza(self):
        self.assertIsNone(memoria.leer(self.carpeta))


class TestGuardarDefensivo(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.carpeta = Path(self._tmp.name)
        self.ruta = self.carpeta / "musica_estado.json"

    def test_sin_cola_borra_el_archivo(self):
        memoria.guardar(self.ruta, _estado((Tema("C:/m/a.mp3", "A"),), 0))
        self.assertTrue(self.ruta.exists())
        memoria.guardar(self.ruta, _estado((), None))
        self.assertFalse(self.ruta.exists())

    def test_sin_posicion_borra_el_archivo(self):
        memoria.guardar(self.ruta, _estado((Tema("C:/m/a.mp3", "A"),), 0))
        memoria.guardar(self.ruta, _estado((Tema("C:/m/a.mp3", "A"),), None))
        self.assertFalse(self.ruta.exists())

    def test_estado_none_borra_el_archivo(self):
        memoria.guardar(self.ruta, _estado((Tema("C:/m/a.mp3", "A"),), 0))
        memoria.guardar(self.ruta, None)
        self.assertFalse(self.ruta.exists())

    def test_borrar_sin_archivo_no_lanza(self):
        memoria.guardar(self.ruta, None)

    def test_guardar_sin_carpeta_no_lanza(self):
        from unittest import mock
        with mock.patch.object(memoria.logger, "exception"):
            memoria.guardar(self.carpeta / "no" / "existe" / "x.json",
                            _estado((Tema("C:/m/a.mp3", "A"),), 0))


if __name__ == "__main__":
    unittest.main()
