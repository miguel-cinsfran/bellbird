"""Pruebas del resumen de tiempos del banco de QA, sin ventanas."""

import unittest

from qa.tiempos_banco import lineas_tiempos


class TiemposDelBancoTest(unittest.TestCase):

    def _anotacion(self, escenario, orden, segundos):
        return {"escenario": escenario, "orden": orden, "segundos": segundos}

    def test_los_diez_mas_lentos_van_del_mayor_al_menor(self):
        anotaciones = [
            self._anotacion("uno", "op%d" % i, i / 10)
            for i in range(12)
        ]
        lineas = lineas_tiempos(
            anotaciones, [("uno", 1.2), ("dos", 0.4)])

        pasos = [l for l in lineas if l.lstrip().startswith(
            tuple("%d. " % i for i in range(1, 11)))]
        self.assertEqual(len(pasos), 10)
        self.assertIn("1. uno, op11: 1.100 s", pasos[0])
        self.assertIn("10. uno, op2: 0.200 s", pasos[9])
        self.assertNotIn(", op1:", "\n".join(pasos))
        self.assertNotIn(", op0:", "\n".join(pasos))

    def test_un_escenario_sin_ordenes_igual_muestra_su_duracion(self):
        lineas = lineas_tiempos([], [("vacio", 3.5), ("otro", 1.0)])

        self.assertIn("    (sin órdenes anotadas)", lineas)
        self.assertIn("    vacio: 3.500 s", lineas)
        self.assertIn("    otro: 1.000 s", lineas)

    def test_las_duraciones_salen_en_el_orden_en_que_corrieron(self):
        lineas = lineas_tiempos([], [("primero", 2.0), ("segundo", 5.0),
                                     ("tercero", 1.0)])

        indice_primero = lineas.index("    primero: 2.000 s")
        indice_segundo = lineas.index("    segundo: 5.000 s")
        indice_tercero = lineas.index("    tercero: 1.000 s")
        self.assertLess(indice_primero, indice_segundo)
        self.assertLess(indice_segundo, indice_tercero)

    def test_la_seccion_empieza_con_tiempos(self):
        self.assertEqual(lineas_tiempos([], [])[0], "TIEMPOS")


if __name__ == "__main__":
    unittest.main()
