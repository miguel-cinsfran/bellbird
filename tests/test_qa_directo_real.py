"""Pruebas de la lógica pura de qa/directo_real.py, sin red ni ventanas."""

import importlib.util
import unittest
from pathlib import Path

_RUTA = Path(__file__).resolve().parent.parent / "qa" / "directo_real.py"
_paquete = importlib.util.spec_from_file_location(
    "directo_real_qa", _RUTA)
directo_real = importlib.util.module_from_spec(_paquete)
_paquete.loader.exec_module(directo_real)


class TestArmarTitulo(unittest.TestCase):

    def test_con_hora(self):
        self.assertEqual(directo_real.armar_titulo("20:15"),
                         "Prueba de YTChat 20:15")

    def test_sin_hora_no_deja_basura(self):
        self.assertEqual(directo_real.armar_titulo("  "), "Prueba de YTChat")


class TestEsBorrable(unittest.TestCase):

    def test_lo_propio_no_listado_se_borra(self):
        self.assertTrue(directo_real.es_borrable(
            "Prueba de YTChat 20:15", "unlisted"))

    def test_exige_privacidad_no_listada(self):
        self.assertFalse(directo_real.es_borrable(
            "Prueba de YTChat 20:15", "public"))
        self.assertFalse(directo_real.es_borrable(
            "Prueba de YTChat 20:15", "private"))
        self.assertFalse(directo_real.es_borrable(
            "Prueba de YTChat 20:15", ""))

    def test_exige_titulo_de_la_prueba(self):
        self.assertFalse(directo_real.es_borrable(
            "Mi directo", "unlisted"))
        self.assertFalse(directo_real.es_borrable("", "unlisted"))


class TestExtraerIdVideo(unittest.TestCase):

    def test_url_watch(self):
        self.assertEqual(directo_real.extraer_id_video(
            "mira https://www.youtube.com/watch?v=AbC123_-xYz y más"),
            "AbC123_-xYz")

    def test_url_corta(self):
        self.assertEqual(directo_real.extraer_id_video(
            "salió en https://youtu.be/AbC123_-xYz"),
            "AbC123_-xYz")

    def test_sin_id_da_vacio(self):
        self.assertEqual(directo_real.extraer_id_video(
            "Tu directo de YouTube ya está al aire."), "")
        self.assertEqual(directo_real.extraer_id_video(""), "")


class TestPrimerFaltante(unittest.TestCase):

    def test_todo_presente_da_none(self):
        anuncios = "ya está al aire, conectado al directo, transmisión detenida"
        self.assertIsNone(directo_real.primer_faltante(
            anuncios, ["ya está al aire", "conectado al directo"]))

    def test_devuelve_el_primer_paso_fallido(self):
        anuncios = "ya está al aire"
        self.assertEqual(directo_real.primer_faltante(
            anuncios, ["ya está al aire", "conectado al directo",
                       "transmisión detenida"]),
            "conectado al directo")

    def test_no_importan_mayusculas(self):
        self.assertIsNone(directo_real.primer_faltante(
            "YA ESTÁ AL AIRE", ["ya está al aire"]))


class TestDecidirCerrarObs(unittest.TestCase):

    def test_si_estaba_abierto_no_se_cierra(self):
        self.assertFalse(directo_real.decidir_cerrar_obs(True))

    def test_si_lo_abrio_la_app_se_cierra(self):
        self.assertTrue(directo_real.decidir_cerrar_obs(False))


class TestLeerValor(unittest.TestCase):

    def test_lista_devuelve_lo_elegido(self):
        class Lista:
            def selected_text(self):
                return "YouTube"

            def get_value(self):
                return ""

            def window_text(self):
                return "Transmitir a"

        self.assertEqual(directo_real._leer_valor(Lista()), "YouTube")

    def test_si_no_hay_elegido_usa_get_value(self):
        class ListaVacia:
            def selected_text(self):
                return ""

            def get_value(self):
                return "unlisted"

            def window_text(self):
                return "Privacidad"

        self.assertEqual(
            directo_real._leer_valor(ListaVacia()), "unlisted")

    def test_sin_selected_text_usa_get_value(self):
        class Campo:
            def get_value(self):
                return "mi título"

            def window_text(self):
                return "mi título"

        self.assertEqual(directo_real._leer_valor(Campo()), "mi título")

    def test_si_todo_vacio_usa_window_text(self):
        class Roto:
            def selected_text(self):
                return None

            def get_value(self):
                raise RuntimeError("sin valor")

            def window_text(self):
                return "texto"

        self.assertEqual(directo_real._leer_valor(Roto()), "texto")


if __name__ == "__main__":
    unittest.main()
