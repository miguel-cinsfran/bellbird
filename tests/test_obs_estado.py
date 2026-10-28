import re
import unittest

from tests.pseudo_prueba import con_pseudo
from ytchat.core.idioma import _
from ytchat.obs import obs_estado


class NotaTransmisionTest(unittest.TestCase):
    def test_nombra_la_ventana_capturada_el_audio_y_el_microfono(self):
        nota = obs_estado.NOTA_TRANSMISION
        self.assertIn("Ventana que se captura", nota)
        self.assertIn("audio del escritorio", nota)
        self.assertIn("micrófono", nota)

    def test_ninguna_frase_pasa_de_25_palabras(self):
        frases = re.split(r"(?<=[.:])\s+", obs_estado.NOTA_TRANSMISION)
        largas = [frase for frase in frases if len(frase.split()) > 25]
        self.assertEqual(largas, [])


class FrasesObsTest(unittest.TestCase):
    def test_transmision_inactiva(self):
        self.assertEqual(obs_estado.frase_transmision(False, 0, 0, 0),
                         "No estás transmitiendo")

    def test_transmision_activa_sin_fotogramas_perdidos(self):
        self.assertEqual(obs_estado.frase_transmision(True, 61, 0, 100),
                         "Transmitiendo desde hace 1 min")

    def test_transmision_activa_con_fotogramas_perdidos(self):
        self.assertEqual(obs_estado.frase_transmision(True, 3_600, 4, 100),
                         "Transmitiendo desde hace 1 h 0 min, 4 de 100 fotogramas perdidos")

    def test_fotogramas_perdidos_sin_total_omite_la_proporcion(self):
        self.assertEqual(obs_estado.frase_transmision(True, 3_600, 4, 0),
                         "Transmitiendo desde hace 1 h 0 min, 4 fotogramas perdidos")

    def test_grabacion_inactiva(self):
        self.assertEqual(obs_estado.frase_grabacion(False, False, "00:00:00.000"),
                         "No estás grabando")

    def test_grabacion_en_pausa_recorta_las_milesimas(self):
        self.assertEqual(obs_estado.frase_grabacion(True, True, "01:02:03.456"),
                         "Grabación en pausa, 01:02:03")

    def test_grabacion_activa(self):
        self.assertEqual(obs_estado.frase_grabacion(True, False, "00:01:02.000"),
                         "Grabando, 00:01:02")

    def test_escena_al_aire_con_nombre(self):
        self.assertEqual(obs_estado.frase_escena_al_aire("Escena"), "Al aire: Escena")

    def test_escena_al_aire_sin_nombre(self):
        self.assertEqual(obs_estado.frase_escena_al_aire(""),
                         "No se pudo saber que escena está al aire")

    def test_frases_de_resultado(self):
        esperadas = {
            "transmision_iniciada": "Transmisión iniciada",
            "transmision_detenida": "Transmisión detenida",
            "grabacion_iniciada": "Grabación iniciada",
            "grabacion_detenida": "Grabación detenida",
            "grabacion_en_pausa": "Grabación en pausa",
            "grabacion_reanudada": "Grabación reanudada",
            "escena_cambiada": "Escena puesta al aire",
        }
        self.assertEqual({accion: obs_estado.frase_resultado(accion)
                          for accion in esperadas}, esperadas)


class TestPseudoEstado(unittest.TestCase):
    """Pseudotraducción de los textos de `obs_estado`.

    Sin ventanas: llama a las funciones bajo `con_pseudo()` y exige cada
    texto propio marcado. Los datos (nombres de escena, duraciones,
    tiempos) viajan con ejemplos y se exigen presentes.
    """

    def test_nota_se_traduce_donde_se_usa(self):
        with con_pseudo():
            self.assertTrue(_(obs_estado.NOTA_TRANSMISION).startswith("[¡"))

    def test_frase_transmision_marca_activa_e_inactiva(self):
        with con_pseudo():
            self.assertTrue(obs_estado.frase_transmision(
                False, 0, 0, 0).startswith("[¡"))
            activa = obs_estado.frase_transmision(True, 61, 0, 100)
            self.assertTrue(activa.startswith("[¡"), activa)
            self.assertIn("1 min", activa)
            con_perdidos = obs_estado.frase_transmision(True, 3600, 4, 100)
            self.assertTrue(con_perdidos.startswith("[¡"), con_perdidos)
            self.assertIn("4", con_perdidos)
            self.assertIn("de 100", con_perdidos)

    def test_frase_grabacion_marca_los_tres_caminos(self):
        with con_pseudo():
            self.assertTrue(obs_estado.frase_grabacion(
                False, False, "00:00:00.000").startswith("[¡"))
            en_pausa = obs_estado.frase_grabacion(True, True, "01:02:03.456")
            self.assertTrue(en_pausa.startswith("[¡"), en_pausa)
            self.assertIn("01:02:03", en_pausa)
            grabando = obs_estado.frase_grabacion(True, False, "00:01:02.000")
            self.assertTrue(grabando.startswith("[¡"), grabando)
            self.assertIn("00:01:02", grabando)

    def test_frase_escena_marca_con_y_sin_nombre(self):
        with con_pseudo():
            con_nombre = obs_estado.frase_escena_al_aire("Escena")
            self.assertTrue(con_nombre.startswith("[¡"), con_nombre)
            self.assertIn("Escena", con_nombre)
            self.assertTrue(obs_estado.frase_escena_al_aire(
                "").startswith("[¡"))

    def test_resultados_se_traducen_donde_se_usan(self):
        acciones = ("transmision_iniciada", "transmision_detenida",
                    "grabacion_iniciada", "grabacion_detenida",
                    "grabacion_en_pausa", "grabacion_reanudada",
                    "escena_cambiada")
        with con_pseudo():
            for accion in acciones:
                with self.subTest(accion=accion):
                    self.assertTrue(
                        _(obs_estado.frase_resultado(accion)).startswith(
                            "[¡"), accion)


if __name__ == "__main__":
    unittest.main()
