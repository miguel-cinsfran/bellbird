"""Pruebas puras de los textos de la subventana de captura.

Sin wx.App ni ventanas: solo importa las constantes y `texto_negra`
del módulo, que no crea controles al importarse.
"""

import unittest

from ytchat.ui.ia_agregar_captura import (
    TEXTO_CARGANDO,
    TEXTO_OBS_CERRADO,
    texto_negra,
)


class TestTextosAgregarCaptura(unittest.TestCase):

    def test_cargando(self):
        self.assertEqual(TEXTO_CARGANDO, "Cargando las fuentes de OBS…")

    def test_obs_cerrado(self):
        self.assertEqual(TEXTO_OBS_CERRADO, "OBS no está abierto.")

    def test_negra_nombra_la_fuente(self):
        self.assertEqual(
            texto_negra("Escena al aire: Escena"),
            "La captura de Escena al aire: Escena salió negra y no se "
            "agregó. Si usas la cortina de pantalla de NVDA, cambia en OBS "
            "el método de captura de esa fuente a Windows 10.")

    def test_negra_con_etiqueta_simple(self):
        texto = texto_negra("Cámara")
        self.assertIn("Cámara", texto)
        self.assertIn("Windows 10", texto)


if __name__ == "__main__":
    unittest.main()
