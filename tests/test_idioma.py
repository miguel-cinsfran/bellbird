"""Pruebas del punto único de traducción y de las herramientas de catálogos."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from babel.messages import pofile

from scripts import traducciones
from tests.rutas_temporales import redirigir_rutas
from ytchat.core import idioma


class TestElegirCodigo(unittest.TestCase):
    """La función pura que decide el idioma, sin leer entorno ni Windows."""

    CODIGOS = {"es", "en", "fr"}

    def test_variable_de_entorno_gana_sobre_config_y_windows(self):
        self.assertEqual(
            idioma.elegir_codigo("en", "fr", "fr_FR", self.CODIGOS), "en")

    def test_config_gana_sobre_windows(self):
        self.assertEqual(
            idioma.elegir_codigo("", "fr", "es_MX", self.CODIGOS), "fr")

    def test_windows_y_ausencia_usan_el_idioma_de_windows(self):
        self.assertEqual(
            idioma.elegir_codigo("", "windows", "fr_FR", self.CODIGOS), "fr")
        self.assertEqual(
            idioma.elegir_codigo("windows", "en", "fr_FR", self.CODIGOS), "fr")
        self.assertEqual(
            idioma.elegir_codigo("", "", "fr_FR", self.CODIGOS), "fr")

    def test_regional_sin_catalogo_cae_a_la_base(self):
        self.assertEqual(
            idioma.elegir_codigo("es_PY", "", "", self.CODIGOS), "es")

    def test_idioma_sin_catalogo_cae_al_espanol(self):
        self.assertEqual(
            idioma.elegir_codigo("de", "", "", self.CODIGOS), "es")

    def test_propiedad_el_resultado_siempre_es_utilizable(self):
        valores = ["", "es", "es_PY", "en", "fr", "de", "windows", None]
        for entorno in valores:
            for config in valores:
                for windows in valores:
                    with self.subTest(entorno=entorno, config=config,
                                      windows=windows):
                        resultado = idioma.elegir_codigo(
                            entorno, config, windows, self.CODIGOS)
                        self.assertIn(resultado, self.CODIGOS | {"es"})


class TestPseudo(unittest.TestCase):

    def tearDown(self):
        idioma._reiniciar()

    def test_marca_el_texto_sin_tocar_el_ampersand_ni_el_hueco(self):
        with tempfile.TemporaryDirectory() as tmp:
            idioma.instalar("pseudo", tmp)
            self.assertEqual(
                idioma._("Guardar &nombre en {nombre}"),
                "[¡Guardar &nombre en {nombre}!]")

    def test_n_devuelve_el_texto_tal_cual(self):
        self.assertEqual(idioma.N_("Texto con & y {hueco}"),
                         "Texto con & y {hueco}")


class TestResolucion(unittest.TestCase):

    def tearDown(self):
        idioma._reiniciar()

    def test_dos_llamadas_leen_la_config_una_sola_vez(self):
        idioma._reiniciar()
        leer = mock.Mock(return_value="es")
        with mock.patch.dict(os.environ, {"BELLBIRD_IDIOMA": ""}), \
             mock.patch.object(idioma, "_idioma_config", leer), \
             mock.patch.object(idioma, "idioma_windows", return_value="fr_FR"):
            self.assertEqual(idioma._("uno"), "uno")
            self.assertEqual(idioma._("dos"), "dos")
        self.assertEqual(leer.call_count, 1)

    def test_resolucion_usa_la_variable_de_entorno(self):
        idioma._reiniciar()
        with mock.patch.dict(os.environ, {"BELLBIRD_IDIOMA": "en"}), \
             mock.patch.object(idioma, "_idioma_config", return_value="fr"), \
             mock.patch.object(idioma, "idioma_windows", return_value="fr_FR"), \
             mock.patch.object(idioma, "codigos_con_catalogo",
                               return_value={"en", "fr", "es"}):
            self.assertEqual(idioma.idioma_actual(), "en")


class TestConfig(unittest.TestCase):

    def test_config_ilegible_no_levanta_excepcion(self):
        with tempfile.TemporaryDirectory() as tmp:
            with redirigir_rutas(tmp):
                (Path(tmp) / "config.ini").write_bytes(b"\xff\xfe[ui]\n")
                with self.assertLogs(idioma.logger, level="DEBUG"):
                    self.assertEqual(idioma._idioma_config(), "windows")

    def test_config_sin_ui_no_levanta_excepcion(self):
        with tempfile.TemporaryDirectory() as tmp:
            with redirigir_rutas(tmp):
                (Path(tmp) / "config.ini").write_text(
                    "[voz]\nvelocidad = 200\n", encoding="utf-8")
                with self.assertLogs(idioma.logger, level="DEBUG"):
                    self.assertEqual(idioma._idioma_config(), "windows")

    def test_config_inexistente_cuenta_como_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            with redirigir_rutas(tmp):
                with self.assertLogs(idioma.logger, level="DEBUG"):
                    self.assertEqual(idioma._idioma_config(), "windows")


class TestIdiomaWindows(unittest.TestCase):

    @unittest.skipUnless(os.name == "nt", "kernel32 solo existe en Windows")
    def test_llamada_real_devuelve_codigo_con_forma(self):
        self.assertRegex(idioma.idioma_windows(), r"^[a-z]{2}(_[A-Z]{2})?$")


class TestPuntaAPunta(unittest.TestCase):
    """Un texto de un .py hasta su traducción leída del .mo."""

    def tearDown(self):
        idioma._reiniciar()

    def test_texto_desde_py_hasta_mo(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp) / "proyecto"
            idiomas = Path(tmp) / "idiomas"
            (raiz / "ytchat").mkdir(parents=True)
            (raiz / "main.py").write_text(
                "# Traductores: acción de guardar\n"
                '_("Guardado")\n'
                'N_("Solo para extraer")\n'
                'ngettext("{n} canción", "{n} canciones", n)\n'
                'pgettext("verbo", "Abrir")\n',
                encoding="utf-8")
            (raiz / "ytchat" / "__init__.py").write_text("", encoding="utf-8")

            traducciones.extraer(carpeta_raiz=raiz, carpeta_idiomas=idiomas)
            plantilla = traducciones.ruta_plantilla(idiomas)
            self.assertIn("Solo para extraer",
                          plantilla.read_text(encoding="utf-8"))
            traducciones.actualizar("en", carpeta_raiz=raiz,
                                    carpeta_idiomas=idiomas)

            po = traducciones.ruta_po(idiomas, "en")
            with po.open("rb") as archivo:
                catalogo = pofile.read_po(archivo)
            self._traducir(catalogo, "Guardado", "Saved")
            self._traducir(catalogo, "Abrir", "Open", contexto="verbo")
            plural = catalogo.get(("{n} canción", "{n} canciones"))
            plural.string = ["{n} song", "{n} songs"]
            plural.flags.discard("fuzzy")
            with po.open("wb") as archivo:
                pofile.write_po(archivo, catalogo)

            traducciones.actualizar("en", carpeta_raiz=raiz,
                                    carpeta_idiomas=idiomas)
            with po.open("rb") as archivo:
                actualizado = pofile.read_po(archivo)
            self.assertEqual(actualizado.get("Guardado").string, "Saved")
            self.assertEqual(
                actualizado.get(("{n} canción", "{n} canciones")).string[0],
                "{n} song")
            self.assertEqual(
                actualizado.get("Abrir", context="verbo").string, "Open")

            traducciones.compilar(carpeta_idiomas=idiomas)
            idioma.instalar("en", idiomas)

            self.assertEqual(idioma._("Guardado"), "Saved")
            self.assertEqual(
                idioma.ngettext("{n} canción", "{n} canciones", 1),
                "{n} song")
            self.assertEqual(
                idioma.ngettext("{n} canción", "{n} canciones", 2),
                "{n} songs")
            self.assertEqual(idioma.pgettext("verbo", "Abrir"), "Open")
            self.assertIn("Traductores: acción de guardar",
                          po.read_text(encoding="utf-8"))

    @staticmethod
    def _traducir(catalogo, texto, traduccion, contexto=None):
        mensaje = catalogo.get(texto, context=contexto)
        mensaje.string = traduccion
        mensaje.flags.discard("fuzzy")


class TestIdiomasDisponibles(unittest.TestCase):
    """Pares (valor, nombre) para la lista de idioma de Preferencias."""

    def tearDown(self):
        idioma._reiniciar()

    def _mo(self, raiz, codigo):
        destino = Path(raiz) / codigo / "LC_MESSAGES" / f"{idioma.DOMINIO}.mo"
        destino.parent.mkdir(parents=True)
        destino.write_bytes(b"")

    def test_sin_catalogos_solo_windows_y_espanol(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(idioma, "_", lambda texto: texto):
                self.assertEqual(
                    idioma.idiomas_disponibles(tmp),
                    [("windows", "Idioma de Windows"), ("es", "Español")])

    def test_con_en_suma_english_al_final(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._mo(tmp, "en")
            with mock.patch.object(idioma, "_", lambda texto: texto):
                self.assertEqual(
                    idioma.idiomas_disponibles(tmp),
                    [("windows", "Idioma de Windows"), ("es", "Español"),
                     ("en", "English")])

    def test_codigo_sin_nombre_se_muestra_tal_cual_y_ordena_por_nombre(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._mo(tmp, "fr")
            self._mo(tmp, "en")
            with mock.patch.object(idioma, "_", lambda texto: texto):
                self.assertEqual(
                    idioma.idiomas_disponibles(tmp),
                    [("windows", "Idioma de Windows"), ("es", "Español"),
                     ("en", "English"), ("fr", "fr")])

    def test_el_seudo_y_el_espanol_no_se_repiten(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._mo(tmp, "es")
            self._mo(tmp, "pseudo")
            self._mo(tmp, "en")
            with mock.patch.object(idioma, "_", lambda texto: texto):
                self.assertEqual(
                    idioma.idiomas_disponibles(tmp),
                    [("windows", "Idioma de Windows"), ("es", "Español"),
                     ("en", "English")])


if __name__ == "__main__":
    unittest.main()
