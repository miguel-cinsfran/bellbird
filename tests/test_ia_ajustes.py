"""Pruebas de los ajustes de IA, sin red ni ventanas."""

import tempfile
import unittest
from pathlib import Path

from ytchat.ai import ajustes_ia
from ytchat.ai.ajustes_ia import AjustesIA
from ytchat.ai import conversacion


def _escribir(ruta, texto):
    Path(ruta).write_text(texto, encoding="utf-8")


class TestFabrica(unittest.TestCase):

    def test_valores_por_defecto(self):
        fabrica = AjustesIA()
        self.assertEqual(
            (fabrica.proveedor, fabrica.modelo, fabrica.direccion,
              fabrica.pregunta, fabrica.largo, fabrica.tiempo_espera,
              fabrica.solo_gratis, fabrica.privacidad_aceptada,
              fabrica.decir_analizando),
            ("gemini", "", "", "", "media", 60, False, False, True))


class TestLeer(unittest.TestCase):

    def test_sin_archivo_da_la_fabrica(self):
        with tempfile.TemporaryDirectory() as tmp:
            leidos = ajustes_ia.leer(Path(tmp) / "no-existe.ini")
        self.assertEqual(leidos, AjustesIA())

    def test_archivo_roto_da_la_fabrica(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.ini"
            _escribir(ruta, "[ia\nsin cerrar = ")
            self.assertEqual(ajustes_ia.leer(ruta), AjustesIA())

    def test_seccion_ausente_da_la_fabrica(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.ini"
            _escribir(ruta, "[otra]\nclave = valor\n")
            self.assertEqual(ajustes_ia.leer(ruta), AjustesIA())

    def test_seccion_vacia_da_la_fabrica(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.ini"
            _escribir(ruta, "[ia]\n")
            self.assertEqual(ajustes_ia.leer(ruta), AjustesIA())

    def test_clave_ausente_toma_la_fabrica(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.ini"
            _escribir(ruta, "[ia]\nproveedor = openai\n")
            leidos = ajustes_ia.leer(ruta)
            self.assertEqual(leidos.proveedor, "openai")
            self.assertEqual(leidos.modelo, "")
            self.assertEqual(leidos.largo, "media")
            self.assertEqual(leidos.tiempo_espera, 60)
            self.assertFalse(leidos.solo_gratis)
            self.assertTrue(leidos.decir_analizando)

    def test_raros_se_normalizan(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.ini"
            _escribir(ruta, "[ia]\nproveedor = inventado\nlargo = enorme\n"
                            "tiempo_espera = muchísimo\n"
                            "solo_gratis = sí\n"
                            "privacidad_aceptada = no\n"
                            "decir_analizando = tal vez\n"
                            "modelo =   hola  \n"
                            "direccion =   https://mio.example.com/v1/  \n")
            leidos = ajustes_ia.leer(ruta)
            self.assertEqual(leidos.proveedor, "gemini")
            self.assertEqual(leidos.largo, "media")
            self.assertEqual(leidos.tiempo_espera, 60)
            self.assertFalse(leidos.solo_gratis)
            self.assertFalse(leidos.privacidad_aceptada)
            self.assertTrue(leidos.decir_analizando)
            self.assertEqual(leidos.modelo, "hola")
            self.assertEqual(leidos.direccion,
                             "https://mio.example.com/v1/")

    def test_tiempo_fuera_de_rango_se_acota(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.ini"
            _escribir(ruta, "[ia]\ntiempo_espera = 5\n")
            self.assertEqual(ajustes_ia.leer(ruta).tiempo_espera, 10)
            _escribir(ruta, "[ia]\ntiempo_espera = 9999\n")
            self.assertEqual(ajustes_ia.leer(ruta).tiempo_espera, 300)

    def test_booleanos_como_los_lee_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.ini"
            _escribir(ruta, "[ia]\nsolo_gratis = yes\n"
                            "privacidad_aceptada = 1\n"
                            "decir_analizando = off\n")
            leidos = ajustes_ia.leer(ruta)
            self.assertTrue(leidos.solo_gratis)
            self.assertTrue(leidos.privacidad_aceptada)
            self.assertFalse(leidos.decir_analizando)


class TestGuardar(unittest.TestCase):

    def test_pregunta_dificil_vuelve_igual(self):
        rara = "línea uno\nlínea dos 100% # etiqueta ; fin \\ corte"
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.ini"
            _escribir(ruta, "[ia]\nproveedor = gemini\n")
            ajustes = AjustesIA(pregunta=rara, modelo="m",
                                solo_gratis=True,
                                privacidad_aceptada=True, tiempo_espera=90)
            self.assertTrue(ajustes_ia.guardar(ruta, ajustes))
            leidos = ajustes_ia.leer(ruta)
            self.assertEqual(leidos.pregunta, rara)
            self.assertEqual(leidos.modelo, "m")
            self.assertTrue(leidos.solo_gratis)
            self.assertTrue(leidos.privacidad_aceptada)
            self.assertEqual(leidos.tiempo_espera, 90)

    def test_guardar_conserva_el_resto(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.ini"
            _escribir(ruta, "[ia]\nproveedor = gemini\n\n[otra]\n"
                            "# comentario que sigue igual\n"
                            "clave = valor\n")
            ajustes = AjustesIA(proveedor="openai", modelo="gpt-x")
            self.assertTrue(ajustes_ia.guardar(ruta, ajustes))
            texto = Path(ruta).read_text(encoding="utf-8")
            self.assertIn("# comentario que sigue igual", texto)
            self.assertIn("clave = valor", texto)
            leidos = ajustes_ia.leer(ruta)
            self.assertEqual(leidos.proveedor, "openai")
            self.assertEqual(leidos.modelo, "gpt-x")

    def test_decir_analizando_vuelve_igual(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.ini"
            _escribir(ruta, "[ia]\nproveedor = gemini\n")
            ajustes = AjustesIA(decir_analizando=False)
            self.assertTrue(ajustes_ia.guardar(ruta, ajustes))
            self.assertFalse(ajustes_ia.leer(ruta).decir_analizando)


class TestGuardarDecirAnalizando(unittest.TestCase):

    def test_escribe_solo_esa_clave_y_conserva_el_resto(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.ini"
            _escribir(ruta, "[ia]\nproveedor = gemini\n"
                            "decir_analizando = true\n\n[otra]\n"
                            "clave = valor\n")
            self.assertTrue(
                ajustes_ia.guardar_decir_analizando(ruta, False))
            texto = Path(ruta).read_text(encoding="utf-8")
            self.assertIn("proveedor = gemini", texto)
            self.assertIn("decir_analizando = false", texto)
            self.assertIn("clave = valor", texto)
            leidos = ajustes_ia.leer(ruta)
            self.assertFalse(leidos.decir_analizando)
            self.assertEqual(leidos.proveedor, "gemini")
            self.assertTrue(
                ajustes_ia.guardar_decir_analizando(ruta, True))
            self.assertTrue(ajustes_ia.leer(ruta).decir_analizando)


class TestGuardarPrivacidadAceptada(unittest.TestCase):

    def test_escribe_solo_esa_clave_y_conserva_el_resto(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "config.ini"
            _escribir(ruta, "[ia]\nproveedor = openai\n"
                            "privacidad_aceptada = false\n\n[otra]\n"
                            "clave = valor\n")
            self.assertTrue(
                ajustes_ia.guardar_privacidad_aceptada(ruta, True))
            texto = Path(ruta).read_text(encoding="utf-8")
            self.assertIn("proveedor = openai", texto)
            self.assertIn("privacidad_aceptada = true", texto)
            self.assertIn("clave = valor", texto)
            leidos = ajustes_ia.leer(ruta)
            self.assertTrue(leidos.privacidad_aceptada)
            self.assertEqual(leidos.proveedor, "openai")


class TestPreguntaEfectiva(unittest.TestCase):

    def test_vacia_usa_la_de_fabrica(self):
        for vacia in ("", "   "):
            with self.subTest(vacia=repr(vacia)):
                self.assertEqual(
                    ajustes_ia.pregunta_efectiva(AjustesIA(pregunta=vacia)),
                    conversacion.PREGUNTA_INICIAL)

    def test_con_texto_quita_bordes(self):
        self.assertEqual(
            ajustes_ia.pregunta_efectiva(AjustesIA(pregunta="  hola  ")),
            "hola")


if __name__ == "__main__":
    unittest.main()
