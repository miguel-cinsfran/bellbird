"""Pruebas de la identidad de la aplicación y los textos que la muestran."""

import unittest

from guyrapu.core import acerca_de
from guyrapu.core import config
from guyrapu.core.version_legible import version_legible


class TestNombreApp(unittest.TestCase):
    def test_nombre_de_la_aplicacion(self):
        self.assertEqual(config.APP_NAME, "Guyrapu")

    def test_el_user_agent_sale_del_nombre_y_la_version(self):
        self.assertEqual(config.USER_AGENT,
                         f"{config.APP_NAME}/{config.APP_VERSION}")

    def test_la_url_del_repositorio_es_la_del_proyecto(self):
        self.assertEqual(config.URL_REPOSITORIO,
                         "https://github.com/miguel-cinsfran/guyrapu")

    def test_las_urls_de_la_actualizacion_salen_del_repositorio(self):
        from guyrapu.core import actualizacion
        self.assertEqual(
            actualizacion.URL_ULTIMA_VERSION,
            "https://api.github.com/repos/miguel-cinsfran/guyrapu/"
            "releases/latest")
        self.assertEqual(
            actualizacion.URL_PAGINA_RELEASES,
            "https://github.com/miguel-cinsfran/guyrapu/releases/latest")


class TestVersionLegible(unittest.TestCase):
    def test_preversion_con_punto(self):
        self.assertEqual(version_legible("3.0.0-beta.2"), "3.0.0 beta 2")

    def test_quita_una_v_inicial(self):
        self.assertEqual(version_legible("v3.0.0-beta.2"), "3.0.0 beta 2")

    def test_version_sin_preversion(self):
        self.assertEqual(version_legible("2.5.1"), "2.5.1")

    def test_preversion_rc(self):
        self.assertEqual(version_legible("3.0.0-rc.1"), "3.0.0 rc 1")

    def test_version_ilegible_se_devuelve_intacta(self):
        self.assertEqual(version_legible("sin versión"), "sin versión")


class TestAcercaDe(unittest.TestCase):
    def setUp(self):
        self.texto = acerca_de.texto("3.0.0-beta.2")

    def test_empieza_con_el_nombre_y_la_version_legible(self):
        self.assertTrue(self.texto.startswith("Guyrapu 3.0.0 beta 2\n\n"))

    def test_describe_la_app(self):
        self.assertIn("Lee en voz alta el chat de los directos de YouTube y "
                      "TikTok.", self.texto)

    def test_lleva_autor_licencia_y_repositorio_en_orden(self):
        autor = self.texto.index("Autor: Miguel Ángel Insfrán")
        licencia = self.texto.index("Licencia: GPL versión 3, con condiciones "
                                    "adicionales.")
        repositorio = self.texto.index(
            "Repositorio: https://github.com/miguel-cinsfran/guyrapu")
        self.assertLess(autor, licencia)
        self.assertLess(licencia, repositorio)

    def test_la_licencia_nombra_los_archivos(self):
        self.assertIn("archivos LICENSE y NOTICE", self.texto)


if __name__ == "__main__":
    unittest.main()
