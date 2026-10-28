"""Pruebas de la búsqueda y el primer plano de la ventana de OBS."""

import unittest

from ytchat.obs import obs_ventana


class TestMostrar(unittest.TestCase):

    def test_sin_ventana_avisa_que_obs_no_esta_abierto(self):
        self.assertEqual(
            obs_ventana.mostrar(buscar=lambda: None),
            obs_ventana.TEXTO_SIN_OBS)

    def test_ventana_traida_no_devuelve_texto(self):
        self.assertEqual(
            obs_ventana.mostrar(buscar=lambda: 1234, traer=lambda h: True),
            "")

    def test_ventana_no_traida_avisa_el_fallo(self):
        vistos = []
        self.assertEqual(
            obs_ventana.mostrar(
                buscar=lambda: 5678,
                traer=lambda h: vistos.append(h) or False),
            obs_ventana.TEXTO_SIN_FRENTE)
        self.assertEqual(vistos, [5678])

    def test_buscar_que_lanza_cuenta_como_no_encontrado(self):
        def buscar():
            raise OSError("fallo de ctypes")

        self.assertEqual(
            obs_ventana.mostrar(buscar=buscar),
            obs_ventana.TEXTO_SIN_OBS)


class TestBuscarVentanaReal(unittest.TestCase):

    def test_buscar_ventana_no_lanza_y_da_none_o_entero(self):
        resultado = obs_ventana.buscar_ventana()
        self.assertTrue(resultado is None or isinstance(resultado, int))


if __name__ == "__main__":
    unittest.main()
