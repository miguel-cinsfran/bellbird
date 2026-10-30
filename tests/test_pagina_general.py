"""Pruebas de la decisión de preguntar antes de salir.

Sin ventanas: solo cubre la función pura `mensaje_confirmar_salida`, que
recibe la opción y los tres estados y devuelve el mensaje o None. El
cableado con `wx.MessageDialog` vive en `test_gui.py` y lo corre el advisor.
"""

import unittest

from bellbird.ui.confirmar_salida import mensaje_confirmar_salida


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


if __name__ == "__main__":
    unittest.main()
