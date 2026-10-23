"""Pruebas de la lectura de la sección [lectura] (config_lectura)."""

import unittest

from ytchat.core import config
from ytchat.core import config_lectura


class TestOpcionesLectura(unittest.TestCase):

    def _leer(self, contenido: str) -> dict:
        p = config._mk_parser()
        p.read_string(contenido, source="config.ini")
        return config_lectura.opciones_lectura(p)

    def test_los_cuatro_formatos_validos_se_conservan(self):
        for formato in ("nombre_mensaje", "mensaje_nombre", "solo_mensaje",
                        "solo_nombre"):
            with self.subTest(formato=formato):
                opciones = self._leer(
                    f"[lectura]\nformato_prefijo = {formato}\n")
                self.assertEqual(opciones["formato_prefijo"], formato)

    def test_formato_invalido_cae_a_nombre_mensaje(self):
        opciones = self._leer("[lectura]\nformato_prefijo = raro\n")
        self.assertEqual(opciones["formato_prefijo"], "nombre_mensaje")

    def test_formato_vacio_cae_a_nombre_mensaje(self):
        opciones = self._leer("[lectura]\nformato_prefijo =\n")
        self.assertEqual(opciones["formato_prefijo"], "nombre_mensaje")

    def test_atajos_globales_se_lee_en_true_y_en_false(self):
        for valor, esperado in (("true", True), ("false", False)):
            with self.subTest(valor=valor):
                opciones = self._leer(
                    f"[lectura]\natajos_globales = {valor}\n")
                self.assertEqual(
                    opciones["lectura_atajos_globales"], esperado)

    def test_recientes_lector_y_voz_se_conservan(self):
        for valor in ("lector", "voz"):
            with self.subTest(valor=valor):
                opciones = self._leer(
                    f"[lectura]\nrecientes = {valor}\n")
                self.assertEqual(opciones["lectura_recientes"], valor)

    def test_recientes_en_mayusculas_se_normaliza(self):
        opciones = self._leer("[lectura]\nrecientes = VOZ\n")
        self.assertEqual(opciones["lectura_recientes"], "voz")

    def test_recientes_invalido_o_vacio_cae_a_lector(self):
        for contenido in ("[lectura]\nrecientes = raro\n",
                          "[lectura]\nrecientes =\n",
                          "[lectura]\nformato_prefijo = solo_mensaje\n"):
            with self.subTest(contenido=contenido):
                opciones = self._leer(contenido)
                self.assertEqual(opciones["lectura_recientes"], "lector")


if __name__ == "__main__":
    unittest.main()
