from __future__ import annotations

import unittest

from bellbird.downloads.progreso_ytdlp import (
    PLANTILLA_DESCARGA,
    PLANTILLA_PROCESO,
    analizar_linea_descarga,
    analizar_linea_proceso,
    analizar_linea_progreso,
    plantillas_progreso,
    progreso_total,
)


class TestAnalizarLineaProgreso(unittest.TestCase):
    def test_linea_http_conserva_el_nombre(self):
        datos = analizar_linea_progreso(
            "PROG 7168 117495 NA 3617032.130895091 0 "
            "nombre con espacios.m4a"
        )
        self.assertEqual(datos["descargado"], 7168)
        self.assertEqual(datos["total"], 117495)
        self.assertAlmostEqual(datos["pct"], 7168 * 100 / 117495)
        self.assertEqual(datos["velocidad"], 3617032.130895091)
        self.assertEqual(datos["eta"], 0)
        self.assertEqual(datos["nombre"], "nombre con espacios.m4a")

    def test_linea_hls_usa_total_estimado(self):
        datos = analizar_linea_progreso(
            "PROG 1024 NA 4876.190478857593 NA prueba.mp4"
        )
        self.assertIsNone(datos["total"])
        self.assertGreater(datos["pct"], 0)

    def test_linea_sin_prefijo_no_es_progreso(self):
        self.assertIsNone(analizar_linea_progreso("[youtube] Extracting URL"))

    def test_na_se_convierte_en_none(self):
        datos = analizar_linea_progreso("PROG 1 NA NA NA NA archivo.mp4")
        self.assertIsNone(datos["total"])
        self.assertIsNone(datos["velocidad"])
        self.assertIsNone(datos["eta"])
        self.assertEqual(datos["pct"], 0.0)

    def test_nombre_vacio_es_linea_rota(self):
        self.assertIsNone(analizar_linea_progreso("PROG 1 2 NA 3 4 "))

    def test_linea_incompleta_no_revienta(self):
        self.assertIsNone(analizar_linea_progreso("PROG 1 2"))

    def test_numero_roto_no_revienta(self):
        self.assertIsNone(analizar_linea_progreso("PROG roto 2 NA 3 4 archivo"))

    def test_salto_de_linea_no_contamina_el_nombre(self):
        datos = analizar_linea_progreso("PROG 1 2 NA 3 4 archivo.mp4\r\n")
        self.assertEqual(datos["nombre"], "archivo.mp4")


class TestPlantillasProgreso(unittest.TestCase):
    def test_pide_descarga_y_postproceso(self):
        self.assertEqual(plantillas_progreso(),
                         ["--progress-template", PLANTILLA_DESCARGA,
                          "--progress-template", PLANTILLA_PROCESO])


class TestAnalizarLineaDescarga(unittest.TestCase):
    def test_lista_trae_indice_y_total(self):
        datos = analizar_linea_descarga(
            "PROGD 5 10 NA 2 3 2 5 nombre con espacios.mp4")
        self.assertEqual(datos["indice"], 2)
        self.assertEqual(datos["total"], 5)
        self.assertEqual(datos["pct"], 50.0)
        self.assertEqual(datos["velocidad"], 2.0)
        self.assertEqual(datos["eta"], 3)
        self.assertEqual(datos["nombre"], "nombre con espacios.mp4")

    def test_sin_lista_indice_y_total_son_none(self):
        datos = analizar_linea_descarga("PROGD 1 NA NA NA NA NA NA archivo.mp4")
        self.assertIsNone(datos["indice"])
        self.assertIsNone(datos["total"])
        self.assertEqual(datos["pct"], 0.0)

    def test_linea_ajena_no_es_descarga(self):
        self.assertIsNone(analizar_linea_descarga("PROG 1 2 NA 3 4 archivo"))


class TestAnalizarLineaProceso(unittest.TestCase):
    def test_lee_estado_y_procesador(self):
        self.assertEqual(analizar_linea_proceso("PROC started ExtractAudio"),
                         ("started", "ExtractAudio"))

    def test_linea_ajena_no_es_proceso(self):
        self.assertIsNone(analizar_linea_proceso("PROG 1 2 NA 3 4 archivo"))


class TestProgresoTotal(unittest.TestCase):
    def test_sin_lista_devuelve_el_porcentaje(self):
        self.assertEqual(progreso_total(0, 0, 42.0), 42.0)
        self.assertEqual(progreso_total(None, None, 42.0), 42.0)

    def test_con_lista_reparte_el_total(self):
        self.assertEqual(progreso_total(1, 4, 0), 0.0)
        self.assertEqual(progreso_total(1, 4, 100), 25.0)
        self.assertEqual(progreso_total(3, 4, 50), 62.5)

    def test_nunca_retrocede_al_avanzar_por_todos_los_videos(self):
        anterior = 0.0
        for indice in range(1, 6):
            for pct in range(0, 101, 5):
                valor = progreso_total(indice, 5, pct)
                self.assertGreaterEqual(valor, anterior)
                self.assertGreaterEqual(valor, 0.0)
                self.assertLessEqual(valor, 100.0)
                anterior = valor


if __name__ == "__main__":
    unittest.main()
