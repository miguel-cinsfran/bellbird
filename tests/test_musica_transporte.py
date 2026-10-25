"""Pruebas de silencio y saltos de diez segundos del coordinador."""

import unittest

from ytchat.music.coordinador import Coordinador
from ytchat.music.modelo import (
    ERROR_MOTOR, OK, SIN_TEMA,
)
from tests.test_musica_coordinador import AdaptadorFalso, tema


class AdaptadorConVolumen(AdaptadorFalso):
    """Como el adaptador real, recuerda y reaplica el volumen al cargar."""

    def __init__(self, volumen=70):
        super().__init__()
        self.volumen_actual = volumen

    def cargar(self, tema, ficha, volumen=None):
        super().cargar(tema, ficha, volumen)
        self.volumen(self.volumen_actual)

    def volumen(self, valor):
        super().volumen(valor)
        self.volumen_actual = valor


class TestSilencio(unittest.TestCase):

    def test_fijar_silencio_manda_cero_y_no_cambia_el_volumen_guardado(self):
        ad = AdaptadorConVolumen()
        c = Coordinador(ad, volumen=70)
        self.assertTrue(c.fijar_silencio(True).ok)
        self.assertTrue(c.silenciado)
        self.assertEqual(ad.llamadas[-1], ("volumen", 0))
        self.assertTrue(c.fijar_silencio(False).ok)
        self.assertFalse(c.silenciado)
        self.assertEqual(ad.llamadas[-1], ("volumen", 70))

    def test_el_silencio_sobrevive_al_cambio_de_tema(self):
        ad = AdaptadorConVolumen()
        c = Coordinador(ad, volumen=70)
        c.reproducir_lista([tema("a"), tema("b")])
        c.fijar_silencio(True)
        c.siguiente()
        self.assertTrue(c.silenciado)
        self.assertEqual(ad.volumen_actual, 0)

    def test_subir_o_bajar_el_volumen_quita_el_silencio(self):
        ad = AdaptadorConVolumen()
        c = Coordinador(ad, volumen=70)
        c.fijar_silencio(True)
        c.fijar_volumen(55)
        self.assertFalse(c.silenciado)
        self.assertEqual(ad.volumen_actual, 55)

    def test_un_fallo_del_motor_deja_el_estado_como_estaba(self):
        class Fallon(AdaptadorFalso):
            def volumen(self, valor):
                raise RuntimeError("fallo simulado")

        c = Coordinador(Fallon())
        self.assertEqual(c.fijar_silencio(True).codigo, ERROR_MOTOR)
        self.assertFalse(c.silenciado)


class TestSaltar(unittest.TestCase):

    def _con_tema(self, duracion_ms=120_000, posicion=30_000):
        ad = AdaptadorFalso()
        ad.tiempo = posicion
        c = Coordinador(ad)
        c.reproducir_lista([tema("a", duracion_ms=duracion_ms)])
        return c, ad

    def test_adelantar_suma_diez_segundos(self):
        c, ad = self._con_tema()
        salto = c.saltar(10_000)
        self.assertTrue(salto.ok)
        self.assertEqual(salto.codigo, OK)
        self.assertEqual(salto.posicion_ms, 40_000)
        self.assertIn(("ir_a", 40_000), ad.llamadas)

    def test_retroceder_no_baja_de_cero(self):
        c, ad = self._con_tema(posicion=3_000)
        salto = c.saltar(-10_000)
        self.assertTrue(salto.ok)
        self.assertEqual(salto.posicion_ms, 0)

    def test_adelantar_no_pasa_del_final_menos_un_segundo(self):
        c, ad = self._con_tema(duracion_ms=120_000, posicion=115_000)
        salto = c.saltar(10_000)
        self.assertEqual(salto.posicion_ms, 119_000)

    def test_sin_tema_no_hay_salto(self):
        c = Coordinador(AdaptadorFalso())
        salto = c.saltar(10_000)
        self.assertEqual(salto.codigo, SIN_TEMA)
        self.assertFalse(salto.ok)
        self.assertIsNone(salto.posicion_ms)

    def test_sin_duracion_no_recorta(self):
        c, ad = self._con_tema(duracion_ms=0, posicion=30_000)
        self.assertEqual(c.saltar(10_000).posicion_ms, 40_000)

    def test_el_salto_no_reanuda_la_pausa(self):
        c, _ad = self._con_tema()
        c.alternar_pausa()
        c.saltar(10_000)
        self.assertTrue(c.estado().pausado)

    def test_si_el_motor_falla_devuelve_error(self):
        class Fallon(AdaptadorFalso):
            def ir_a(self, ms):
                raise RuntimeError("fallo simulado")

        ad = Fallon()
        ad.tiempo = 30_000
        c = Coordinador(ad)
        c.reproducir_lista([tema("a", duracion_ms=120_000)])
        salto = c.saltar(10_000)
        self.assertEqual(salto.codigo, ERROR_MOTOR)
        self.assertIsNone(salto.posicion_ms)


if __name__ == "__main__":
    unittest.main()
