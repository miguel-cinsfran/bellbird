"""Pruebas de la identidad de la aplicación (config.APP_NAME)."""

import unittest

from guyrapu.core import config


class TestNombreApp(unittest.TestCase):
    def test_nombre_de_la_aplicacion(self):
        self.assertEqual(config.APP_NAME, "Bellbird")


if __name__ == "__main__":
    unittest.main()
