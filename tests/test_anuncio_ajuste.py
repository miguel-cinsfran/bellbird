"""Tests del anuncio corto al ajustar un valor varias veces seguidas."""

import unittest
from unittest import mock

from bellbird.core import anuncio_ajuste
from bellbird.core.anuncio_ajuste import AnuncioAjuste, con_limite


class RelojFalso:
    def __init__(self):
        self.hora = 1000.0

    def __call__(self):
        return self.hora

    def avanzar(self, segundos):
        self.hora += segundos


class TestAnuncioAjuste(unittest.TestCase):

    def test_primera_vez_completa(self):
        reloj = RelojFalso()
        ajuste = AnuncioAjuste(reloj=reloj)
        self.assertEqual(
            ajuste.frase("volumen_voz", "Volumen de la voz: 40%", "40%"),
            "Volumen de la voz: 40%")

    def test_mismo_control_a_los_diez_segundos_corta(self):
        reloj = RelojFalso()
        ajuste = AnuncioAjuste(reloj=reloj)
        ajuste.frase("volumen_voz", "Volumen de la voz: 40%", "40%")
        reloj.avanzar(10)
        self.assertEqual(
            ajuste.frase("volumen_voz", "Volumen de la voz: 45%", "45%"),
            "45%")

    def test_mismo_control_a_los_sesenta_y_un_segundos_completa(self):
        reloj = RelojFalso()
        ajuste = AnuncioAjuste(reloj=reloj)
        ajuste.frase("volumen_voz", "Volumen de la voz: 40%", "40%")
        reloj.avanzar(61)
        self.assertEqual(
            ajuste.frase("volumen_voz", "Volumen de la voz: 45%", "45%"),
            "Volumen de la voz: 45%")

    def test_otro_control_en_medio_vuelve_a_completa(self):
        reloj = RelojFalso()
        ajuste = AnuncioAjuste(reloj=reloj)
        ajuste.frase("volumen_voz", "Volumen de la voz: 40%", "40%")
        reloj.avanzar(10)
        self.assertEqual(
            ajuste.frase("velocidad_voz", "Velocidad de la voz: +3", "+3"),
            "Velocidad de la voz: +3")

    def test_volver_al_primero_tras_otro_completa(self):
        reloj = RelojFalso()
        ajuste = AnuncioAjuste(reloj=reloj)
        ajuste.frase("volumen_voz", "Volumen de la voz: 40%", "40%")
        reloj.avanzar(10)
        ajuste.frase("velocidad_voz", "Velocidad de la voz: +3", "+3")
        reloj.avanzar(10)
        self.assertEqual(
            ajuste.frase("volumen_voz", "Volumen de la voz: 45%", "45%"),
            "Volumen de la voz: 45%")

    def test_registrar_hace_corto_al_siguiente(self):
        reloj = RelojFalso()
        ajuste = AnuncioAjuste(reloj=reloj)
        ajuste.registrar("volumen_reproductor")
        self.assertEqual(
            ajuste.frase("volumen_reproductor",
                         "Volumen del reproductor: 40 por ciento",
                         "40 por ciento"),
            "40 por ciento")


class TestConLimite(unittest.TestCase):

    def test_en_el_maximo_agrega_maximo(self):
        self.assertEqual(
            con_limite("Volumen de la voz: 100%", 100, 0, 100),
            "Volumen de la voz: 100%, máximo")

    def test_en_el_minimo_agrega_minimo(self):
        self.assertEqual(
            con_limite("Volumen de la voz: 0%", 0, 0, 100),
            "Volumen de la voz: 0%, mínimo")

    def test_en_el_medio_no_cambia(self):
        self.assertEqual(
            con_limite("Volumen de la voz: 50%", 50, 0, 100),
            "Volumen de la voz: 50%")


class TestAnuncioVelocidad(unittest.TestCase):

    def test_en_el_maximo_dice_maximo_completo_y_corto(self):
        with mock.patch.object(anuncio_ajuste, "COMPARTIDO", AnuncioAjuste()):
            self.assertEqual(anuncio_ajuste.anuncio_velocidad(100),
                             "Velocidad de la voz: 100, máximo")
            self.assertEqual(anuncio_ajuste.anuncio_velocidad(100),
                             "100, máximo")

    def test_fuera_del_tope_no_cambia(self):
        with mock.patch.object(anuncio_ajuste, "COMPARTIDO", AnuncioAjuste()):
            self.assertEqual(anuncio_ajuste.anuncio_velocidad(50),
                             "Velocidad de la voz: 50")
            self.assertEqual(anuncio_ajuste.anuncio_velocidad(50), "50")


class TestAnuncioVolumen(unittest.TestCase):

    def test_en_el_minimo_dice_minimo_completo_y_corto(self):
        with mock.patch.object(anuncio_ajuste, "COMPARTIDO", AnuncioAjuste()):
            self.assertEqual(anuncio_ajuste.anuncio_volumen(0),
                             "Volumen de la voz: 0%, mínimo")
            self.assertEqual(anuncio_ajuste.anuncio_volumen(0), "0%, mínimo")

    def test_fuera_del_tope_no_cambia(self):
        with mock.patch.object(anuncio_ajuste, "COMPARTIDO", AnuncioAjuste()):
            self.assertEqual(anuncio_ajuste.anuncio_volumen(50),
                             "Volumen de la voz: 50%")
            self.assertEqual(anuncio_ajuste.anuncio_volumen(50), "50%")


if __name__ == "__main__":
    unittest.main()
