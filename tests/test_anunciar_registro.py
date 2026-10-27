"""El registro de anuncios en `accesibilidad.anunciar`, sin ventanas.

Reemplaza el lector y el hilo por dobles: no habla, no abre nada y no toca
la interfaz. Solo comprueba que cada anuncio deja una línea y una sola.
"""

import unittest
from unittest import mock

from ytchat.ui import accesibilidad
from ytchat.ui import gui


def _lineas_anuncio(registro):
    return [linea for linea in registro.output if "ANUNCIO" in linea]


class AnunciarRegistroTest(unittest.TestCase):
    def test_desde_el_hilo_principal_registra_una_sola_linea(self):
        with mock.patch.object(accesibilidad, "_lector", mock.Mock()), \
                mock.patch.object(gui.wx, "IsMainThread", return_value=True), \
                self.assertLogs("ytchat.accesibilidad", level="INFO") as registro:
            accesibilidad.anunciar("Hola")
        self.assertEqual(len(_lineas_anuncio(registro)), 1)
        self.assertIn("ANUNCIO Hola", _lineas_anuncio(registro)[0])

    def test_sin_lector_igual_registra(self):
        with mock.patch.object(accesibilidad, "_lector", None), \
                self.assertLogs("ytchat.accesibilidad", level="INFO") as registro:
            accesibilidad.anunciar("Hola")
        self.assertEqual(_lineas_anuncio(registro),
                         [registro.output[0]])
        self.assertIn("ANUNCIO sin lector Hola", registro.output[0])

    def test_el_reenvio_de_otro_hilo_no_registra_dos_veces(self):
        estados = iter([False, True])
        with mock.patch.object(accesibilidad, "_lector", mock.Mock()), \
                mock.patch.object(gui.wx, "IsMainThread",
                                  side_effect=lambda: next(estados)), \
                mock.patch.object(gui.wx, "CallAfter",
                                  side_effect=lambda fn, *a, **k: fn(*a, **k)), \
                self.assertLogs("ytchat.accesibilidad", level="INFO") as registro:
            accesibilidad.anunciar("Hola")
        self.assertEqual(len(_lineas_anuncio(registro)), 1)

    def test_sin_lector_no_toca_la_interfaz(self):
        with mock.patch.object(accesibilidad, "_lector", None), \
                mock.patch.object(gui.wx, "IsMainThread") as es_principal, \
                mock.patch.object(accesibilidad, "logger"):
            accesibilidad.anunciar("Hola")
        es_principal.assert_not_called()


if __name__ == "__main__":
    unittest.main()
