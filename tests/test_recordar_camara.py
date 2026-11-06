"""Pruebas de recordar el nombre nuevo de la cámara en Preferencias."""

import unittest
from types import SimpleNamespace
from unittest import mock

from guyrapu.ui import preferencias_camara


class RecordarCambioDeNombreTest(unittest.TestCase):

    def test_si_era_la_camara_actualiza_la_configuracion_y_la_guarda(self):
        principal = SimpleNamespace(_config={"camara_fuente": "Cam"})
        guardar = mock.Mock()
        self.assertTrue(preferencias_camara.recordar_cambio_de_nombre(
            principal, "Cam", "Cámara nueva", guardar))
        self.assertEqual(principal._config["camara_fuente"], "Cámara nueva")
        guardar.assert_called_once_with(
            "transmision", "camara_fuente", "Cámara nueva")

    def test_si_no_era_la_camara_no_cambia_ni_guarda(self):
        principal = SimpleNamespace(_config={"camara_fuente": "Otra"})
        guardar = mock.Mock()
        self.assertFalse(preferencias_camara.recordar_cambio_de_nombre(
            principal, "Cam", "Cámara nueva", guardar))
        self.assertEqual(principal._config["camara_fuente"], "Otra")
        guardar.assert_not_called()

    def test_si_falla_el_guardado_igual_deja_el_nombre_nuevo(self):
        principal = SimpleNamespace(_config={"camara_fuente": "Cam"})
        guardar = mock.Mock(side_effect=OSError("sin disco"))
        with self.assertLogs(preferencias_camara.logger, level="WARNING"):
            self.assertTrue(preferencias_camara.recordar_cambio_de_nombre(
                principal, "Cam", "Cámara nueva", guardar))
        self.assertEqual(principal._config["camara_fuente"], "Cámara nueva")
