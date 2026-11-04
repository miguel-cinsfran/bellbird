"""Pruebas del resumen de tiempos del banco de QA, sin ventanas."""

import unittest

from qa.tiempos_banco import lineas_tiempos


class TiemposDelBancoTest(unittest.TestCase):

    def _anotacion(self, escenario, orden, segundos, tipo=None, inicio=None):
        anotacion = {"escenario": escenario, "orden": orden,
                     "segundos": segundos}
        if tipo is not None:
            anotacion["tipo"] = tipo
        if inicio is not None:
            anotacion["inicio"] = inicio
        return anotacion

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
        self.assertIn("1. uno, op11 [orden]: 1.100 s", pasos[0])
        self.assertIn("10. uno, op2 [orden]: 0.200 s", pasos[9])
        self.assertNotIn(", op1:", "\n".join(pasos))
        self.assertNotIn(", op0:", "\n".join(pasos))

    def test_un_escenario_sin_ordenes_igual_muestra_su_duracion(self):
        lineas = lineas_tiempos([], [("vacio", 3.5), ("otro", 1.0)])

        self.assertIn("    (sin órdenes anotadas)", lineas)
        self.assertIn("    vacio: 3.500 s, sin medir 3.5 s", lineas)
        self.assertIn("    otro: 1.000 s, sin medir 1.0 s", lineas)

    def test_las_duraciones_salen_en_el_orden_en_que_corrieron(self):
        lineas = lineas_tiempos([], [("primero", 2.0), ("segundo", 5.0),
                                     ("tercero", 1.0)])

        indice_primero = lineas.index("    primero: 2.000 s, sin medir 2.0 s")
        indice_segundo = lineas.index("    segundo: 5.000 s, sin medir 5.0 s")
        indice_tercero = lineas.index("    tercero: 1.000 s, sin medir 1.0 s")
        self.assertLess(indice_primero, indice_segundo)
        self.assertLess(indice_segundo, indice_tercero)

    def test_la_seccion_empieza_con_tiempos(self):
        self.assertEqual(lineas_tiempos([], [])[0], "TIEMPOS")

    def test_el_sin_medir_descuenta_la_union_de_lo_anotado(self):
        anotaciones = [
            self._anotacion("pref", "tab: Preferencias", 4.0, "tab", 1.0),
            self._anotacion("pref", "op1", 1.0, "orden", 2.0),
            self._anotacion("pref", "op2", 1.0, "orden", 3.5),
            self._anotacion("pref", "roles_segun_windows", 2.0, "uia", 7.0),
        ]
        lineas = lineas_tiempos(anotaciones, [("pref", 10.0)])

        self.assertIn("    pref: 10.000 s, sin medir 4.0 s", lineas)

    def test_los_diez_mas_lentos_mezclan_los_tres_tipos_con_su_etiqueta(self):
        anotaciones = [
            self._anotacion("esc", "tab: Preferencias", 2.0, "tab", 0.0),
            self._anotacion("esc", "orden_lenta", 3.0, "orden", 4.0),
            self._anotacion("esc", "roles_segun_windows", 1.0, "uia", 5.0),
        ]
        lineas = lineas_tiempos(anotaciones, [("esc", 6.0)])

        pasos = [l for l in lineas if l.lstrip().startswith(
            tuple("%d. " % i for i in range(1, 4)))]
        self.assertEqual(len(pasos), 3)
        self.assertIn("1. esc, orden_lenta [orden]: 3.000 s", pasos[0])
        self.assertIn("2. esc, tab: Preferencias [tab]: 2.000 s", pasos[1])
        self.assertIn("3. esc, roles_segun_windows [uia]: 1.000 s", pasos[2])

    def test_una_anotacion_sin_tipo_cuenta_como_orden(self):
        anotaciones = [self._anotacion("esc", "vieja", 1.0, inicio=0.0)]
        lineas = lineas_tiempos(anotaciones, [("esc", 2.0)])

        self.assertIn("1. esc, vieja [orden]: 1.000 s", lineas[2])
        self.assertIn("    esc: 2.000 s, sin medir 1.0 s", lineas)


if __name__ == "__main__":
    unittest.main()
