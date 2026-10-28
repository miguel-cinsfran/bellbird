"""Pseudotraducción de los textos puros de Inteligencia artificial.

Sin ventanas: llama a las funciones de `opciones_ia` bajo `con_pseudo()`
y exige los fragmentos propios marcados y los datos sin marcar. Los
nombres de modelos y proveedores son datos y pasan sin marcar.
"""

import unittest

from tests.pseudo_prueba import con_pseudo
from ytchat.ai import catalogo
from ytchat.ai import opciones_ia
from ytchat.ai import protocolos
from ytchat.ai import proveedores
from ytchat.core.idioma import _


def _muestra():
    """Un proveedor con un modelo gratis y uno contributor."""

    def _modelo(ident, nombre, gratis=False, contributor=False):
        return {"id": ident, "nombre": nombre, "protocolo": protocolos.CHAT,
                "base": "https://openrouter.ai/api/v1", "gratis": gratis,
                "contributor": contributor, "piensa": False,
                "tope_salida": None}

    return {
        "version": catalogo.VERSION,
        "fecha": "2026-10-21",
        "proveedores": {
            "openrouter": {
                "nombre": "OpenRouter",
                "modelos": [
                    _modelo("regalado-falso", "Regalado Falso", gratis=True),
                    _modelo("writely-falso", "Writely Falso",
                            contributor=True),
                ],
            },
        },
    }


class TestFilasMarcadas(unittest.TestCase):

    def test_sufijos_propios_van_marcados_y_nombres_no(self):
        proveedor = proveedores.por_id("openrouter")
        with con_pseudo():
            filas = dict(opciones_ia.filas_modelos(_muestra(), proveedor,
                                                   False))
        self.assertEqual(filas["regalado-falso"],
                         "Regalado Falso[¡, gratis!]")
        self.assertEqual(filas["writely-falso"],
                         "Writely Falso[¡, entrena con lo enviado!]")

    def test_resumen_problema_y_estado_van_marcados(self):
        from ytchat.ai import sondeo_gratis
        resultados = {"a": sondeo_gratis.RESPONDE}
        with con_pseudo():
            resumen = opciones_ia.resumen_sondeo(resultados, 1,
                                                 "Google Gemini")
            falta = opciones_ia.problema_de_clave(
                proveedores.por_id("gemini"), "")
            corta = opciones_ia.problema_de_clave(
                proveedores.por_id("gemini"), "corta")
            guardada = opciones_ia.estado_de_clave("abcdefgh")
            solo = opciones_ia.estado_de_clave("abc")
        for texto in (resumen, falta, corta, guardada, solo):
            with self.subTest(texto=texto):
                self.assertTrue(texto.startswith("[¡"), texto)


if __name__ == "__main__":
    unittest.main()
