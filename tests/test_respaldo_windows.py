"""La voz de Windows de respaldo: su motor, su voz y sus ajustes.

Cubre `bellbird/voice/respaldo_windows.py` con motores dobles. Sin ventanas ni
motores reales.
"""

import unittest

from bellbird.voice import motores
from bellbird.voice.respaldo_windows import Respaldo


class MotorFalso:
    """Doble de motor SAPI que recuerda voz, ajustes y cierre."""

    def __init__(self, voces=("Voz A", "Voz B")):
        self._voces = list(voces)
        self.elegidas = []
        self.velocidad = self.volumen = self.tono = None
        self.cerrado = False

    def voces(self):
        return list(self._voces)

    def elegir_voz(self, idx):
        self.elegidas.append(idx)
        return True

    def fijar_velocidad(self, pct):
        self.velocidad = pct

    def fijar_volumen(self, pct):
        self.volumen = pct

    def fijar_tono(self, pct):
        self.tono = pct

    def cerrar(self):
        self.cerrado = True


class Fabrica:
    """Crea un motor nuevo en cada pedido y anota los nombres pedidos."""

    def __init__(self, voces=("Voz A", "Voz B"), falla=False):
        self.voces = list(voces)
        self.falla = falla
        self.creados = []
        self.motores = []

    def __call__(self, nombre):
        self.creados.append(nombre)
        if self.falla:
            raise motores.MotorNoDisponible("sapi no disponible")
        motor = MotorFalso(self.voces)
        self.motores.append(motor)
        return motor


class TestCreacion(unittest.TestCase):
    def test_crea_el_motor_la_primera_vez(self):
        fabrica = Fabrica()
        respaldo = Respaldo(fabrica, "Voz B", 40, 50, 30)
        motor = respaldo.conseguir()
        self.assertEqual(fabrica.creados, ["sapi"])
        self.assertIs(respaldo.motor, motor)
        self.assertEqual(motor.elegidas, [1])
        self.assertEqual((motor.velocidad, motor.volumen, motor.tono),
                         (40, 50, 30))

    def test_no_recrea_si_ya_existe(self):
        fabrica = Fabrica()
        respaldo = Respaldo(fabrica)
        motor = respaldo.conseguir()
        self.assertIs(respaldo.conseguir(), motor)
        self.assertEqual(len(fabrica.creados), 1)

    def test_voz_inexistente_usa_la_primera(self):
        fabrica = Fabrica()
        motor = Respaldo(fabrica, "No existe").conseguir()
        self.assertEqual(motor.elegidas, [0])

    def test_voz_vacia_usa_la_primera(self):
        fabrica = Fabrica()
        motor = Respaldo(fabrica, "").conseguir()
        self.assertEqual(motor.elegidas, [0])

    def test_sin_voces_cierra_y_devuelve_none(self):
        fabrica = Fabrica(voces=())
        respaldo = Respaldo(fabrica)
        self.assertIsNone(respaldo.conseguir())
        self.assertIsNone(respaldo.motor)
        self.assertTrue(fabrica.motores[0].cerrado)

    def test_fabrica_que_falla_devuelve_none(self):
        respaldo = Respaldo(Fabrica(falla=True))
        self.assertIsNone(respaldo.conseguir())


class TestAjustes(unittest.TestCase):
    def test_los_ajustes_de_conseguir_valen_al_crear(self):
        fabrica = Fabrica()
        motor = Respaldo(fabrica, "", 10, 20, 30).conseguir()
        self.assertEqual((motor.velocidad, motor.volumen, motor.tono),
                         (10, 20, 30))

    def test_los_ajustes_de_conseguir_no_cambian_un_motor_creado(self):
        fabrica = Fabrica()
        respaldo = Respaldo(fabrica, "", 10, 20, 30)
        motor = respaldo.conseguir()
        respaldo.conseguir(90, 90, 90)
        self.assertEqual((motor.velocidad, motor.volumen, motor.tono),
                         (10, 20, 30))

    def test_fijar_ajustes_en_caliente(self):
        fabrica = Fabrica()
        respaldo = Respaldo(fabrica)
        motor = respaldo.conseguir()
        respaldo.fijar_ajustes(20, 30, 40)
        self.assertEqual((motor.velocidad, motor.volumen, motor.tono),
                         (20, 30, 40))

    def test_fijar_ajustes_antes_de_crear_se_aplican_al_crear(self):
        fabrica = Fabrica()
        respaldo = Respaldo(fabrica)
        respaldo.fijar_ajustes(20, 30, 40)
        motor = respaldo.conseguir()
        self.assertEqual((motor.velocidad, motor.volumen, motor.tono),
                         (20, 30, 40))


class TestVozEnCaliente(unittest.TestCase):
    def test_cambiar_voz_en_caliente(self):
        fabrica = Fabrica()
        respaldo = Respaldo(fabrica, "Voz A")
        motor = respaldo.conseguir()
        motor.elegidas.clear()
        respaldo.cambiar_voz("Voz B")
        self.assertEqual(motor.elegidas, [1])
        self.assertEqual(len(fabrica.creados), 1)

    def test_cambiar_voz_antes_de_crear_se_usa_al_crear(self):
        fabrica = Fabrica()
        respaldo = Respaldo(fabrica)
        respaldo.cambiar_voz("Voz B")
        motor = respaldo.conseguir()
        self.assertEqual(motor.elegidas, [1])

    def test_cambiar_a_la_misma_voz_no_vuelve_a_elegir(self):
        fabrica = Fabrica()
        respaldo = Respaldo(fabrica, "Voz A")
        motor = respaldo.conseguir()
        motor.elegidas.clear()
        respaldo.cambiar_voz("Voz A")
        self.assertEqual(motor.elegidas, [])


class TestCierre(unittest.TestCase):
    def test_cerrar_cierra_y_permite_crear_otro(self):
        fabrica = Fabrica()
        respaldo = Respaldo(fabrica)
        motor = respaldo.conseguir()
        respaldo.cerrar()
        self.assertTrue(motor.cerrado)
        self.assertIsNone(respaldo.motor)
        self.assertIsNot(respaldo.conseguir(), motor)
        self.assertEqual(len(fabrica.creados), 2)


if __name__ == "__main__":
    unittest.main()
