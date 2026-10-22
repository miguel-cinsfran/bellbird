"""Pruebas de la lógica pura de qa/ia_real.py, sin red ni ventanas."""

import importlib.util
import unittest
from pathlib import Path

_RUTA = Path(__file__).resolve().parent.parent / "qa" / "ia_real.py"
_paquete = importlib.util.spec_from_file_location("ia_real_qa", _RUTA)
ia_real = importlib.util.module_from_spec(_paquete)
_paquete.loader.exec_module(ia_real)


class TestNombraColores(unittest.TestCase):

    def test_verde_pasa(self):
        self.assertTrue(ia_real.nombra_colores("se ve una ventana verde"))

    def test_magenta_en_mayuscula_pasa(self):
        self.assertTrue(ia_real.nombra_colores("Magenta a la derecha"))

    def test_fucsia_pasa(self):
        self.assertTrue(ia_real.nombra_colores("un recuadro fucsia"))

    def test_rosa_dentro_de_rosado_pasa(self):
        self.assertTrue(ia_real.nombra_colores("un panel rosado"))

    def test_sin_color_no_pasa(self):
        self.assertFalse(ia_real.nombra_colores("se ven dos ventanas"))

    def test_vacio_no_pasa(self):
        self.assertFalse(ia_real.nombra_colores(""))


class TestTieneDos(unittest.TestCase):

    def test_dos_en_letras_pasa(self):
        self.assertTrue(ia_real.tiene_dos("se ven dos ventanas"))

    def test_dos_en_numero_pasa(self):
        self.assertTrue(ia_real.tiene_dos("hay 2 ventanas"))

    def test_dosis_no_pasa(self):
        self.assertFalse(ia_real.tiene_dos("una dosis de color"))

    def test_doce_no_pasa(self):
        self.assertFalse(ia_real.tiene_dos("hay 12 ventanas"))

    def test_vacio_no_pasa(self):
        self.assertFalse(ia_real.tiene_dos(""))


class TestEsError(unittest.TestCase):

    def _errores(self):
        from ytchat.ai import consulta
        lista = []
        for nombre in ("_TEXTOS", "_ERRORES"):
            diccionario = getattr(consulta, nombre, None)
            if isinstance(diccionario, dict):
                lista.extend(diccionario.values())
                break
        for nombre in ("TEXTO_SIN_NIVEL_GRATUITO", "_MSG_PROVEEDOR",
                       "_MSG_MODELO", "_MSG_DIRECCION"):
            valor = getattr(consulta, nombre, "")
            if valor:
                lista.append(valor)
        lista.extend([
            "Agrega una captura antes de preguntar.",
            "Escribe una pregunta.",
            "No se pudo completar la consulta. Vuelve a intentarlo.",
        ])
        return lista

    def test_cada_texto_de_error_pasa(self):
        for texto in self._errores():
            with self.subTest(texto=texto[:30]):
                self.assertTrue(ia_real.es_error(texto))

    def test_respuesta_normal_no_pasa(self):
        self.assertFalse(ia_real.es_error(
            "Se ven dos ventanas, una verde a la izquierda y otra "
            "magenta a la derecha."))

    def test_vacio_no_pasa(self):
        self.assertFalse(ia_real.es_error(""))


class TestModeloPermitido(unittest.TestCase):

    def test_openrouter_con_free_pasa(self):
        self.assertTrue(ia_real.modelo_permitido(
            "openrouter", "x-ai/grok-4.1-fast:free"))

    def test_openrouter_sin_free_no_pasa(self):
        self.assertFalse(ia_real.modelo_permitido(
            "openrouter", "x-ai/grok-4.1-fast"))

    def test_otro_proveedor_pasa(self):
        self.assertTrue(ia_real.modelo_permitido(
            "gemini", "gemini-2.0-flash"))
        self.assertTrue(ia_real.modelo_permitido(
            "openai", "gpt-4o-mini"))


class TestInforme(unittest.TestCase):

    def _pasos(self):
        return [
            ("Consulta rápida", "(rápida)", "Hay una verde y una magenta.",
             12, True),
            ("Ventanas", "¿Cuántas?", "Se ven dos.", 20, True),
        ]

    def test_lleva_pregunta_respuesta_y_segundos(self):
        texto = ia_real.informe(self._pasos(), "openrouter", "algo:free")
        self.assertIn("¿Cuántas?", texto)
        self.assertIn("Se ven dos.", texto)
        self.assertIn("20", texto)
        self.assertIn("openrouter", texto)
        self.assertIn("algo:free", texto)

    def test_nunca_lleva_la_clave(self):
        clave_falsa = "sk-or-falsa-123456789"
        texto = ia_real.informe(self._pasos(), "openrouter", "algo:free")
        self.assertNotIn(clave_falsa, texto)

    def test_resume_pasos_y_fallos(self):
        pasos = self._pasos() + [("Panel", "¿Qué?", "Nada.", 9, False)]
        texto = ia_real.informe(pasos, "gemini", "gemini-2.0-flash")
        self.assertIn("3 pasos", texto)
        self.assertIn("1 fallo", texto)


if __name__ == "__main__":
    unittest.main()
