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
                    _modelo("regalado-falso", "Regalado Falso",
                            protocolos.CHAT,
                            "https://openrouter.ai/api/v1",
                            gratis=True),
                    _modelo("regalado-falso-contributor",
                            "Regalado Falso Contributor",
                            protocolos.CHAT,
                            "https://openrouter.ai/api/v1",
                            gratis=True, contributor=True),
                ],
            },
        },
    }


class TestFilasModelos(unittest.TestCase):

    def test_gemini_no_marca_gratis_ni_filtra(self):
        from ytchat.ai import opciones_ia
        proveedor = proveedores.por_id("gemini")
        esperadas = [("gemini-falso", "Gemini Falso"),
                     ("gemini-caro", "Gemini Caro")]
        self.assertEqual(
            opciones_ia.filas_modelos(_muestra(), proveedor, False),
            esperadas)
        self.assertEqual(
            opciones_ia.filas_modelos(_muestra(), proveedor, True),
            esperadas)

    def test_openrouter_conserva_gratis_y_su_filtro(self):
        from ytchat.ai import opciones_ia
        proveedor = proveedores.por_id("openrouter")
        filas = dict(opciones_ia.filas_modelos(_muestra(), proveedor, False))
        self.assertEqual(
            filas["writely-falso-contributor"],
            "Writely Falso, entrena con lo enviado")
        self.assertEqual(filas["regalado-falso"], "Regalado Falso, gratis")
        self.assertEqual(
            filas["regalado-falso-contributor"],
            "Regalado Falso Contributor, gratis, entrena con lo enviado")
        solo_gratis = dict(opciones_ia.filas_modelos(
            _muestra(), proveedor, True))
        self.assertEqual(
            set(solo_gratis),
            {"regalado-falso", "regalado-falso-contributor"})

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
            _muestra(), proveedores.por_id("openrouter"), True)
        self.assertEqual(
            opciones_ia.separar_modelo_guardado(
                "writely-falso-contributor", filas),
            ("", "writely-falso-contributor"))


class TestAvisoDeModelo(unittest.TestCase):

    def test_con_contributor_avisa_corto(self):
        from ytchat.ai import opciones_ia
        modelos = catalogo.modelos(_muestra(), "openrouter")
        modelo = next(m for m in modelos if m.contributor)
        self.assertEqual(opciones_ia.aviso_de_modelo(modelo),
                         "Este modelo entrena con lo que se le envía.")
        self.assertEqual(opciones_ia.TEXTO_CONTRIBUTOR,
                         "Este modelo entrena con lo que se le envía.")

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


class TestEstadoDeClave(unittest.TestCase):

    def test_sin_clave_no_dice_nada(self):
        from ytchat.ai import opciones_ia
        self.assertEqual(opciones_ia.estado_de_clave(""), "")
        self.assertEqual(opciones_ia.estado_de_clave(None), "")

    def test_clave_corta_solo_dice_guardada(self):
        from ytchat.ai import opciones_ia
        for clave in ("abcd", "abcdefg"):
            with self.subTest(clave=clave):
                self.assertEqual(opciones_ia.estado_de_clave(clave),
                                 "Guardada")

    def test_clave_de_ocho_o_mas_muestra_los_ultimos_cuatro(self):
        from ytchat.ai import opciones_ia
        self.assertEqual(opciones_ia.estado_de_clave("abcdefgh"),
                         "Guardada, termina en efgh")
        clave = "clave-de-prueba-de-treinta-y-nueve-1234"
        self.assertEqual(len(clave), 39)
        self.assertEqual(opciones_ia.estado_de_clave(clave),
                         "Guardada, termina en 1234")

    def test_nunca_muestra_mas_de_cuatro_caracteres_de_la_clave(self):
        from ytchat.ai import opciones_ia
        claves = ("abcd", "abcdefg", "abcdefgh", "A" * 39)
        for clave in claves:
            with self.subTest(clave=clave):
                texto = opciones_ia.estado_de_clave(clave)
                for largo in range(5, len(clave) + 1):
                    for inicio in range(len(clave) - largo + 1):
                        self.assertNotIn(clave[inicio:inicio + largo], texto)


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


class TestProblemaDeClave(unittest.TestCase):

    CLAVE_GEMINI = "AIza" + "a" * 35
    CLAVE_OPENROUTER = "sk-or-v1-" + "a" * 29
    CLAVE_OTRO = "clave-larga-de-veinte-y-mas"

    @staticmethod
    def _casos():
        from ytchat.ai import opciones_ia
        return (
            ("gemini", "", opciones_ia.TEXTO_FALTA_CLAVE),
            ("gemini", "     ", opciones_ia.TEXTO_FALTA_CLAVE),
            ("gemini", "asdf", opciones_ia.TEXTO_CLAVE_CORTA),
            ("gemini", "a" * 19, opciones_ia.TEXTO_CLAVE_CORTA),
            ("gemini", "a" * 20, opciones_ia.TEXTO_CLAVE_PREFIJO.format(
                proveedor="Google Gemini", prefijo="AIza")),
            ("gemini", "AIza" + "a" * 16, ""),
            ("gemini", "AIza" + "a" * 8 + " " + "a" * 7,
             opciones_ia.TEXTO_CLAVE_CARACTERES),
            ("gemini", "AIza" + "a" * 15 + "ñ",
             opciones_ia.TEXTO_CLAVE_CARACTERES),
            ("gemini", "AIza" + "a" * 15 + "/",
             opciones_ia.TEXTO_CLAVE_CARACTERES),
            ("openrouter", "a" * 30, opciones_ia.TEXTO_CLAVE_PREFIJO.format(
                proveedor="OpenRouter", prefijo="sk-or-")),
            ("openrouter", TestProblemaDeClave.CLAVE_OPENROUTER, ""),
            ("otro", TestProblemaDeClave.CLAVE_OTRO, ""),
            ("gemini", "  " + TestProblemaDeClave.CLAVE_GEMINI + "  ", ""),
            ("gemini", "  " + "a" * 19 + "  ",
             opciones_ia.TEXTO_CLAVE_CORTA),
        )

    def _problema(self, proveedor, clave):
        from ytchat.ai import opciones_ia
        return opciones_ia.problema_de_clave(
            proveedores.por_id(proveedor), clave)

    def test_los_casos_dan_el_problema_esperado(self):
        for proveedor, clave, esperado in self._casos():
            with self.subTest(proveedor=proveedor, clave=clave):
                self.assertEqual(self._problema(proveedor, clave), esperado)

    def test_toda_clave_aceptada_tiene_forma(self):
        from ytchat.ai import opciones_ia
        permitidos = set(
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789-_.")
        for proveedor, clave, _esperado in self._casos():
            with self.subTest(proveedor=proveedor, clave=clave):
                if opciones_ia.problema_de_clave(
                        proveedores.por_id(proveedor), clave):
                    continue
                limpia = clave.strip()
                self.assertGreaterEqual(len(limpia), 20)
                self.assertLessEqual(set(limpia), permitidos)


if __name__ == "__main__":
    unittest.main()
