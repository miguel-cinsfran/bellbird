"""Pruebas de las frases de General de OBS, sin wx."""

import unittest

from bellbird.obs import obs_general


TODAS = {
    "cpuUsage": 12.6,
    "outputSkippedFrames": 3,
    "outputTotalFrames": 100,
    "renderSkippedFrames": 5,
    "renderTotalFrames": 200,
    "availableDiskSpace": 2048,
}


class TestLineasDeGeneral(unittest.TestCase):

    def test_con_todos_los_datos(self):
        self.assertEqual(obs_general.lineas("TikTok", TODAS), [
            "Conectado con OBS. Perfil: TikTok.",
            "Uso de CPU: 13 %.",
            "Fotogramas omitidos por retraso en la codificación: 3 de 100.",
            "Fotogramas perdidos por retraso de procesamiento: 5 de 200.",
            "Espacio en disco disponible: 2,0 GB.",
        ])

    def test_sin_perfil_no_escribe_su_linea(self):
        lineas = obs_general.lineas("", TODAS)
        self.assertNotIn("Conectado con OBS. Perfil: .", lineas)
        self.assertFalse(any(linea.startswith("Conectado con OBS")
                             for linea in lineas))

    def test_sin_cpu_no_escribe_su_linea(self):
        datos = dict(TODAS)
        del datos["cpuUsage"]
        lineas = obs_general.lineas("TikTok", datos)
        self.assertFalse(any(linea.startswith("Uso de CPU")
                             for linea in lineas))

    def test_sin_los_fotogramas_de_codificacion_no_escribe_su_linea(self):
        for clave in ("outputSkippedFrames", "outputTotalFrames"):
            with self.subTest(clave=clave):
                datos = dict(TODAS)
                del datos[clave]
                lineas = obs_general.lineas("TikTok", datos)
                self.assertFalse(any(linea.startswith("Fotogramas omitidos")
                                     for linea in lineas))

    def test_sin_los_fotogramas_de_procesamiento_no_escribe_su_linea(self):
        for clave in ("renderSkippedFrames", "renderTotalFrames"):
            with self.subTest(clave=clave):
                datos = dict(TODAS)
                del datos[clave]
                lineas = obs_general.lineas("TikTok", datos)
                self.assertFalse(any(linea.startswith("Fotogramas perdidos")
                                     for linea in lineas))

    def test_sin_espacio_en_disco_no_escribe_su_linea(self):
        datos = dict(TODAS)
        del datos["availableDiskSpace"]
        lineas = obs_general.lineas("TikTok", datos)
        self.assertFalse(any(linea.startswith("Espacio en disco")
                             for linea in lineas))

    def test_el_cpu_se_redondea_a_entero(self):
        for valor, esperado in ((12.4, "12"), (12.6, "13"), (0, "0")):
            with self.subTest(valor=valor):
                datos = dict(TODAS)
                datos["cpuUsage"] = valor
                lineas = obs_general.lineas("TikTok", datos)
                self.assertIn("Uso de CPU: {valor} %.".format(valor=esperado),
                              lineas)

    def test_sin_estadisticas_solo_queda_el_perfil(self):
        self.assertEqual(obs_general.lineas("TikTok", {}),
                         ["Conectado con OBS. Perfil: TikTok."])


if __name__ == "__main__":
    unittest.main()
