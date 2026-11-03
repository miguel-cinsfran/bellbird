"""Pruebas del resumen del estado de la grabación, sin wx."""

import unittest

from bellbird.obs import estado_grabacion


def _resumir(**cambios):
    datos = {
        "grabacion": {"outputActive": False, "outputPaused": False,
                      "outputTimecode": "00:00:00.000"},
        "transmision": {"outputActive": False},
        "escena": "Principal",
        "microfono": "Mic/Aux",
        "silenciado": False,
    }
    datos.update(cambios)
    return estado_grabacion.resumir(**datos)


class TestTitular(unittest.TestCase):

    def test_grabando_con_el_tiempo_sin_milesimas(self):
        estado = _resumir(grabacion={
            "outputActive": True, "outputPaused": False,
            "outputTimecode": "00:01:02.500"})
        self.assertEqual(estado.titular, "Grabando, 00:01:02")
        self.assertEqual(estado.tono, "activo")

    def test_en_pausa_con_el_tiempo_y_tono_aviso(self):
        estado = _resumir(grabacion={
            "outputActive": True, "outputPaused": True,
            "outputTimecode": "00:02:03.500"})
        self.assertEqual(estado.titular, "Grabación en pausa, 00:02:03")
        self.assertEqual(estado.tono, "aviso")

    def test_sin_grabar(self):
        estado = _resumir()
        self.assertEqual(estado.titular, "Sin grabar")
        self.assertEqual(estado.tono, "listo")


class TestLineas(unittest.TestCase):

    def test_escena_y_microfono_sin_la_linea_de_transmision(self):
        estado = _resumir()
        self.assertEqual(estado.lineas, (
            "Escena actual: Principal",
            "Micrófono Mic/Aux: activado",
        ))

    def test_transmitiendo_agrega_la_linea_al_final(self):
        estado = _resumir(
            grabacion={"outputActive": True, "outputPaused": False,
                       "outputTimecode": "00:01:02.000"},
            transmision={"outputActive": True})
        self.assertEqual(estado.lineas, (
            "Escena actual: Principal",
            "Micrófono Mic/Aux: activado",
            "También se está transmitiendo.",
        ))

    def test_microfono_silenciado(self):
        estado = _resumir(silenciado=True)
        self.assertIn("Micrófono Mic/Aux: silenciado", estado.lineas)

    def test_sin_escena_ni_microfono_solo_queda_lo_que_hay(self):
        estado = _resumir(escena="", microfono="")
        self.assertEqual(estado.lineas, ())


if __name__ == "__main__":
    unittest.main()
