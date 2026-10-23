import unittest

from ytchat.obs.obs_audio import elegir_microfono, frase_microfono, nombre_corto


class ElegirMicrofonoTest(unittest.TestCase):
    def test_prefiere_el_nombre_guardado(self):
        self.assertEqual(elegir_microfono(("Mic/Aux", "Otro"), "Otro"), "Otro")

    def test_el_preferido_gana_a_una_fuente_con_mic(self):
        self.assertEqual(elegir_microfono(("Mic/Aux", "Audio USB"), "Audio USB"),
                         "Audio USB")

    def test_elije_la_primera_fuente_con_mic_sin_tildes(self):
        self.assertEqual(elegir_microfono(
            ("Audio del escritorio", "Mícrofono USB"), ""), "Mícrofono USB")

    def test_usa_la_primera_fuente_si_no_hay_microfono(self):
        self.assertEqual(elegir_microfono(("Audio del escritorio", "Auxiliar"), ""),
                         "Audio del escritorio")

    def test_devuelve_vacio_sin_fuentes(self):
        self.assertEqual(elegir_microfono((), "Mic/Aux"), "")


class FraseMicrofonoTest(unittest.TestCase):
    def test_anuncia_microfono_silenciado(self):
        self.assertEqual(frase_microfono("Mic/Aux", True), "Micrófono silenciado")

    def test_anuncia_microfono_activado(self):
        self.assertEqual(frase_microfono("Mic/Aux", False), "Micrófono activado")

    def test_nombra_la_fuente_que_no_es_microfono(self):
        self.assertEqual(frase_microfono("Audio del escritorio", True),
                         "Audio del escritorio silenciado")

    def test_anuncia_la_ausencia_de_fuentes(self):
        self.assertEqual(frase_microfono("", False),
                         "OBS no tiene ninguna fuente de audio")

    def test_anuncia_el_dispositivo_fijo_del_microfono(self):
        self.assertEqual(
            frase_microfono("Mic/Aux", False, "Micrófono (WO Mic Device)"),
            "Micrófono activado: WO Mic Device")

    def test_anuncia_el_predeterminado_de_windows_con_su_nombre(self):
        self.assertEqual(
            frase_microfono("Mic/Aux", False, "Micrófono (WO Mic Device)", True),
            "Micrófono activado: predeterminado de Windows, WO Mic Device")

    def test_anuncia_el_predeterminado_de_windows_sin_nombre(self):
        self.assertEqual(
            frase_microfono("Mic/Aux", False, "", True),
            "Micrófono activado: predeterminado de Windows")

    def test_sin_dispositivo_anuncia_como_hoy(self):
        self.assertEqual(frase_microfono("Mic/Aux", False, "", False),
                         "Micrófono activado")

    def test_silenciado_no_nombra_el_dispositivo(self):
        self.assertEqual(
            frase_microfono("Mic/Aux", True, "Micrófono (WO Mic Device)", True),
            "Micrófono silenciado")

    def test_la_fuente_que_no_es_microfono_no_nombra_el_dispositivo(self):
        self.assertEqual(
            frase_microfono("Audio del escritorio", False,
                            "Micrófono (WO Mic Device)"),
            "Audio del escritorio activado")


class NombreCortoTest(unittest.TestCase):
    def test_quita_el_envoltorio_de_windows(self):
        self.assertEqual(nombre_corto("Micrófono (WO Mic Device)"),
                         "WO Mic Device")

    def test_conserva_el_nombre_sin_envoltorio(self):
        self.assertEqual(nombre_corto("Mic/Aux"), "Mic/Aux")

    def test_usa_el_primer_parentesis_y_el_ultimo_cierre(self):
        self.assertEqual(nombre_corto("Micrófono (USB (2))"), "USB (2)")

    def test_nunca_es_vacio_si_el_nombre_no_lo_es(self):
        for nombre in ("Mic/Aux", "Micrófono (WO Mic Device)", " ()", " () ",
                       "Audio del escritorio"):
            with self.subTest(nombre=nombre):
                self.assertTrue(nombre_corto(nombre))


if __name__ == "__main__":
    unittest.main()
