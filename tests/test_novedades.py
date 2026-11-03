"""Pruebas de las novedades de todas las versiones al actualizar.

Sin red real: la lista de publicaciones se arma a mano y el `urlopen`
se reemplaza por un doble.
"""

import io
import json
import unittest
from unittest import mock
from urllib.error import URLError

from bellbird.core import actualizacion, canal_app, novedades
from bellbird.core.config import APP_VERSION


def _publicacion(tag, body="", draft=False, prerelease=False):
    return {"tag_name": tag, "body": body, "draft": draft,
            "prerelease": prerelease}


def _versiones(texto):
    return [linea[len("## Versión "):]
            for linea in texto.split("\n") if linea.startswith("## Versión ")]


class TestJuntarNovedades(unittest.TestCase):

    def test_ordena_de_mayor_a_menor_aunque_venga_desordenada(self):
        publicaciones = [
            _publicacion("v2.9.0", "nueve"),
            _publicacion("v3.1.0", "uno"),
            _publicacion("v3.0.0", "cero"),
        ]
        texto = novedades.juntar_novedades(publicaciones, "2.5.1", "3.1.0")
        self.assertEqual(["3.1.0", "3.0.0", "2.9.0"], _versiones(texto))
        self.assertIn("uno", texto)
        self.assertIn("cero", texto)
        self.assertIn("nueve", texto)

    def test_versiones_estrictamente_decrecientes(self):
        publicaciones = [
            _publicacion("v3.0.0"),
            _publicacion("v2.10.0"),
            _publicacion("v2.9.9"),
            _publicacion("v3.1.0"),
        ]
        texto = novedades.juntar_novedades(publicaciones, "2.5.1", "3.1.0")
        tuplas = [actualizacion.version_como_tupla(v)
                  for v in _versiones(texto)]
        self.assertEqual(sorted(tuplas, reverse=True), tuplas)

    def test_excluye_borradores_prerelease_instalada_anteriores_y_posteriores(self):
        publicaciones = [
            _publicacion("v2.5.1", "instalada"),
            _publicacion("v2.4.0", "anterior"),
            _publicacion("v3.2.0", "posterior"),
            _publicacion("v3.0.0", "borrador", draft=True),
            _publicacion("v2.9.0", "previa", prerelease=True),
            _publicacion("v3.1.0", "incluida"),
        ]
        texto = novedades.juntar_novedades(publicaciones, "2.5.1", "3.1.0")
        self.assertEqual(["3.1.0"], _versiones(texto))
        self.assertIn("incluida", texto)
        for fuera in ("instalada", "anterior", "posterior", "borrador", "previa"):
            self.assertNotIn(fuera, texto)

    def test_tag_con_y_sin_v(self):
        publicaciones = [
            _publicacion("v3.1.0", "con v"),
            _publicacion("3.0.0", "sin v"),
        ]
        texto = novedades.juntar_novedades(publicaciones, "2.0.0", "3.1.0")
        self.assertEqual(["3.1.0", "3.0.0"], _versiones(texto))
        self.assertIn("con v", texto)
        self.assertIn("sin v", texto)

    def test_body_vacio_aporta_solo_el_encabezado(self):
        texto = novedades.juntar_novedades(
            [_publicacion("v3.0.0", "")], "2.0.0", "3.0.0")
        self.assertEqual("## Versión 3.0.0", texto)

    def test_con_betas_las_incluye_y_las_ordena(self):
        publicaciones = [
            _publicacion("v3.0.0", "estable"),
            _publicacion("v3.0.0-beta.10", "diez"),
            _publicacion("v3.0.0-beta.2", "dos"),
            _publicacion("v3.0.0-beta.1", "uno"),
            _publicacion("v3.0.0-beta.3", "borrador", draft=True),
        ]
        texto = novedades.juntar_novedades(
            publicaciones, "2.5.1", "3.0.0", incluir_betas=True)
        self.assertEqual(["3.0.0", "3.0.0-beta.10", "3.0.0-beta.2",
                          "3.0.0-beta.1"], _versiones(texto))
        self.assertIn("diez", texto)
        self.assertNotIn("borrador", texto)

    def test_sin_betas_por_defecto_las_deja_fuera(self):
        publicaciones = [
            _publicacion("v3.0.0", "estable"),
            _publicacion("v3.0.0-beta.10", "previa", prerelease=True),
        ]
        texto = novedades.juntar_novedades(publicaciones, "2.5.1", "3.0.0")
        self.assertEqual(["3.0.0"], _versiones(texto))
        self.assertNotIn("previa", texto)

    def test_entrada_que_no_es_lista_devuelve_vacio(self):
        self.assertEqual("", novedades.juntar_novedades(None, "2.0.0", "3.0.0"))
        self.assertEqual("", novedades.juntar_novedades(
            {"tag_name": "v3.0.0"}, "2.0.0", "3.0.0"))

    def test_sin_ninguna_que_cumpla_devuelve_vacio(self):
        self.assertEqual("", novedades.juntar_novedades(
            [_publicacion("v3.0.0")], "3.0.0", "3.0.0"))


class TestConsultarConNovedades(unittest.TestCase):

    def _paquete(self, version="v3.1.0"):
        return actualizacion.PaqueteElegido(
            version=version, notas="notas de la última",
            url_zip="https://ejemplo.com/App.zip",
            url_firma="https://ejemplo.com/App.zip.sha256",
            tamanio=10)

    def _respuesta(self, contenido):
        return io.BytesIO(json.dumps(contenido).encode("utf-8"))

    def test_lista_valida_reemplaza_las_notas(self):
        publicaciones = [
            _publicacion("v3.0.0", "cero"),
            _publicacion("v3.1.0", "uno"),
        ]
        with mock.patch.object(
                actualizacion, "consultar_ultima_version",
                return_value=self._paquete()), \
                mock.patch.object(
                    novedades, "urlopen",
                    return_value=self._respuesta(publicaciones)):
            paquete = novedades.consultar_con_novedades()
        self.assertIsNotNone(paquete)
        self.assertEqual(["3.1.0", "3.0.0"], _versiones(paquete.notas))
        self.assertNotEqual("notas de la última", paquete.notas)

    def test_lista_que_falla_deja_las_notas_de_la_ultima(self):
        with mock.patch.object(
                actualizacion, "consultar_ultima_version",
                return_value=self._paquete()), \
                mock.patch.object(
                    novedades, "urlopen", side_effect=URLError("sin red")):
            paquete = novedades.consultar_con_novedades()
        self.assertIsNotNone(paquete)
        self.assertEqual("notas de la última", paquete.notas)

    def test_lista_que_no_sirve_deja_las_notas_de_la_ultima(self):
        with mock.patch.object(
                actualizacion, "consultar_ultima_version",
                return_value=self._paquete()), \
                mock.patch.object(
                    novedades, "urlopen",
                    return_value=self._respuesta({"no": "es lista"})):
            paquete = novedades.consultar_con_novedades()
        self.assertEqual("notas de la última", paquete.notas)

    def test_ultima_version_none_da_none(self):
        with mock.patch.object(
                actualizacion, "consultar_ultima_version",
                return_value=None), \
                mock.patch.object(novedades, "urlopen") as pedir:
            self.assertIsNone(novedades.consultar_con_novedades())
        pedir.assert_not_called()

    def test_con_la_misma_version_no_pide_la_lista(self):
        release = {
            "tag_name": APP_VERSION,
            "body": "notas de la última",
            "assets": [
                {"name": "App.zip", "size": 10,
                 "browser_download_url": "https://ejemplo.com/App.zip"},
                {"name": "App.zip.sha256", "size": 5,
                 "browser_download_url": "https://ejemplo.com/App.zip.sha256"},
            ],
        }
        respuestas = [self._respuesta(release)]
        llamadas = []

        def pedir(*args, **kwargs):
            llamadas.append(args)
            if len(llamadas) > 1:
                raise AssertionError("no debe pedir la lista")
            return respuestas[0]

        with mock.patch.object(actualizacion, "urlopen", side_effect=pedir), \
                mock.patch.object(novedades, "urlopen", side_effect=pedir):
            paquete = novedades.consultar_con_novedades()
        self.assertEqual(1, len(llamadas))
        self.assertEqual("notas de la última", paquete.notas)

    def test_usa_la_version_instalada(self):
        publicaciones = [_publicacion("v3.0.0", "cero")]
        with mock.patch.object(
                actualizacion, "consultar_ultima_version",
                return_value=self._paquete()), \
                mock.patch.object(novedades, "APP_VERSION", "2.5.1"), \
                mock.patch.object(
                    novedades, "urlopen",
                    return_value=self._respuesta(publicaciones)):
            paquete = novedades.consultar_con_novedades()
        self.assertEqual(["3.0.0"], _versiones(paquete.notas))

    def test_canal_beta_ofrece_la_beta_y_sus_novedades(self):
        publicaciones = [
            _publicacion("v3.0.0-beta.1", "uno"),
            _publicacion("v3.0.0-beta.2", "dos"),
            _publicacion("v2.5.1", "instalada"),
        ]
        paquete_beta = self._paquete("v3.0.0-beta.2")
        with mock.patch.object(novedades, "APP_VERSION", "2.5.1"), \
                mock.patch.object(
                    canal_app, "canal_guardado", return_value="beta"), \
                mock.patch.object(
                    canal_app, "consultar_ultima_beta",
                    return_value=paquete_beta), \
                mock.patch.object(
                    actualizacion, "consultar_ultima_version") as estable, \
                mock.patch.object(
                    novedades, "urlopen",
                    return_value=self._respuesta(publicaciones)):
            paquete = novedades.consultar_con_novedades()
        estable.assert_not_called()
        self.assertEqual("v3.0.0-beta.2", paquete.version)
        self.assertEqual(["3.0.0-beta.2", "3.0.0-beta.1"],
                         _versiones(paquete.notas))

    def test_canal_beta_incluye_la_beta_intermedia_y_estable_no(self):
        publicaciones = [
            _publicacion("v3.0.0-beta.1", "beta intermedia", prerelease=True),
            _publicacion("v3.0.0-beta.2", "beta nueva", prerelease=True),
            _publicacion("v3.0.0", "estable"),
        ]
        with mock.patch.object(novedades, "APP_VERSION", "2.5.1"), \
                mock.patch.object(
                    canal_app, "canal_guardado", return_value="beta"), \
                mock.patch.object(
                    canal_app, "consultar_ultima_beta",
                    return_value=self._paquete("v3.0.0-beta.2")), \
                mock.patch.object(
                    novedades, "urlopen",
                    return_value=self._respuesta(publicaciones)):
            notas_beta = novedades.consultar_con_novedades().notas
        with mock.patch.object(
                canal_app, "canal_guardado", return_value="estable"), \
                mock.patch.object(
                    actualizacion, "consultar_ultima_version",
                    return_value=self._paquete("v3.0.0")), \
                mock.patch.object(
                    novedades, "urlopen",
                    return_value=self._respuesta(publicaciones)):
            notas_estable = novedades.consultar_con_novedades().notas
        self.assertIn("beta intermedia", notas_beta)
        self.assertNotIn("beta intermedia", notas_estable)

    def test_canal_estable_no_consulta_betas(self):
        publicaciones = [
            _publicacion("v3.0.0", "estable"),
            _publicacion("v3.1.0-beta.1", "previa", prerelease=True),
        ]
        with mock.patch.object(
                canal_app, "canal_guardado", return_value="estable"), \
                mock.patch.object(
                    canal_app, "consultar_ultima_beta") as beta, \
                mock.patch.object(
                    actualizacion, "consultar_ultima_version",
                    return_value=self._paquete("v3.0.0")), \
                mock.patch.object(
                    novedades, "urlopen",
                    return_value=self._respuesta(publicaciones)):
            paquete = novedades.consultar_con_novedades()
        beta.assert_not_called()
        self.assertEqual("v3.0.0", paquete.version)
        self.assertEqual(["3.0.0"], _versiones(paquete.notas))

    def test_canal_raro_usa_la_consulta_estable(self):
        with mock.patch.object(
                canal_app, "canal_guardado", return_value="raro"), \
                mock.patch.object(
                    canal_app, "consultar_ultima_beta") as beta, \
                mock.patch.object(
                    actualizacion, "consultar_ultima_version",
                    return_value=self._paquete("v3.0.0")), \
                mock.patch.object(
                    novedades, "urlopen", side_effect=URLError("sin red")):
            paquete = novedades.consultar_con_novedades()
        beta.assert_not_called()
        self.assertEqual("v3.0.0", paquete.version)


if __name__ == "__main__":
    unittest.main()
