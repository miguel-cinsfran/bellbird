"""Pruebas de las frases de General de OBS, sin wx."""

import unittest

from guyrapu.obs import estado_panel, obs_general


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


def _estado(destino="TikTok", transmision=None, grabacion=None,
            escena="Principal", microfono="Mic/Aux", silenciado=False,
            problemas=()):
    return estado_panel.resumir(
        destino, transmision or {"outputActive": False, "outputDuration": 0},
        grabacion or {"outputActive": False, "outputPaused": False,
                      "outputTimecode": "00:00:00.000"},
        escena, microfono, silenciado, problemas)


class TestResumenDeGeneral(unittest.TestCase):
    """El estado de General reúne la transmisión, la escena y el equipo."""

    def test_con_transmision_activa_empieza_por_su_titular(self):
        estado = _estado(transmision={"outputActive": True,
                                      "outputDuration": 61})
        resultado = obs_general.resumen(estado, "TikTok", TODAS)
        self.assertEqual(resultado[0], "Transmitiendo a TikTok desde hace 1 min")
        self.assertIn("Escena actual: Principal", resultado)
        self.assertIn("Micrófono Mic/Aux: activado", resultado)
        self.assertIn("Grabación: detenida", resultado)
        self.assertIn("Conectado con OBS. Perfil: TikTok.", resultado)

    def test_con_un_problema_de_revision_lo_encabeza(self):
        estado = _estado(problemas=("El micrófono está silenciado.",))
        resultado = obs_general.resumen(estado, "TikTok", TODAS)
        self.assertEqual(
            resultado[0],
            "Revisa antes de transmitir: El micrófono está silenciado.")

    def test_sin_destino_pide_elegirlo(self):
        estado = _estado(destino="")
        self.assertEqual(obs_general.resumen(estado, "", TODAS)[0],
                         "Elige a dónde transmitir")

    def test_con_grabacion_en_pausa_lo_dice_en_sus_lineas(self):
        estado = _estado(grabacion={
            "outputActive": True, "outputPaused": True,
            "outputTimecode": "00:02:03.500"})
        self.assertIn("Grabación: en pausa, 00:02:03",
                      obs_general.resumen(estado, "TikTok", TODAS))

    def test_sin_estadisticas_queda_el_estado_y_el_perfil(self):
        estado = _estado()
        self.assertEqual(obs_general.resumen(estado, "TikTok", {}), [
            "Preparado para transmitir a TikTok",
            "Escena actual: Principal",
            "Micrófono Mic/Aux: activado",
            "Grabación: detenida",
            "Conectado con OBS. Perfil: TikTok.",
        ])

    def test_ningun_dato_aparece_dos_veces(self):
        estado = _estado(transmision={"outputActive": True,
                                      "outputDuration": 61})
        resultado = obs_general.resumen(estado, "TikTok", TODAS)
        self.assertEqual(len(resultado), len(set(resultado)), resultado)


if __name__ == "__main__":
    unittest.main()
