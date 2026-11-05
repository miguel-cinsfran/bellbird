"""Frases y registro de las metas de un directo de TikTok.

Puro y sin wx: las frases de meta cumplida y de avance, el registro con
candado y las reglas de cuándo una meta está cumplida y de qué meta
informa F2.
"""

import unittest

from guyrapu.capture import metas


class TestFrases(unittest.TestCase):

    def test_cumplida_con_descripcion(self):
        self.assertEqual(
            metas.frase_cumplida("100 rosas para el viaje"),
            "Meta cumplida: 100 rosas para el viaje")

    def test_cumplida_sin_descripcion(self):
        self.assertEqual(metas.frase_cumplida(""), "Meta cumplida")
        self.assertEqual(metas.frase_cumplida("   "), "Meta cumplida")

    def test_en_curso_con_descripcion(self):
        self.assertEqual(
            metas.frase_meta("100 rosas para el viaje", 340, 500),
            "Meta: 100 rosas para el viaje, 340 de 500")

    def test_en_curso_sin_descripcion(self):
        self.assertEqual(metas.frase_meta("", 340, 500), "Meta: 340 de 500")


class TestRegistroMetas(unittest.TestCase):

    def setUp(self):
        metas.registro.reiniciar()

    def test_avance_sin_cumplir_no_anuncia_y_queda_para_f2(self):
        anuncia = metas.registro.actualizar(
            "g1", "100 rosas para el viaje", [(340, 500)])
        self.assertFalse(anuncia)
        self.assertEqual(
            metas.registro.en_curso(),
            "Meta: 100 rosas para el viaje, 340 de 500")

    def test_al_cumplirse_anuncia_una_sola_vez(self):
        self.assertFalse(metas.registro.actualizar(
            "g1", "100 rosas para el viaje", [(340, 500)]))
        self.assertTrue(metas.registro.actualizar(
            "g1", "100 rosas para el viaje", [(500, 500)]))
        self.assertFalse(metas.registro.actualizar(
            "g1", "100 rosas para el viaje", [(500, 500)]))

    def test_una_submeta_con_objetivo_cero_no_cuenta(self):
        self.assertFalse(metas.registro.actualizar(
            "g1", "", [(9, 0)]))
        self.assertTrue(metas.registro.actualizar(
            "g1", "", [(9, 0), (10, 10)]))

    def test_f2_nombra_la_ultima_actualizada_sin_cumplir(self):
        metas.registro.actualizar("a", "Meta A", [(10, 100)])
        metas.registro.actualizar("b", "Meta B", [(20, 100)])
        self.assertEqual(metas.registro.en_curso(),
                         "Meta: Meta B, 20 de 100")
        metas.registro.actualizar("a", "Meta A", [(30, 100)])
        self.assertEqual(metas.registro.en_curso(),
                         "Meta: Meta A, 30 de 100")

    def test_f2_usa_la_primera_submeta_sin_cumplir(self):
        metas.registro.actualizar(
            "g1", "Viaje", [(100, 200), (150, 300)])
        self.assertEqual(metas.registro.en_curso(),
                         "Meta: Viaje, 100 de 200")

    def test_las_cumplidas_no_aparecen_en_f2(self):
        metas.registro.actualizar("a", "Meta A", [(100, 100)])
        self.assertEqual(metas.registro.en_curso(), "")

    def test_f2_vacio_sin_metas(self):
        self.assertEqual(metas.registro.en_curso(), "")

    def test_reiniciar_olvida_todo(self):
        metas.registro.actualizar("a", "Meta A", [(10, 100)])
        metas.registro.reiniciar()
        self.assertEqual(metas.registro.en_curso(), "")


if __name__ == "__main__":
    unittest.main()
