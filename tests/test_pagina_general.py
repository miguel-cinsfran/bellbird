"""Pruebas de la decisión de preguntar antes de salir.

Sin ventanas: solo cubre las funciones puras `mensaje_confirmar_salida`,
`descargas_sin_terminar` y `mensaje_con_descargas`. El cableado con
`wx.MessageDialog` vive en `test_gui.py` y lo corre el advisor.
"""

import unittest
from types import SimpleNamespace

from bellbird.ui.confirmar_salida import (
    descargas_sin_terminar, mensaje_confirmar_salida, mensaje_con_descargas)


class TestMensajeConfirmarSalida(unittest.TestCase):

    def test_con_chat_conectado_pregunta_por_el_chat(self):
        self.assertEqual(
            mensaje_confirmar_salida(True, True, False, False),
            "¿Salir de la aplicación? Hay un chat conectado.")

    def test_con_supervisor_activo_pregunta_por_la_transmision(self):
        self.assertEqual(
            mensaje_confirmar_salida(True, False, True, False),
            "¿Salir de la aplicación? Hay una transmisión en curso.")

    def test_con_obs_transmitiendo_pregunta_por_la_transmision(self):
        self.assertEqual(
            mensaje_confirmar_salida(True, False, False, True),
            "¿Salir de la aplicación? Hay una transmisión en curso.")

    def test_con_chat_y_transmision_nombra_los_dos(self):
        self.assertEqual(
            mensaje_confirmar_salida(True, True, True, True),
            "¿Salir de la aplicación? Hay un chat conectado y una "
            "transmisión en curso.")

    def test_sin_nada_activo_no_pregunta(self):
        self.assertIsNone(mensaje_confirmar_salida(True, False, False, False))

    def test_con_opcion_desactivada_no_pregunta_aunque_haya_actividad(self):
        self.assertIsNone(mensaje_confirmar_salida(False, True, True, True))


class TestDescargasSinTerminar(unittest.TestCase):

    def test_cuenta_en_cola_y_descargando_e_ignora_el_resto(self):
        items = [SimpleNamespace(estado="en_cola"),
                 SimpleNamespace(estado="descargando"),
                 SimpleNamespace(estado="completado"),
                 SimpleNamespace(estado="parcial"),
                 SimpleNamespace(estado="cancelado"),
                 SimpleNamespace(estado="error")]
        self.assertEqual(descargas_sin_terminar(items), 2)

    def test_sin_items_devuelve_cero(self):
        self.assertEqual(descargas_sin_terminar([]), 0)


class TestMensajeConDescargas(unittest.TestCase):

    def test_con_cero_deja_el_mensaje_sin_tocar(self):
        mensaje = "¿Salir de la aplicación? Hay un chat conectado."
        self.assertEqual(mensaje_con_descargas(mensaje, 0), mensaje)
        self.assertIsNone(mensaje_con_descargas(None, 0))

    def test_con_una_agrega_la_frase_en_singular(self):
        self.assertEqual(
            mensaje_con_descargas("¿Salir de la aplicación?", 1),
            "¿Salir de la aplicación? Hay 1 descarga sin terminar y "
            "se cancelará.")
        self.assertEqual(
            mensaje_con_descargas(None, 1),
            "¿Salir de la aplicación? Hay 1 descarga sin terminar y "
            "se cancelará.")

    def test_con_varias_agrega_la_frase_en_plural(self):
        self.assertEqual(
            mensaje_con_descargas("¿Salir de la aplicación?", 3),
            "¿Salir de la aplicación? Hay 3 descargas sin terminar y "
            "se cancelarán.")
        self.assertEqual(
            mensaje_con_descargas(None, 3),
            "¿Salir de la aplicación? Hay 3 descargas sin terminar y "
            "se cancelarán.")


if __name__ == "__main__":
    unittest.main()
