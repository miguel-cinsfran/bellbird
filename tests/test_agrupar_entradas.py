"""Agrupador de entradas al directo de TikTok (lógica pura, sin wx)."""

import re
import unittest

from guyrapu.capture.agrupar_entradas import AgrupadorEntradas, nombres_del_grupo


class TestAgrupadorEntradas(unittest.TestCase):

    def test_junta_personas_distintas_en_orden_de_llegada(self):
        agrupador = AgrupadorEntradas(ventana=10.0)
        agrupador.sumar("Ana", "1", 100.0)
        agrupador.sumar("Beto", "2", 101.0)
        agrupador.sumar("Caro", "3", 102.0)
        self.assertEqual(
            agrupador.vencido(110.0),
            [("Ana", "1"), ("Beto", "2"), ("Caro", "3")])

    def test_no_repite_a_quien_entra_dos_veces(self):
        agrupador = AgrupadorEntradas(ventana=10.0)
        agrupador.sumar("Ana", "1", 100.0)
        agrupador.sumar("Ana", "1", 101.0)
        agrupador.sumar("Beto", "2", 102.0)
        self.assertEqual(
            agrupador.vencido(110.0),
            [("Ana", "1"), ("Beto", "2")])

    def test_sin_id_la_clave_es_el_nombre(self):
        agrupador = AgrupadorEntradas(ventana=10.0)
        agrupador.sumar("Ana", "", 100.0)
        agrupador.sumar("Ana", "", 101.0)
        self.assertEqual(agrupador.vencido(110.0), [("Ana", "")])

    def test_no_suelta_antes_de_la_ventana(self):
        agrupador = AgrupadorEntradas(ventana=10.0)
        agrupador.sumar("Ana", "1", 100.0)
        self.assertEqual(agrupador.vencido(109.999), [])
        self.assertEqual(agrupador.vencido(109.999), [])

    def test_suelta_todo_al_cumplir_la_ventana_y_la_vacia(self):
        agrupador = AgrupadorEntradas(ventana=10.0)
        agrupador.sumar("Ana", "1", 100.0)
        agrupador.sumar("Beto", "2", 101.0)
        self.assertEqual(
            agrupador.vencido(110.0), [("Ana", "1"), ("Beto", "2")])
        self.assertEqual(agrupador.vencido(110.0), [])

    def test_con_ventana_cero_suelta_al_instante(self):
        agrupador = AgrupadorEntradas(ventana=0)
        agrupador.sumar("Ana", "1", 100.0)
        self.assertEqual(agrupador.vencido(100.0), [("Ana", "1")])

    def test_la_ventana_puede_ser_una_funcion_que_cambia(self):
        segundos = [10]
        agrupador = AgrupadorEntradas(ventana=lambda: segundos[0])
        agrupador.sumar("Ana", "1", 100.0)
        self.assertEqual(agrupador.vencido(104.0), [])
        segundos[0] = 3
        self.assertEqual(agrupador.vencido(104.0), [("Ana", "1")])


class TestNombresDelGrupo(unittest.TestCase):

    def test_un_nombre(self):
        self.assertEqual(nombres_del_grupo(["Ana"]), "Ana")

    def test_dos_nombres(self):
        self.assertEqual(nombres_del_grupo(["Ana", "Beto"]), "Ana y Beto")

    def test_tres_nombres(self):
        self.assertEqual(
            nombres_del_grupo(["Ana", "Beto", "Caro"]),
            "Ana, Beto y Caro")

    def test_cuatro_nombres_resumen_uno_mas(self):
        self.assertEqual(
            nombres_del_grupo(["Ana", "Beto", "Caro", "Dani"]),
            "Ana, Beto, Caro y 1 más")

    def test_siete_nombres_resumen_cuatro_mas(self):
        self.assertEqual(
            nombres_del_grupo(
                ["Ana", "Beto", "Caro", "Dani", "Eva", "Flor", "Gabi"]),
            "Ana, Beto, Caro y 4 más")

    def test_propiedad_hasta_veinte_nombres(self):
        for total in range(1, 21):
            nombres = [f"Persona{n}" for n in range(total)]
            with self.subTest(total=total):
                texto = nombres_del_grupo(nombres)
                visibles = [nombre for nombre in nombres
                            if nombre in texto]
                self.assertLessEqual(len(visibles), 3)
                if total <= 3:
                    self.assertEqual(len(visibles), total)
                    self.assertNotIn("más", texto)
                    continue
                coincidencia = re.search(r"y (\d+) más$", texto)
                self.assertIsNotNone(coincidencia, texto)
                self.assertEqual(
                    len(visibles) + int(coincidencia.group(1)), total)


if __name__ == "__main__":
    unittest.main()
