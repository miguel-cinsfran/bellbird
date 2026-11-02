"""Pruebas del resumen del estado de OBS para el panel, sin wx."""

import unittest

from bellbird.obs import estado_panel


def _resumir(**cambios):
    datos = {
        "destino": "YouTube",
        "transmision": {"outputActive": False, "outputDuration": 0},
        "grabacion": {"outputActive": False, "outputPaused": False,
                      "outputTimecode": "00:00:00.000"},
        "escena": "Principal",
        "microfono": "Mic/Aux",
        "silenciado": False,
        "problemas": (),
    }
    datos.update(cambios)
    return estado_panel.resumir(**datos)


class TestTitular(unittest.TestCase):

    def test_listo_para_transmitir(self):
        estado = _resumir()
        self.assertEqual(estado.titular, "Preparado para transmitir a YouTube")
        self.assertEqual(estado.tono, "listo")

    def test_sin_destino_pide_elegirlo(self):
        estado = _resumir(destino="")
        self.assertEqual(estado.titular, "Elige a dónde transmitir")
        self.assertEqual(estado.tono, "listo")

    def test_transmitiendo_con_la_duracion_de_obs(self):
        estado = _resumir(
            destino="TikTok",
            transmision={"outputActive": True, "outputDuration": 30})
        self.assertEqual(
            estado.titular,
            "Transmitiendo a TikTok desde hace menos de un minuto")
        self.assertEqual(estado.tono, "activo")

    def test_transmitiendo_sin_destino_no_deja_un_hueco(self):
        estado = _resumir(
            destino="",
            transmision={"outputActive": True, "outputDuration": 61})
        self.assertEqual(estado.titular, "Transmitiendo desde hace 1 min")

    def test_transmitiendo_reutiliza_la_duracion_de_obs_estado(self):
        estado = _resumir(
            transmision={"outputActive": True, "outputDuration": 61})
        self.assertEqual(
            estado.titular,
            "Transmitiendo a YouTube desde hace 1 min")

    def test_con_problemas_muestra_el_primero_con_tono_aviso(self):
        estado = _resumir(problemas=("El micrófono Mic/Aux está silenciado.",
                                     "La escena no tiene fuentes visibles."))
        self.assertEqual(
            estado.titular,
            "Revisa antes de transmitir: El micrófono Mic/Aux está silenciado.")
        self.assertEqual(estado.tono, "aviso")

    def test_transmitir_manda_sobre_los_problemas(self):
        estado = _resumir(
            transmision={"outputActive": True, "outputDuration": 0},
            problemas=("Un problema.",))
        self.assertEqual(estado.tono, "activo")
        self.assertTrue(estado.titular.startswith("Transmitiendo a YouTube"))

    def test_sin_destino_no_hay_problemas(self):
        estado = _resumir(destino="", problemas=("Un problema.",))
        self.assertEqual(estado.titular, "Elige a dónde transmitir")


class TestLineas(unittest.TestCase):

    def test_lineas_completas_en_orden(self):
        estado = _resumir()
        self.assertEqual(estado.lineas, (
            "Escena actual: Principal",
            "Micrófono Mic/Aux: activado",
            "Grabación: detenida",
        ))

    def test_microfono_silenciado(self):
        estado = _resumir(silenciado=True)
        self.assertIn("Micrófono Mic/Aux: silenciado", estado.lineas)

    def test_sin_microfono_se_omite_la_linea(self):
        estado = _resumir(microfono="")
        self.assertEqual(estado.lineas, (
            "Escena actual: Principal",
            "Grabación: detenida",
        ))

    def test_sin_escena_se_omite_la_linea(self):
        estado = _resumir(escena="")
        self.assertEqual(estado.lineas, (
            "Micrófono Mic/Aux: activado",
            "Grabación: detenida",
        ))

    def test_grabacion_en_curso_con_tiempo(self):
        estado = _resumir(
            grabacion={"outputActive": True, "outputPaused": False,
                       "outputTimecode": "00:01:02.500"})
        self.assertIn("Grabación: en curso, 00:01:02", estado.lineas)

    def test_grabacion_en_pausa_con_tiempo(self):
        estado = _resumir(
            grabacion={"outputActive": True, "outputPaused": True,
                       "outputTimecode": "00:02:03.500"})
        self.assertIn("Grabación: en pausa, 00:02:03", estado.lineas)


if __name__ == "__main__":
    unittest.main()
