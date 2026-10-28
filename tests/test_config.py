"""Pruebas de la identidad de la aplicación (config.APP_NAME)."""

import unittest

from ytchat.core import config


class TestNombreApp(unittest.TestCase):
    def test_app_name_es_bellbird(self):
        self.assertEqual(config.APP_NAME, "Bellbird")


if __name__ == "__main__":
    unittest.main()
