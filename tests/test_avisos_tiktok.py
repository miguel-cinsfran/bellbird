"""Modos por aviso de TikTok: lo que se lee, se muestra o se oculta.

Cubre `ytchat/core/avisos_tiktok.py` sin ventanas: los modos guardados, los
de fábrica y los extraños, el filtro del chat y la migración de las dos
casillas viejas a las cinco claves nuevas.
"""

import configparser
import unittest

from ytchat.core import avisos_tiktok
from ytchat.core import config as cfg


def _config(**extras):
    base = {"tiktok_aviso_entradas": "leer"}
    base.update(extras)
    return base


class TestModoDe(unittest.TestCase):
    def test_modo_guardado(self):
        self.assertEqual(
            avisos_tiktok.modo_de(
                _config(tiktok_aviso_me_gusta="ocultar"), cfg.TIPO_ME_GUSTA),
            "ocultar")

    def test_ausente_da_el_de_fabrica(self):
        self.assertEqual(
            avisos_tiktok.modo_de({}, cfg.TIPO_ENTRADA), "mostrar")
        self.assertEqual(
            avisos_tiktok.modo_de({}, cfg.TIPO_SEGUIR), "leer")

    def test_extrano_da_el_de_fabrica(self):
        self.assertEqual(
            avisos_tiktok.modo_de(
                _config(tiktok_aviso_entradas="fuerte"), cfg.TIPO_ENTRADA),
            "mostrar")

    def test_tipo_que_no_es_aviso_da_none(self):
        self.assertIsNone(
            avisos_tiktok.modo_de(_config(), cfg.TIPO_TEXTO))

    def test_tipos_coinciden_con_config(self):
        tipos = [aviso[0] for aviso in avisos_tiktok.AVISOS]
        self.assertEqual(
            tipos, [cfg.TIPO_ENTRADA, cfg.TIPO_ME_GUSTA, cfg.TIPO_SEGUIR,
                    cfg.TIPO_COMPARTIR, cfg.TIPO_COFRE])
        self.assertEqual(avisos_tiktok.TIPOS_AVISO, frozenset(tipos))


class TestPasaFiltro(unittest.TestCase):
    def test_none_deja_pasar_todo(self):
        self.assertTrue(avisos_tiktok.pasa_filtro(None, cfg.TIPO_TEXTO))
        self.assertTrue(avisos_tiktok.pasa_filtro(None, cfg.TIPO_ENTRADA))

    def test_conjunto_deja_pasar_sus_tipos(self):
        self.assertTrue(avisos_tiktok.pasa_filtro(
            avisos_tiktok.TIPOS_AVISO, cfg.TIPO_COFRE))
        self.assertFalse(avisos_tiktok.pasa_filtro(
            avisos_tiktok.TIPOS_AVISO, cfg.TIPO_TEXTO))
        self.assertFalse(avisos_tiktok.pasa_filtro(frozenset(), cfg.TIPO_SEGUIR))

    def test_texto_compara_igual(self):
        self.assertTrue(avisos_tiktok.pasa_filtro(
            cfg.TIPO_TEXTO, cfg.TIPO_TEXTO))
        self.assertFalse(avisos_tiktok.pasa_filtro(
            cfg.TIPO_TEXTO, cfg.TIPO_SUPERCHAT))


class TestMigrar(unittest.TestCase):
    def _parser(self, texto):
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(texto)
        return parser

    def test_viejo_verdadero_migra_a_leer(self):
        parser = self._parser("[tiktok]\nanunciar_entradas = true\n")
        escritas = []
        avisos_tiktok.migrar(
            parser, "ruta", lambda r, s, c, v: escritas.append((r, s, c, v)))
        self.assertIn(("ruta", "tiktok", "aviso_entradas", "leer"), escritas)
        self.assertEqual(parser.get("tiktok", "aviso_entradas"), "leer")

    def test_viejo_falso_migra_a_mostrar(self):
        parser = self._parser("[tiktok]\nanunciar_entradas = false\n")
        escritas = []
        avisos_tiktok.migrar(
            parser, "ruta", lambda r, s, c, v: escritas.append((r, s, c, v)))
        self.assertIn(("ruta", "tiktok", "aviso_entradas", "mostrar"), escritas)
        self.assertEqual(parser.get("tiktok", "aviso_entradas"), "mostrar")

    def test_viejo_ausente_migra_a_mostrar(self):
        parser = self._parser("[tiktok]\nusuario = pepe\n")
        escritas = []
        avisos_tiktok.migrar(
            parser, "ruta", lambda r, s, c, v: escritas.append((r, s, c, v)))
        self.assertIn(("ruta", "tiktok", "aviso_entradas", "mostrar"), escritas)
        self.assertIn(("ruta", "tiktok", "aviso_me_gusta", "mostrar"), escritas)
        self.assertEqual(parser.get("tiktok", "aviso_entradas"), "mostrar")
        self.assertEqual(
            parser.get("tiktok", "anunciar_entradas", fallback="ausente"),
            "ausente")

    def test_me_gusta_migra_desde_leer_me_gusta(self):
        parser = self._parser("[tiktok]\nleer_me_gusta = true\n")
        escritas = []
        avisos_tiktok.migrar(
            parser, "ruta", lambda r, s, c, v: escritas.append((r, s, c, v)))
        self.assertIn(("ruta", "tiktok", "aviso_me_gusta", "leer"), escritas)
        self.assertEqual(parser.get("tiktok", "aviso_me_gusta"), "leer")

    def test_clave_nueva_presente_no_se_toca(self):
        parser = self._parser("[tiktok]\nanunciar_entradas = true\n"
                              "aviso_entradas = ocultar\n")
        escritas = []
        avisos_tiktok.migrar(
            parser, "ruta", lambda r, s, c, v: escritas.append((r, s, c, v)))
        self.assertNotIn(("ruta", "tiktok", "aviso_entradas", "leer"), escritas)
        self.assertEqual(parser.get("tiktok", "aviso_entradas"), "ocultar")

    def test_sin_seccion_tiktok_la_crea_en_el_parser(self):
        parser = self._parser("[ui]\nfiltro_activo = todos\n")
        escritas = []
        avisos_tiktok.migrar(
            parser, "ruta", lambda r, s, c, v: escritas.append((r, s, c, v)))
        self.assertEqual(parser.get("tiktok", "aviso_entradas"), "mostrar")


if __name__ == "__main__":
    unittest.main()
