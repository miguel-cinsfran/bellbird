"""Tests de la escala de velocidad propia (escala_voz)."""

import unittest

from bellbird.voice import escala_voz


class TestVelocidadDesdeWpm(unittest.TestCase):

    def test_valores_conocidos(self):
        self.assertEqual(escala_voz.velocidad_desde_wpm(175), 50)
        self.assertEqual(escala_voz.velocidad_desde_wpm(500), 100)

    def test_minimo_de_la_escala(self):
        # La fórmula da 20 para 50 wpm: ese wpm corresponde al rate SAPI -6, y
        # el rango de la app vieja (50 a 500) no llega a cubrir -10.
        self.assertEqual(escala_voz.velocidad_desde_wpm(50), 20)

    def test_rango_completo_cae_en_la_escala(self):
        for wpm in range(50, 501):
            pct = escala_voz.velocidad_desde_wpm(wpm)
            self.assertEqual(pct % 5, 0, wpm)
            self.assertGreaterEqual(pct, 0, wpm)
            self.assertLessEqual(pct, 100, wpm)


class TestVelocidadAPrism(unittest.TestCase):

    def test_sapi_ida_y_vuelta(self):
        for pct in range(0, 101, 5):
            x = escala_voz.velocidad_a_prism("sapi", pct)
            self.assertGreaterEqual(x, 0.0, pct)
            self.assertLessEqual(x, 1.0, pct)
            self.assertEqual(round((x - 0.5) * 20), pct // 5 - 10, pct)

    def test_otro_motor_es_directo(self):
        for pct in range(0, 101, 5):
            self.assertAlmostEqual(
                escala_voz.velocidad_a_prism("onecore", pct), pct / 100)


class TestPorcentajeAPrism(unittest.TestCase):

    def test_ida_y_vuelta(self):
        for pct in range(0, 101):
            self.assertAlmostEqual(escala_voz.porcentaje_a_prism(pct),
                                   pct / 100)

    def test_acotado(self):
        self.assertEqual(escala_voz.porcentaje_a_prism(-10), 0.0)
        self.assertEqual(escala_voz.porcentaje_a_prism(150), 1.0)


class TestVelocidadAElevenlabs(unittest.TestCase):

    def test_anclas(self):
        self.assertEqual(escala_voz.velocidad_a_elevenlabs(0), 0.7)
        self.assertEqual(escala_voz.velocidad_a_elevenlabs(50), 1.0)
        self.assertEqual(escala_voz.velocidad_a_elevenlabs(100), 1.2)

    def test_tramos_lineales(self):
        self.assertEqual(escala_voz.velocidad_a_elevenlabs(25), 0.85)
        self.assertEqual(escala_voz.velocidad_a_elevenlabs(75), 1.1)

    def test_acotado(self):
        self.assertEqual(escala_voz.velocidad_a_elevenlabs(-10), 0.7)
        self.assertEqual(escala_voz.velocidad_a_elevenlabs(200), 1.2)

    def test_monotono_y_en_rango(self):
        anterior = 0.0
        for pct in range(0, 101):
            valor = escala_voz.velocidad_a_elevenlabs(pct)
            self.assertGreaterEqual(valor, anterior)
            self.assertGreaterEqual(valor, 0.7)
            self.assertLessEqual(valor, 1.2)
            anterior = valor


class TestAjustarVelocidad(unittest.TestCase):

    def test_nunca_sale_del_rango(self):
        for pct in range(0, 101, 5):
            for pasos in range(-30, 31):
                v = escala_voz.ajustar_velocidad(pct, pasos)
                self.assertGreaterEqual(v, 0)
                self.assertLessEqual(v, 100)
                self.assertEqual(v % 5, 0)

    def test_subir_y_bajar_vuelve_al_inicio(self):
        self.assertEqual(escala_voz.ajustar_velocidad(50, 3), 65)
        self.assertEqual(escala_voz.ajustar_velocidad(65, -3), 50)

    def test_valor_no_multiplo_se_redondea(self):
        self.assertEqual(escala_voz.ajustar_velocidad(52, 0), 50)


class TestResolverVoz(unittest.TestCase):

    VOCES = [
        "Microsoft Helena Desktop - Spanish (Spain)",
        "Microsoft Zira Desktop - English (United States)",
    ]

    def test_indice_en_rango(self):
        self.assertEqual(escala_voz.resolver_voz("1", self.VOCES), 1)

    def test_indice_fuera_de_rango(self):
        self.assertIsNone(escala_voz.resolver_voz("7", self.VOCES))

    def test_nombre_exacto(self):
        self.assertEqual(escala_voz.resolver_voz(self.VOCES[0], self.VOCES), 0)

    def test_nombre_exacto_gana_al_fragmento(self):
        # «Microsoft Helena» es fragmento de la primera y nombre exacto de la
        # segunda: debe elegir la segunda, no la que aparece primero.
        voces = ["Microsoft Helena Desktop - Spanish (Spain)", "Microsoft Helena"]
        self.assertEqual(escala_voz.resolver_voz("Microsoft Helena", voces), 1)

    def test_fragmento_sin_mayusculas(self):
        self.assertEqual(escala_voz.resolver_voz("zira", self.VOCES), 1)

    def test_nada_coincide(self):
        self.assertIsNone(escala_voz.resolver_voz("inexistente", self.VOCES))

    def test_vacio_o_none(self):
        self.assertIsNone(escala_voz.resolver_voz("", self.VOCES))
        self.assertIsNone(escala_voz.resolver_voz(None, self.VOCES))


class TestMigrarVoz(unittest.TestCase):

    VOCES = ["Microsoft Helena", "Microsoft Pablo"]

    def test_numero_en_rango_pasa_a_nombre(self):
        self.assertEqual(escala_voz.migrar_voz("1", self.VOCES), "Microsoft Pablo")
        self.assertEqual(escala_voz.migrar_voz(0, self.VOCES), "Microsoft Helena")

    def test_numero_fuera_de_rango_no_migra(self):
        self.assertIsNone(escala_voz.migrar_voz("9", self.VOCES))

    def test_nombre_ya_guardado_no_migra(self):
        self.assertIsNone(escala_voz.migrar_voz("Microsoft Pablo", self.VOCES))

    def test_vacio_y_none_no_migran(self):
        self.assertIsNone(escala_voz.migrar_voz("", self.VOCES))
        self.assertIsNone(escala_voz.migrar_voz("   ", self.VOCES))
        self.assertIsNone(escala_voz.migrar_voz(None, self.VOCES))

    def test_sin_voces_no_migra(self):
        self.assertIsNone(escala_voz.migrar_voz("0", []))


if __name__ == "__main__":
    unittest.main()
