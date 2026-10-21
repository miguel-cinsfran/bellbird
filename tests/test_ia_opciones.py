"""Pruebas de la lógica pura de la página Inteligencia artificial.

Sin wx, sin red y sin el Administrador de credenciales: solo el módulo
`opciones_ia` y los catálogos armados a mano.
"""

import unittest

from ytchat.ai import catalogo
from ytchat.ai import consulta
from ytchat.ai import conversacion
from ytchat.ai import protocolos
from ytchat.ai import proveedores
from ytchat.ai.ajustes_ia import AjustesIA
from ytchat.ai.conversacion import Conversacion


def _muestra():
    """Un modelo por protocolo, con un gratis y un contributor de más."""

    def _modelo(ident, nombre, protocolo, base, gratis=False,
               contributor=False, piensa=False, tope=None):
        return {"id": ident, "nombre": nombre, "protocolo": protocolo,
                "base": base, "gratis": gratis,
                "contributor": contributor, "piensa": piensa,
                "tope_salida": tope}

    return {
        "version": catalogo.VERSION,
        "fecha": "2026-10-21",
        "proveedores": {
            "google": {
                "nombre": "Google",
                "modelos": [
                    _modelo("gemini-falso", "Gemini Falso",
                            protocolos.GEMINI,
                            "https://generativelanguage.googleapis.com/v1beta",
                            gratis=True),
                    _modelo("gemini-caro", "Gemini Caro",
                            protocolos.GEMINI,
                            "https://generativelanguage.googleapis.com/v1beta"),
                ],
            },
            "openai": {
                "nombre": "OpenAI",
                "modelos": [
                    _modelo("gpt-falso", "GPT Falso",
                            protocolos.RESPONSES,
                            "https://api.openai.com/v1",
                            piensa=True, tope=8000),
                ],
            },
            "anthropic": {
                "nombre": "Anthropic",
                "modelos": [
                    _modelo("claude-falso", "Claude Falso",
                            protocolos.ANTHROPIC,
                            "https://api.anthropic.com/v1"),
                ],
            },
            "openrouter": {
                "nombre": "OpenRouter",
                "modelos": [
                    _modelo("writely-falso-contributor", "Writely Falso",
                            protocolos.CHAT,
                            "https://openrouter.ai/api/v1",
                            contributor=True),
                ],
            },
        },
    }


class TestFilasModelos(unittest.TestCase):

    def test_filas_con_etiqueta_y_gratis(self):
        from ytchat.ai import opciones_ia
        filas = opciones_ia.filas_modelos(
            _muestra(), proveedores.por_id("gemini"), False)
        self.assertEqual(filas, [("gemini-falso", "Gemini Falso, gratis"),
                                 ("gemini-caro", "Gemini Caro")])

    def test_solo_gratis_filtra(self):
        from ytchat.ai import opciones_ia
        filas = opciones_ia.filas_modelos(
            _muestra(), proveedores.por_id("gemini"), True)
        self.assertEqual(filas, [("gemini-falso", "Gemini Falso, gratis")])

    def test_proveedor_sin_catalogo_da_lista_vacia(self):
        from ytchat.ai import opciones_ia
        self.assertEqual(
            opciones_ia.filas_modelos(
                _muestra(), proveedores.por_id("otro"), False), [])
        self.assertEqual(
            opciones_ia.filas_modelos(
                _muestra(), proveedores.por_id("otro"), True), [])


class TestModeloElegido(unittest.TestCase):

    def test_otro_gana_sobre_la_lista(self):
        from ytchat.ai import opciones_ia
        self.assertEqual(
            opciones_ia.modelo_elegido("gemini-falso", "gpt-falso"),
            "gpt-falso")

    def test_otro_con_espacios_se_recorta(self):
        from ytchat.ai import opciones_ia
        self.assertEqual(
            opciones_ia.modelo_elegido("gemini-falso", "  gpt-falso  "),
            "gpt-falso")

    def test_otro_vacio_deja_la_lista(self):
        from ytchat.ai import opciones_ia
        self.assertEqual(
            opciones_ia.modelo_elegido("gemini-falso", "   "),
            "gemini-falso")

    def test_sin_lista_ni_otro_da_vacio(self):
        from ytchat.ai import opciones_ia
        self.assertEqual(opciones_ia.modelo_elegido("", ""), "")

    def test_marcador_sin_modelos_cuenta_como_vacio(self):
        from ytchat.ai import opciones_ia
        self.assertEqual(
            opciones_ia.modelo_elegido(opciones_ia.TEXTO_SIN_MODELOS, ""),
            "")


class TestSepararModeloGuardado(unittest.TestCase):

    def test_guardado_en_filas_va_a_la_lista(self):
        from ytchat.ai import opciones_ia
        filas = opciones_ia.filas_modelos(
            _muestra(), proveedores.por_id("gemini"), False)
        self.assertEqual(
            opciones_ia.separar_modelo_guardado("gemini-caro", filas),
            ("gemini-caro", ""))

    def test_guardado_fuera_de_filas_va_a_otro(self):
        from ytchat.ai import opciones_ia
        filas = opciones_ia.filas_modelos(
            _muestra(), proveedores.por_id("gemini"), True)
        self.assertEqual(
            opciones_ia.separar_modelo_guardado("gemini-caro", filas),
            ("", "gemini-caro"))


class TestAvisoDeModelo(unittest.TestCase):

    def test_con_contributor_avisa(self):
        from ytchat.ai import opciones_ia
        modelos = catalogo.modelos(_muestra(), "openrouter")
        modelo = next(m for m in modelos if m.contributor)
        self.assertEqual(opciones_ia.aviso_de_modelo(modelo),
                         opciones_ia.TEXTO_CONTRIBUTOR)

    def test_sin_contributor_no_avisa(self):
        from ytchat.ai import opciones_ia
        modelos = catalogo.modelos(_muestra(), "google")
        for modelo in modelos:
            with self.subTest(modelo=modelo.id):
                self.assertFalse(modelo.contributor)
                self.assertEqual(opciones_ia.aviso_de_modelo(modelo), "")

    def test_sin_modelo_no_avisa(self):
        from ytchat.ai import opciones_ia
        self.assertEqual(opciones_ia.aviso_de_modelo(None), "")


class TestNombreDeClave(unittest.TestCase):

    def test_guardada_y_sin_guardar(self):
        from ytchat.ai import opciones_ia
        proveedor = proveedores.por_id("gemini")
        self.assertEqual(
            opciones_ia.nombre_de_clave(proveedor, True),
            "Clave de Google Gemini, guardada")
        self.assertEqual(
            opciones_ia.nombre_de_clave(proveedor, False),
            "Clave de Google Gemini, sin guardar")


class TestPedidoDePrueba(unittest.TestCase):

    def _pedido(self, proveedor, modelo, clave="clave"):
        from ytchat.ai import opciones_ia
        ajustes = AjustesIA(proveedor=proveedor, modelo=modelo)
        return opciones_ia.pedido_de_prueba(ajustes, _muestra(), clave)

    def test_un_proveedor_de_cada_protocolo(self):
        from ytchat.ai import opciones_ia
        casos = (
            ("gemini", "gemini-falso", protocolos.GEMINI,
             "https://generativelanguage.googleapis.com/v1beta"),
            ("openai", "gpt-falso", protocolos.RESPONSES,
             "https://api.openai.com/v1"),
            ("anthropic", "claude-falso", protocolos.ANTHROPIC,
             "https://api.anthropic.com/v1"),
            ("openrouter", "writely-falso-contributor", protocolos.CHAT,
             "https://openrouter.ai/api/v1"),
        )
        for proveedor, modelo, protocolo, base in casos:
            with self.subTest(proveedor=proveedor):
                pedido = self._pedido(proveedor, modelo)
                self.assertEqual(pedido.protocolo, protocolo)
                self.assertTrue(pedido.url.startswith(base))
                self.assertIn(modelo, pedido.url + str(pedido.cuerpo))
                self.assertIn(opciones_ia.TEXTO_PEDIDO_PRUEBA,
                              str(pedido.cuerpo))
                self.assertNotIn("base64", str(pedido.cuerpo))
                self.assertIn("Responde con una sola palabra.",
                              str(pedido.cuerpo))

    def test_tope_segun_piensa_y_tope_del_catalogo(self):
        pedido = self._pedido("openai", "gpt-falso")
        self.assertEqual(
            pedido.cuerpo["max_output_tokens"],
            conversacion.max_tokens(conversacion.CORTA, True, 8000))
        pedido = self._pedido("gemini", "gemini-falso")
        self.assertEqual(
            pedido.cuerpo["generationConfig"]["maxOutputTokens"],
            conversacion.max_tokens(conversacion.CORTA, False, None))

    def test_sin_modelo_levanta_como_preparar(self):
        from ytchat.ai import opciones_ia
        ajustes = AjustesIA(proveedor="gemini", modelo="   ")
        with self.assertRaises(consulta.FaltaConfiguracion) as salida:
            opciones_ia.pedido_de_prueba(ajustes, _muestra(), "clave")
        charla = Conversacion()
        with self.assertRaises(consulta.FaltaConfiguracion) as esperada:
            consulta.preparar(charla, "hola", ajustes, {}, "clave", "")
        self.assertEqual(str(salida.exception), str(esperada.exception))


if __name__ == "__main__":
    unittest.main()
