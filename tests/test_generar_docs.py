"""Pruebas de las referencias y conversiones de la documentación."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import generar_docs


class DocumentosTest(unittest.TestCase):

    def test_los_documentos_de_origen_existen(self):
        for origen, _, _, _ in generar_docs.documentos():
            self.assertTrue(origen.exists(), f"No existe el documento {origen}")

    def test_descubre_los_md_de_cada_carpeta_de_idioma(self):
        with tempfile.TemporaryDirectory() as temporal:
            docs = Path(temporal)
            (docs / "CONFIGURACION_API.md").write_text("# Guía", encoding="utf-8")
            for idioma in ("es", "en"):
                (docs / idioma).mkdir()
                for nombre in ("MANUAL", "CHANGELOG"):
                    (docs / idioma / f"{nombre}.md").write_text(
                        "# Documento", encoding="utf-8")
            with patch.object(generar_docs, "DOCS", docs):
                encontrados = {
                    (origen.relative_to(docs).as_posix(),
                     destino.relative_to(docs).as_posix(), idioma)
                    for origen, destino, _, idioma in generar_docs.documentos()
                }

        self.assertEqual(encontrados, {
            ("CONFIGURACION_API.md", "CONFIGURACION_API.html", "es"),
            ("es/MANUAL.md", "es/MANUAL.html", "es"),
            ("es/CHANGELOG.md", "es/CHANGELOG.html", "es"),
            ("en/MANUAL.md", "en/MANUAL.html", "en"),
            ("en/CHANGELOG.md", "en/CHANGELOG.html", "en"),
        })


class EnlacesTest(unittest.TestCase):

    def test_pasa_los_relativos_md_a_html_y_deja_los_absolutos(self):
        html = ('<a href="CHANGELOG.md">Novedades</a>'
                '<a href="../CONFIGURACION_API.md">Guía</a>'
                '<a href="https://ejemplo.es/guia.md">Fuera</a>')
        reescrito = generar_docs._reescribir_enlaces(html)
        self.assertIn('href="CHANGELOG.html"', reescrito)
        self.assertIn('href="../CONFIGURACION_API.html"', reescrito)
        self.assertIn('href="https://ejemplo.es/guia.md"', reescrito)


class ConvertirTest(unittest.TestCase):

    def test_no_llama_pandoc_si_el_markdown_no_existe(self):
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            with patch.object(generar_docs.subprocess, "run") as ejecutar:
                convertido = generar_docs._convertir(
                    raiz / "ausente.md", raiz / "salida.html", "Título",
                    raiz / "estilo.html")

        self.assertTrue(convertido)
        ejecutar.assert_not_called()

    def test_reescribe_enlaces_del_html_generado(self):
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            markdown = raiz / "origen.md"
            salida = raiz / "salida.html"
            header = raiz / "estilo.html"
            markdown.write_text("# Documento", encoding="utf-8")
            header.write_text("<style></style>", encoding="utf-8")

            def simular_pandoc(*_args, **_kwargs):
                salida.write_text('<a href="CHANGELOG.md">Novedades</a>',
                                  encoding="utf-8")

            with patch.object(generar_docs.subprocess, "run",
                              side_effect=simular_pandoc) as ejecutar:
                convertido = generar_docs._convertir(
                    markdown, salida, "Título", header, "es")

            self.assertTrue(convertido)
            ejecutar.assert_called_once()
            self.assertIn('href="CHANGELOG.html"',
                          salida.read_text(encoding="utf-8"))

    def test_devuelve_falso_si_pandoc_falla(self):
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            markdown = raiz / "origen.md"
            markdown.write_text("# Documento", encoding="utf-8")
            error = subprocess.CalledProcessError(
                1, ["pandoc"], stderr="falló pandoc")

            with patch.object(generar_docs.subprocess, "run", side_effect=error):
                convertido = generar_docs._convertir(
                    markdown, raiz / "salida.html", "Título", raiz / "estilo.html")

        self.assertFalse(convertido)


class ManualDelPaqueteTest(unittest.TestCase):

    def test_enlaza_el_manual_de_cada_idioma_que_lo_tiene(self):
        with tempfile.TemporaryDirectory() as temporal:
            docs = Path(temporal)
            for idioma in ("es", "en", "pt"):
                (docs / idioma).mkdir()
            (docs / "es" / "MANUAL.md").write_text("# Manual", encoding="utf-8")
            (docs / "en" / "MANUAL.md").write_text("# Manual", encoding="utf-8")
            (docs / "pt" / "CHANGELOG.md").write_text("# Cambios", encoding="utf-8")
            with patch.object(generar_docs, "DOCS", docs):
                self.assertTrue(generar_docs._escribir_manual_paquete())

            pagina = (docs / "manual-paquete.html").read_text(encoding="utf-8")

        self.assertIn('href="docs/es/MANUAL.html"', pagina)
        self.assertIn("Manual de uso", pagina)
        self.assertIn('href="docs/en/MANUAL.html"', pagina)
        self.assertIn("User manual", pagina)
        self.assertNotIn("docs/pt/MANUAL.html", pagina)
        self.assertIn("Los enlaces valen desde la raíz del paquete", pagina)
