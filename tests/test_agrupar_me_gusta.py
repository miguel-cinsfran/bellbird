"""Agrupador de me gusta de TikTok por persona (lógica pura, sin wx)."""

import unittest

from bellbird.capture.agrupar_me_gusta import AgrupadorMeGusta


class TestAgruparPorPersona(unittest.TestCase):
    def test_tres_toques_de_ana_y_uno_de_luis(self):
        agrupador = AgrupadorMeGusta(ventana=10.0)
        agrupador.sumar("Ana", "id_ana", 1, 0.0)
        agrupador.sumar("Ana", "id_ana", 1, 2.0)
        agrupador.sumar("Luis", "id_luis", 1, 4.0)
        agrupador.sumar("Ana", "id_ana", 1, 5.0)
        self.assertEqual(agrupador.vencidos(10.0), [("Ana", "id_ana", 3)])
        self.assertEqual(agrupador.vencidos(10.0), [])
        self.assertEqual(agrupador.vencidos(14.0), [("Luis", "id_luis", 1)])

    def test_sin_ventana_vencida_no_sale_nada(self):
        agrupador = AgrupadorMeGusta(ventana=10.0)
        agrupador.sumar("Ana", "id_ana", 5, 0.0)
        self.assertEqual(agrupador.vencidos(9.9), [])
        self.assertEqual(agrupador.vencidos(10.0), [("Ana", "id_ana", 5)])

    def test_vencidos_sale_en_orden_del_primer_toque(self):
        agrupador = AgrupadorMeGusta(ventana=10.0)
        agrupador.sumar("Luis", "id_luis", 1, 1.0)
        agrupador.sumar("Ana", "id_ana", 2, 0.0)
        self.assertEqual(agrupador.vencidos(11.0),
                         [("Ana", "id_ana", 2), ("Luis", "id_luis", 1)])

    def test_el_autor_es_el_ultimo_nombre_del_grupo(self):
        agrupador = AgrupadorMeGusta(ventana=10.0)
        agrupador.sumar("Ana", "id_ana", 1, 0.0)
        agrupador.sumar("Anita", "id_ana", 1, 2.0)
        self.assertEqual(agrupador.vencidos(10.0), [("Anita", "id_ana", 2)])

    def test_cantidad_invalida_cuenta_uno(self):
        for invalida in (0, None, True, False, "hola", -3, 2.5):
            with self.subTest(cantidad=invalida):
                agrupador = AgrupadorMeGusta(ventana=10.0)
                agrupador.sumar("Ana", "id_ana", invalida, 0.0)
                self.assertEqual(agrupador.vencidos(10.0),
                                 [("Ana", "id_ana", 1)])

    def test_cantidad_valida_suma_sus_toques(self):
        agrupador = AgrupadorMeGusta(ventana=10.0)
        agrupador.sumar("Ana", "id_ana", 7, 0.0)
        agrupador.sumar("Ana", "id_ana", 3, 1.0)
        self.assertEqual(agrupador.vencidos(10.0), [("Ana", "id_ana", 10)])

    def test_sin_canal_id_agrupa_por_el_nombre(self):
        agrupador = AgrupadorMeGusta(ventana=10.0)
        agrupador.sumar("Ana", "", 1, 0.0)
        agrupador.sumar("Ana", "", 2, 1.0)
        agrupador.sumar("Luis", "", 1, 2.0)
        self.assertEqual(agrupador.vencidos(12.0),
                         [("Ana", "", 3), ("Luis", "", 1)])

    def test_grupo_emitido_vuelve_a_empezar(self):
        agrupador = AgrupadorMeGusta(ventana=10.0)
        agrupador.sumar("Ana", "id_ana", 2, 0.0)
        self.assertEqual(agrupador.vencidos(10.0), [("Ana", "id_ana", 2)])
        agrupador.sumar("Ana", "id_ana", 4, 11.0)
        self.assertEqual(agrupador.vencidos(21.0), [("Ana", "id_ana", 4)])

    def test_ventana_personalizada(self):
        agrupador = AgrupadorMeGusta(ventana=5.0)
        agrupador.sumar("Ana", "id_ana", 1, 0.0)
        self.assertEqual(agrupador.vencidos(4.9), [])
        self.assertEqual(agrupador.vencidos(5.0), [("Ana", "id_ana", 1)])


if __name__ == "__main__":
    unittest.main()
