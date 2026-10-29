"""Tests del anuncio corto al ajustar un valor varias veces seguidas."""

import unittest

from bellbird.core.anuncio_ajuste import AnuncioAjuste


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


if __name__ == "__main__":
    unittest.main()
