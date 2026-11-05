"""Cuándo un mensaje de ElevenLabs cae a Windows y cuándo se avisa.

Cubre `guyrapu/voice/caida_elevenlabs.py` sin motor. La clase solo recibe
valores y caracteres usados.
"""

import unittest
from unittest import mock

from guyrapu.voice import caida_elevenlabs
from guyrapu.voice.caida_elevenlabs import CaidaElevenLabs


class TestDecision(unittest.TestCase):
    def test_de_fabrica_no_limita_ni_reserva(self):
        caida = CaidaElevenLabs()
        self.assertEqual(caida.tope, 0)
        self.assertFalse(caida.solo_importantes)
        self.assertEqual(caida.elegir(False, 1000, 1000), (False, ""))

    def test_tope_negativo_queda_en_cero(self):
        self.assertEqual(CaidaElevenLabs(tope=-5).tope, 0)

    def test_solo_importantes_manda_lo_comun_al_respaldo(self):
        caida = CaidaElevenLabs(solo_importantes=True)
        self.assertEqual(caida.elegir(False, 0, 10), (True, ""))

    def test_lo_importante_va_a_la_nube(self):
        caida = CaidaElevenLabs(solo_importantes=True)
        self.assertEqual(caida.elegir(True, 0, 10), (False, ""))

    def test_tope_manda_al_respaldo_y_avisa_una_sola_vez(self):
        caida = CaidaElevenLabs(tope=10)
        usar, aviso = caida.elegir(False, 5, 10)
        self.assertTrue(usar)
        self.assertIn("límite de caracteres", aviso)
        self.assertEqual(caida.elegir(False, 5, 10), (True, ""))

    def test_justo_en_el_tope_pasa(self):
        caida = CaidaElevenLabs(tope=10)
        self.assertEqual(caida.elegir(False, 0, 10), (False, ""))


class TestFallo(unittest.TestCase):
    def test_fallo_avisa_una_vez_por_racha(self):
        caida = CaidaElevenLabs()
        aviso = caida.fallo("sin red")
        self.assertIn("sin red", aviso)
        self.assertIn("Se usa la voz de Windows", aviso)
        self.assertIsNone(caida.fallo("sin red"))

    def test_exito_cierra_la_racha(self):
        caida = CaidaElevenLabs()
        caida.fallo("sin red")
        caida.exito()
        self.assertIn("Se usa la voz de Windows", caida.fallo("sin red"))

    def test_error_reciente_manda_al_respaldo_sin_avisar(self):
        caida = CaidaElevenLabs()
        caida.fallo("sin red")
        self.assertTrue(caida.error_reciente())
        self.assertEqual(caida.elegir(False, 0, 10), (True, ""))

    def test_error_viejo_no_manda_al_respaldo(self):
        caida = CaidaElevenLabs()
        with mock.patch.object(caida_elevenlabs.time, "monotonic",
                               side_effect=[100.0, 100.0, 200.0]):
            caida.fallo("sin red")
            self.assertTrue(caida.error_reciente())
            self.assertFalse(caida.error_reciente())
        self.assertEqual(caida.elegir(False, 0, 10), (False, ""))

    def test_exito_no_repite_el_aviso_del_tope(self):
        caida = CaidaElevenLabs(tope=10)
        caida.elegir(False, 5, 10)
        caida.exito()
        self.assertEqual(caida.elegir(False, 5, 10), (True, ""))


class TestConfigurar(unittest.TestCase):
    def test_configurar_actualiza_tope_y_solo_importantes(self):
        caida = CaidaElevenLabs()
        caida.configurar(5, True)
        self.assertEqual(caida.tope, 5)
        self.assertTrue(caida.solo_importantes)
        self.assertEqual(caida.elegir(False, 0, 1), (True, ""))

    def test_configurar_tope_raro_conserva_el_anterior(self):
        caida = CaidaElevenLabs(tope=10)
        caida.configurar("raro", False)
        self.assertEqual(caida.tope, 10)


if __name__ == "__main__":
    unittest.main()
