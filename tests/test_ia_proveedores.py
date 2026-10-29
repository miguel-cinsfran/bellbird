"""Pruebas de los proveedores de IA, sin red ni disco."""

import unittest

from bellbird.ai import catalogo
from bellbird.ai import protocolos
from bellbird.ai import proveedores
from bellbird.core.config import APP_VERSION


def _muestra():
    return {
        "version": catalogo.VERSION,
        "fecha": "2026-10-21",
        "proveedores": {
            "opencode-go": {
                "nombre": "OpenCode Go",
                "modelos": [
                    {"id": "claude-oro",
                     "nombre": "Claude Oro",
                     "protocolo": protocolos.ANTHROPIC,
                     "base": "https://opencode.ai/inference/go/anthropic/v1",
                     "gratis": False, "contributor": False,
                     "piensa": True, "tope_salida": 128000},
                ],
            },
        },
    }


class TestTabla(unittest.TestCase):

    def test_orden_ids_y_nombres(self):
        self.assertEqual(
            [p.id for p in proveedores.PROVEEDORES],
            ["gemini", "openai", "anthropic", "openrouter", "opencode-go",
             "commandcode", "otro"])
        self.assertEqual(
            [p.nombre for p in proveedores.PROVEEDORES],
            ["Google Gemini", "OpenAI", "Anthropic", "OpenRouter",
             "OpenCode Go", "Command Code", "Otro compatible con OpenAI"])

    def test_solo_otro_pide_direccion(self):
        for proveedor in proveedores.PROVEEDORES:
            with self.subTest(proveedor=proveedor.id):
                self.assertEqual(proveedor.pide_direccion,
                                 proveedor.id == "otro")

    def test_otro_sin_catalogo_ni_base(self):
        otro = proveedores.por_id("otro")
        self.assertIsNone(otro.id_catalogo)
        self.assertIsNone(otro.base_por_defecto)
        for proveedor in proveedores.PROVEEDORES:
            if proveedor.id == "otro":
                continue
            with self.subTest(proveedor=proveedor.id):
                self.assertTrue(proveedor.id_catalogo)
                self.assertTrue(proveedor.base_por_defecto)

    def test_defectos_por_proveedor(self):
        esperados = {
            "gemini": (protocolos.GEMINI,
                       "https://generativelanguage.googleapis.com/v1beta"),
            "openai": (protocolos.RESPONSES, "https://api.openai.com/v1"),
            "anthropic": (protocolos.ANTHROPIC,
                          "https://api.anthropic.com/v1"),
            "openrouter": (protocolos.CHAT, "https://openrouter.ai/api/v1"),
            "opencode-go": (
                protocolos.CHAT,
                "https://opencode.ai/inference/go/openai/v1"),
            "commandcode": (
                protocolos.CHAT, "https://api.commandcode.ai/provider/v1"),
        }
        for ident, (protocolo, base) in esperados.items():
            with self.subTest(proveedor=ident):
                proveedor = proveedores.por_id(ident)
                self.assertEqual(proveedor.protocolo_por_defecto, protocolo)
                self.assertEqual(proveedor.base_por_defecto, base)

    def test_por_id_desconocido_da_none(self):
        self.assertIsNone(proveedores.por_id("inexistente"))


class TestResolver(unittest.TestCase):

    def test_catalogo_gana_sobre_el_defecto(self):
        proveedor = proveedores.por_id("opencode-go")
        self.assertEqual(
            proveedores.resolver(proveedor, "claude-oro", _muestra()),
            (protocolos.ANTHROPIC,
             "https://opencode.ai/inference/go/anthropic/v1"))

    def test_ausente_cae_al_defecto(self):
        proveedor = proveedores.por_id("opencode-go")
        self.assertEqual(
            proveedores.resolver(proveedor, "modelo-escrito-a-mano",
                                 _muestra()),
            (protocolos.CHAT,
             "https://opencode.ai/inference/go/openai/v1"))

    def test_otro_con_direccion_buena(self):
        otro = proveedores.por_id("otro")
        self.assertEqual(
            proveedores.resolver(otro, "cualquiera", _muestra(),
                                 "https://mio.example.com/v1"),
            (protocolos.CHAT, "https://mio.example.com/v1"))

    def test_otro_quita_espacios_y_barra_final(self):
        otro = proveedores.por_id("otro")
        self.assertEqual(
            proveedores.resolver(otro, "cualquiera", _muestra(),
                                 "  https://mio.example.com/v1/  "),
            (protocolos.CHAT, "https://mio.example.com/v1"))

    def test_otro_con_direccion_mala(self):
        otro = proveedores.por_id("otro")
        for mala in ("", "   ", "mio.example.com/v1", "ftp://mio/x",
                     "http:/mio"):
            with self.subTest(direccion=mala):
                with self.assertRaises(ValueError):
                    proveedores.resolver(otro, "cualquiera", _muestra(),
                                         mala)


class TestCabeceras(unittest.TestCase):

    def test_opencode_go_lleva_sesion_y_agente(self):
        proveedor = proveedores.por_id("opencode-go")
        cabeceras = proveedores.cabeceras(proveedor, "sesion-1")
        self.assertEqual(cabeceras["x-opencode-session"], "sesion-1")
        self.assertEqual(cabeceras["User-Agent"],
                         "Bellbird/{}".format(APP_VERSION))

    def test_el_resto_vacio(self):
        for proveedor in proveedores.PROVEEDORES:
            if proveedor.id == "opencode-go":
                continue
            with self.subTest(proveedor=proveedor.id):
                self.assertEqual(proveedores.cabeceras(proveedor, "s"), {})


if __name__ == "__main__":
    unittest.main()
