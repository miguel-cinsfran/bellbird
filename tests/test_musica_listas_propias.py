"""Pruebas de las listas propias de música (musica_listas_propias.py), sin wx."""

import tempfile
import unittest
from pathlib import Path

from bellbird.ui import musica_listas_propias


class _ControlFalso(musica_listas_propias.ListasPropiasMusica):
    """Controlador mínimo: recuerda avisos y temas sin abrir ventanas."""

    def __init__(self, carpeta):
        self._carpeta = carpeta
        self.avisos = []
        self.reproducidas = []

    def carpeta_listas(self):
        return self._carpeta

    def _avisar(self, aviso):
        self.avisos.append(aviso.texto)

    def reproducir_temas(self, temas):
        self.reproducidas.append(tuple(temas))


class TestTemasDeLista(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.carpeta = self.raiz / "listas"
        self.carpeta.mkdir()
        self.sonoro = self.raiz / "suena.mp3"
        self.sonoro.write_bytes(b"")
        self._escribir_pipo("Otra", "no-existe.mp3")

    def tearDown(self):
        self.tmp.cleanup()

    def _escribir_pipo(self, titulo, entrada):
        (self.carpeta / "pipo.m3u8").write_text(
            "#EXTM3U\n"
            "#EXTINF:-1,Don Quijote\n"
            f"{self.sonoro.resolve()}\n"
            f"#EXTINF:-1,{titulo}\n"
            f"{entrada}\n",
            encoding="utf-8")

    def test_avisa_la_primera_vez_y_no_la_segunda(self):
        control = _ControlFalso(self.carpeta)
        temas = control.temas_de_lista("pipo")
        control.temas_de_lista("pipo")
        self.assertEqual([t.titulo for t in temas], ["Don Quijote"])
        self.assertEqual(control.avisos,
                         ["No se encontró una canción de la lista: Otra"])

    def test_avisa_de_nuevo_si_cambia_lo_que_falta(self):
        control = _ControlFalso(self.carpeta)
        control.temas_de_lista("pipo")
        self._escribir_pipo("Don Quijote", "otra-que-falta.mp3")
        control.temas_de_lista("pipo")
        self.assertEqual(control.avisos, [
            "No se encontró una canción de la lista: Otra",
            "No se encontró una canción de la lista: Don Quijote",
        ])

    def test_cada_lista_lleva_su_propio_recuerdo(self):
        self._escribir_pipo("Otra", "no-existe.mp3")
        (self.carpeta / "otra.m3u8").write_text(
            "#EXTM3U\n"
            "#EXTINF:-1,Falta aquí\n"
            "tampoco-existe.mp3\n",
            encoding="utf-8")
        control = _ControlFalso(self.carpeta)
        control.temas_de_lista("pipo")
        control.temas_de_lista("otra")
        self.assertEqual(control.avisos, [
            "No se encontró una canción de la lista: Otra",
            "No se encontró una canción de la lista: Falta aquí",
        ])


class TestReproducirListaGuardada(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.carpeta = self.raiz / "listas"
        self.carpeta.mkdir()
        self.sonoro = self.raiz / "suena.mp3"
        self.sonoro.write_bytes(b"")
        (self.carpeta / "pipo.m3u8").write_text(
            "#EXTM3U\n"
            "#EXTINF:-1,Don Quijote\n"
            f"{self.sonoro.resolve()}\n"
            "#EXTINF:-1,Otra\n"
            "no-existe.mp3\n",
            encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_avisa_siempre_aunque_ya_se_haya_dicho(self):
        control = _ControlFalso(self.carpeta)
        control.reproducir_lista_guardada("pipo")
        control.reproducir_lista_guardada("pipo")
        self.assertEqual(control.avisos, [
            "No se encontró una canción de la lista: Otra",
            "No se encontró una canción de la lista: Otra",
        ])
        self.assertEqual(
            [[t.titulo for t in lote] for lote in control.reproducidas],
            [["Don Quijote"], ["Don Quijote"]])
