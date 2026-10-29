"""Pruebas de la prueba de voz, sin ventanas."""

import unittest
from unittest import mock

from tests.pseudo_prueba import con_pseudo
from bellbird.ui import prueba_voz
from bellbird.voice import escala_voz
from bellbird.voice import motor_elevenlabs
from bellbird.voice import motores


class _HiloInmediato:

    def __init__(self, target):
        self._target = target

    def start(self):
        self._target()


class _HiloQuieto:

    def start(self):
        pass


class _MotorElevenFalso:

    def __init__(self, error=None):
        self.error = error
        self.cerrado = 0
        self.dicho = None

    def voces(self):
        return ["Ana"]

    def elegir_voz(self, idx):
        self.voz = idx

    def fijar_velocidad(self, valor):
        self.velocidad = valor

    def fijar_volumen(self, valor):
        self.volumen = valor

    def hablar(self, texto):
        if self.error is not None:
            raise self.error
        self.dicho = texto

    def hablando(self):
        return False

    def cerrar(self):
        self.cerrado += 1


class TestProbarPrism(unittest.TestCase):

    def test_configura_el_motor_en_orden_y_habla(self):
        motor = mock.Mock()
        with mock.patch.object(motores, "MotorPrism", return_value=motor), \
                mock.patch.object(prueba_voz, "anunciar") as anunciar:
            prueba = prueba_voz.PruebaVoz()
            prueba.probar_prism("sapi", 2, 60, 70, 40)

        self.assertEqual(
            [llamada[0] for llamada in motor.method_calls],
            ["elegir_voz", "fijar_velocidad", "fijar_volumen", "fijar_tono",
             "hablar"])
        motor.hablar.assert_called_once_with("Así suena esta voz.")
        self.assertIs(prueba._motor_prueba, motor)
        anunciar.assert_not_called()

    def test_motor_no_disponible_anuncia(self):
        with mock.patch.object(
                motores, "MotorPrism",
                side_effect=motores.MotorNoDisponible("no")), \
                mock.patch.object(prueba_voz, "anunciar") as anunciar:
            prueba = prueba_voz.PruebaVoz()
            prueba.probar_prism("sapi", 0, 50, 50, 50)

        anunciar.assert_called_once_with(
            "No se pudo iniciar el motor de voz elegido.")
        self.assertIsNone(prueba._motor_prueba)

    def test_una_segunda_prueba_cierra_la_anterior(self):
        viejo = mock.Mock()
        nuevo = mock.Mock()
        prueba = prueba_voz.PruebaVoz()
        prueba._motor_prueba = viejo
        with mock.patch.object(motores, "MotorPrism", return_value=nuevo):
            prueba.probar_prism("sapi", 0, 50, 50, 50)

        viejo.cerrar.assert_called_once_with()
        self.assertIs(prueba._motor_prueba, nuevo)


class TestProbarElevenLabs(unittest.TestCase):

    def test_cierra_el_motor_y_libera_la_marca(self):
        motor = _MotorElevenFalso()
        anunciar = mock.Mock()
        with mock.patch.object(
                prueba_voz.wx, "CallAfter",
                side_effect=lambda funcion, *args: funcion(*args)), \
                mock.patch.object(
                    prueba_voz.diagnostico, "crear_hilo",
                    side_effect=lambda target, nombre, **kw: _HiloInmediato(target)), \
                mock.patch.object(
                    motor_elevenlabs, "MotorElevenLabs", return_value=motor), \
                mock.patch.object(escala_voz, "resolver_voz", return_value=0), \
                mock.patch.object(prueba_voz, "anunciar", anunciar):
            prueba = prueba_voz.PruebaVoz()
            prueba.probar_elevenlabs("clave", "Ana", 60, 70)

        self.assertEqual(motor.dicho, "Así suena esta voz.")
        self.assertEqual(motor.cerrado, 1)
        self.assertFalse(prueba._probando_eleven)
        anunciar.assert_not_called()

    def test_no_arranca_una_segunda_mientras_sigue_la_primera(self):
        prueba = prueba_voz.PruebaVoz()
        with mock.patch.object(
                prueba_voz.diagnostico, "crear_hilo",
                return_value=_HiloQuieto()) as crear:
            prueba.probar_elevenlabs("clave", "Ana", 60, 70)
            prueba.probar_elevenlabs("clave", "Ana", 60, 70)

        self.assertEqual(crear.call_count, 1)
        self.assertTrue(prueba._probando_eleven)

    def test_un_error_se_anuncia_con_su_texto(self):
        motor = _MotorElevenFalso(error=RuntimeError("falla de prueba"))
        anunciar = mock.Mock()
        with mock.patch.object(
                prueba_voz.wx, "CallAfter",
                side_effect=lambda funcion, *args: funcion(*args)), \
                mock.patch.object(
                    prueba_voz.diagnostico, "crear_hilo",
                    side_effect=lambda target, nombre, **kw: _HiloInmediato(target)), \
                mock.patch.object(
                    motor_elevenlabs, "MotorElevenLabs", return_value=motor), \
                mock.patch.object(escala_voz, "resolver_voz", return_value=0), \
                mock.patch.object(prueba_voz, "anunciar", anunciar):
            prueba = prueba_voz.PruebaVoz()
            prueba.probar_elevenlabs("clave", "Ana", 60, 70)

        anunciar.assert_called_once_with("falla de prueba")
        self.assertEqual(motor.cerrado, 1)
        self.assertFalse(prueba._probando_eleven)


class TestPseudoTextos(unittest.TestCase):
    """Bajo pseudotraducción, cada frase al usuario sale marcada."""

    def test_prism_habla_y_anuncia_marcado(self):
        motor = mock.Mock()
        with con_pseudo():
            with mock.patch.object(motores, "MotorPrism", return_value=motor):
                prueba = prueba_voz.PruebaVoz()
                prueba.probar_prism("sapi", 2, 60, 70, 40)
        motor.hablar.assert_called_once()
        self.assertTrue(motor.hablar.call_args.args[0].startswith("[¡"),
                        motor.hablar.call_args.args[0])

    def test_prism_sin_motor_anuncia_marcado(self):
        with con_pseudo():
            with mock.patch.object(
                    motores, "MotorPrism",
                    side_effect=motores.MotorNoDisponible("no")), \
                    mock.patch.object(prueba_voz, "anunciar") as anunciar:
                prueba = prueba_voz.PruebaVoz()
                prueba.probar_prism("sapi", 0, 50, 50, 50)
        anunciar.assert_called_once()
        self.assertTrue(anunciar.call_args.args[0].startswith("[¡"),
                        anunciar.call_args.args[0])


class TestCerrar(unittest.TestCase):

    def test_sin_motor_no_hace_nada(self):
        prueba = prueba_voz.PruebaVoz()
        prueba.cerrar()
        self.assertIsNone(prueba._motor_prueba)

    def test_con_motor_lo_cierra_una_sola_vez(self):
        motor = mock.Mock()
        prueba = prueba_voz.PruebaVoz()
        prueba._motor_prueba = motor
        prueba.cerrar()
        prueba.cerrar()
        motor.cerrar.assert_called_once_with()
        self.assertIsNone(prueba._motor_prueba)
