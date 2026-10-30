"""Opciones de formato del Administrador de descargas, sin wx."""

import unittest

from bellbird.downloads import opciones_formato as op


class TestFormatos(unittest.TestCase):
    def test_nueve_formatos_en_orden(self):
        claves = [clave for _etiqueta, clave in op.FORMATOS]
        self.assertEqual(claves, ["video_original", "mp4", "webm",
                                  "audio_original", "mp3", "m4a",
                                  "opus", "flac", "wav"])


class TestClaseDeCalidad(unittest.TestCase):
    def test_clase_en_los_nueve(self):
        esperado = {"video_original": "resolucion", "mp4": "resolucion",
                    "webm": "resolucion", "audio_original": "",
                    "mp3": "bitrate", "m4a": "bitrate",
                    "opus": "bitrate", "flac": "", "wav": ""}
        for formato, clase in esperado.items():
            with self.subTest(formato=formato):
                self.assertEqual(op.clase_de_calidad(formato), clase)


class TestEtiquetasDeCalidad(unittest.TestCase):
    def test_etiquetas_en_los_nueve(self):
        self.assertEqual(op.etiquetas_de_calidad("mp4")[0], "Máxima")
        self.assertIn("1080p", op.etiquetas_de_calidad("webm"))
        self.assertIn("720p", op.etiquetas_de_calidad("video_original"))
        self.assertEqual(op.etiquetas_de_calidad("mp3")[0], "128 kbps")
        self.assertIn("320 kbps", op.etiquetas_de_calidad("opus"))
        for formato in ("audio_original", "flac", "wav"):
            with self.subTest(formato=formato):
                self.assertEqual(op.etiquetas_de_calidad(formato), [])


class TestArgumentosDeFormato(unittest.TestCase):
    def test_tabla_nueve_formatos(self):
        casos = [
            ("video_original", 192, 0, ["-f", "bv*+ba/b"]),
            ("video_original", 192, 720, ["-S", "res:720"]),
            ("mp4", 192, 0, ["--merge-output-format", "mp4"]),
            ("mp4", 192, 1080, ["-S", "res:1080,vcodec:h264,acodec:aac,ext:mp4"]),
            ("webm", 192, 0, ["--merge-output-format", "webm"]),
            ("webm", 192, 480, ["-S", "res:480"]),
            ("audio_original", 192, 0, ["-f", "ba/b", "-x"]),
            ("mp3", 192, 0, ["--audio-format", "mp3", "--audio-quality", "192K"]),
            ("m4a", 256, 0, ["--audio-format", "m4a", "--audio-quality", "256K"]),
            ("opus", 320, 0, ["--audio-format", "opus", "--audio-quality", "320K"]),
            ("flac", 192, 0, ["--audio-format", "flac"]),
            ("wav", 192, 0, ["--audio-format", "wav"]),
        ]
        for formato, bitrate, resolucion, partes in casos:
            with self.subTest(formato=formato, resolucion=resolucion):
                args = op.argumentos_de_formato(formato, bitrate, resolucion)
                for parte in partes:
                    self.assertIn(parte, args, args)

    def test_desconocido_cae_a_mp4(self):
        self.assertEqual(op.argumentos_de_formato("xyz", 192, 0),
                         op.argumentos_de_formato("mp4", 192, 0))

    def test_portada_solo_donde_corresponde(self):
        con_portada = {"mp4", "audio_original", "mp3", "m4a", "opus", "flac"}
        for _etiqueta, formato in op.FORMATOS:
            with self.subTest(formato=formato):
                args = op.argumentos_de_formato(formato, 192, 1080)
                if formato in con_portada:
                    self.assertIn("--embed-thumbnail", args, formato)
                else:
                    self.assertNotIn("--embed-thumbnail", args, formato)

    def test_metadatos_en_los_nueve(self):
        for _etiqueta, formato in op.FORMATOS:
            with self.subTest(formato=formato):
                self.assertIn("--embed-metadata",
                              op.argumentos_de_formato(formato, 192, 720))

    def test_audio_quality_solo_con_bitrate(self):
        for _etiqueta, formato in op.FORMATOS:
            with self.subTest(formato=formato):
                args = op.argumentos_de_formato(formato, 192, 0)
                if op.clase_de_calidad(formato) == "bitrate":
                    self.assertIn("--audio-quality", args, formato)
                else:
                    self.assertNotIn("--audio-quality", args, formato)

    def test_res_solo_con_resolucion_elegida(self):
        for _etiqueta, formato in op.FORMATOS:
            with self.subTest(formato=formato):
                sin = op.argumentos_de_formato(formato, 192, 0)
                self.assertFalse([a for a in sin if a.startswith("res:")],
                                 formato)
                con = op.argumentos_de_formato(formato, 192, 720)
                tiene = any("res:720" in a for a in con)
                if op.clase_de_calidad(formato) == "resolucion":
                    self.assertTrue(tiene, formato)
                else:
                    self.assertFalse(tiene, formato)


class TestPlantillas(unittest.TestCase):
    def test_cuatro_claves_en_orden(self):
        claves = [clave for _etiqueta, clave, _plantilla in op.PLANTILLAS]
        self.assertEqual(claves, ["titulo_id", "titulo", "canal_titulo",
                                  "fecha_titulo"])

    def test_plantillas_sin_extension(self):
        for _etiqueta, _clave, plantilla in op.PLANTILLAS:
            with self.subTest(plantilla=plantilla):
                self.assertNotIn(".%(ext)s", plantilla)
                self.assertIn("%(title)s", plantilla)

    def test_limites_simultaneas(self):
        self.assertEqual((op.SIMULTANEAS_MIN, op.SIMULTANEAS_MAX,
                          op.SIMULTANEAS_DEFECTO), (1, 5, 2))
        self.assertEqual(op.LIMITE_MAX, 1000)


if __name__ == "__main__":
    unittest.main()
