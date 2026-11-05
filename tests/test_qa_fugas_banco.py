"""Pruebas de las ventanas que sobran entre escenarios del banco, sin wx."""

import unittest

from qa.fugas_banco import ventanas_sobrantes


class FugasDelBancoTest(unittest.TestCase):

    def _ventana(self, titulo, visible=True):
        return {"titulo": titulo, "visible": visible}

    def test_devuelve_las_visibles_que_no_son_la_principal(self):
        ventanas = [
            self._ventana("Guyrapu 3.0.0 beta 2"),
            self._ventana("Directo sin imagen"),
            self._ventana("Preferencias"),
        ]
        sobrantes = ventanas_sobrantes(ventanas, "Guyrapu 3.0.0 beta 2")

        self.assertEqual([v["titulo"] for v in sobrantes],
                         ["Directo sin imagen", "Preferencias"])

    def test_una_ventana_invisible_no_cuenta(self):
        ventanas = [
            self._ventana("Guyrapu 3.0.0 beta 2"),
            self._ventana("Oculta", visible=False),
        ]
        self.assertEqual(ventanas_sobrantes(ventanas, "Guyrapu 3.0.0 beta 2"), [])

    def test_la_principal_no_cuenta(self):
        ventanas = [self._ventana("Guyrapu 3.0.0 beta 2")]
        self.assertEqual(ventanas_sobrantes(ventanas, "Guyrapu 3.0.0 beta 2"), [])


if __name__ == "__main__":
    unittest.main()
