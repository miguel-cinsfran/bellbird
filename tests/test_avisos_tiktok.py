"""Modos por aviso de TikTok: lo que se lee, se muestra o se oculta.

Cubre `bellbird/core/avisos_tiktok.py` sin ventanas: los modos guardados, los
de fábrica y los extraños, el filtro del chat y la migración de las dos
casillas viejas a las cinco claves nuevas.
"""

import configparser
import unittest

from bellbird.core import avisos_tiktok
from bellbird.core import config as cfg


def _config(**extras):
    base = {"tiktok_aviso_entradas": "leer"}
    base.update(extras)
    return base


class TestModoDe(unittest.TestCase):
    def test_principal_y_secundaria_dan_leer(self):
        for modo in ("principal", "secundaria"):
            with self.subTest(modo=modo):
                self.assertEqual(
                    avisos_tiktok.modo_de(
                        _config(evento_entrada=modo), cfg.TIPO_ENTRADA),
                    "leer")

    def test_mostrar_y_ocultar_se_conservan(self):
        for modo in ("mostrar", "ocultar"):
            with self.subTest(modo=modo):
                self.assertEqual(
                    avisos_tiktok.modo_de(
                        _config(evento_entrada=modo), cfg.TIPO_ENTRADA),
                    modo)

    def test_ausente_da_el_de_fabrica(self):
        self.assertEqual(
            avisos_tiktok.modo_de({}, cfg.TIPO_ENTRADA), "mostrar")
        self.assertEqual(
            avisos_tiktok.modo_de({}, cfg.TIPO_SEGUIR), "leer")

    def test_las_claves_viejas_de_tiktok_no_se_leen(self):
        self.assertEqual(
            avisos_tiktok.modo_de(
                _config(tiktok_aviso_entradas="ocultar"), cfg.TIPO_ENTRADA),
            "mostrar")
        self.assertEqual(
            avisos_tiktok.modo_de(
                _config(tiktok_aviso_entradas="leer",
                        evento_entrada="ocultar"), cfg.TIPO_ENTRADA),
            "ocultar")

    def test_extrano_da_el_de_fabrica(self):
        self.assertEqual(
            avisos_tiktok.modo_de(
                _config(evento_entrada="fuerte"), cfg.TIPO_ENTRADA),
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
        self.assertNotIn(cfg.TIPO_SUPERCHAT, avisos_tiktok.TIPOS_AVISO)
        self.assertNotIn(cfg.TIPO_MIEMBRO, avisos_tiktok.TIPOS_AVISO)


class TestEventos(unittest.TestCase):
    def test_sticker_comparte_el_evento_superchat(self):
        self.assertEqual(avisos_tiktok.evento_de(cfg.TIPO_SUPERCHAT), "superchat")
        self.assertEqual(avisos_tiktok.evento_de(cfg.TIPO_STICKER), "superchat")

    def test_los_siete_eventos_tienen_su_tipo(self):
        esperado = {
            cfg.TIPO_SUPERCHAT: "superchat", cfg.TIPO_STICKER: "superchat",
            cfg.TIPO_MIEMBRO: "miembro", cfg.TIPO_ENTRADA: "entrada",
            cfg.TIPO_ME_GUSTA: "me_gusta", cfg.TIPO_SEGUIR: "seguir",
            cfg.TIPO_COMPARTIR: "compartir", cfg.TIPO_COFRE: "cofre",
        }
        for tipo, evento in esperado.items():
            with self.subTest(tipo=tipo):
                self.assertEqual(avisos_tiktok.evento_de(tipo), evento)
        self.assertIsNone(avisos_tiktok.evento_de(cfg.TIPO_TEXTO))

    def test_modos_y_rotulos(self):
        self.assertEqual([modo for modo, _rotulo in avisos_tiktok.MODOS_EVENTO],
                         ["principal", "secundaria", "mostrar", "ocultar"])
        self.assertEqual([rotulo for _modo, rotulo in avisos_tiktok.MODOS_EVENTO],
                         ["Voz principal", "Voz secundaria", "Solo sonido",
                          "Desactivado"])

    def test_modo_guardado(self):
        config = {"evento_superchat": "mostrar"}
        self.assertEqual(
            avisos_tiktok.modo_evento(config, cfg.TIPO_SUPERCHAT), "mostrar")

    def test_ausente_da_el_de_fabrica(self):
        self.assertEqual(
            avisos_tiktok.modo_evento({}, cfg.TIPO_MIEMBRO), "principal")
        self.assertEqual(
            avisos_tiktok.modo_evento({}, cfg.TIPO_ENTRADA), "mostrar")
        self.assertEqual(
            avisos_tiktok.modo_evento({}, cfg.TIPO_ME_GUSTA), "mostrar")

    def test_extrano_da_el_de_fabrica(self):
        config = {"evento_cofre": "raro"}
        self.assertEqual(
            avisos_tiktok.modo_evento(config, cfg.TIPO_COFRE), "principal")

    def test_texto_no_es_evento(self):
        self.assertIsNone(avisos_tiktok.modo_evento({}, cfg.TIPO_TEXTO))

    def test_opciones_eventos_validan_y_completan(self):
        texto = "[eventos]\nsuperchat = mostrar\nmiembro = raro\n"
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(texto)
        opciones = avisos_tiktok.opciones_eventos(parser)
        self.assertEqual(opciones["evento_superchat"], "mostrar")
        self.assertEqual(opciones["evento_miembro"], "principal")
        self.assertEqual(opciones["evento_entrada"], "mostrar")


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

    def _migrar(self, texto):
        parser = self._parser(texto)
        escritas = []
        avisos_tiktok.migrar(
            parser, "ruta", lambda r, s, c, v: escritas.append((r, s, c, v)))
        return parser, escritas

    def test_casilla_vieja_verdadera_migra_a_principal(self):
        parser, escritas = self._migrar(
            "[tiktok]\nanunciar_entradas = true\n")
        self.assertIn(("ruta", "eventos", "entrada", "principal"), escritas)
        self.assertEqual(parser.get("eventos", "entrada"), "principal")

    def test_casilla_vieja_falsa_migra_a_mostrar(self):
        parser, escritas = self._migrar(
            "[tiktok]\nanunciar_entradas = false\n")
        self.assertIn(("ruta", "eventos", "entrada", "mostrar"), escritas)
        self.assertEqual(parser.get("eventos", "entrada"), "mostrar")

    def test_viejo_ausente_deja_los_valores_de_fabrica(self):
        parser, _escritas = self._migrar("[tiktok]\nusuario = pepe\n")
        self.assertEqual(parser.get("eventos", "entrada"), "mostrar")
        self.assertEqual(parser.get("eventos", "me_gusta"), "mostrar")
        self.assertFalse(parser.has_option("tiktok", "aviso_entradas"))
        self.assertFalse(parser.has_option("tiktok", "aviso_me_gusta"))

    def test_me_gusta_migra_desde_leer_me_gusta(self):
        parser, escritas = self._migrar(
            "[tiktok]\nleer_me_gusta = true\n")
        self.assertIn(("ruta", "eventos", "me_gusta", "principal"), escritas)
        self.assertEqual(parser.get("eventos", "me_gusta"), "principal")

    def test_las_claves_viejas_de_aviso_se_leen(self):
        parser, escritas = self._migrar(
            "[tiktok]\naviso_cofres = ocultar\n"
            "aviso_compartidos = mostrar\n")
        self.assertIn(("ruta", "eventos", "cofre", "ocultar"), escritas)
        self.assertIn(("ruta", "eventos", "compartir", "mostrar"), escritas)
        self.assertEqual(parser.get("eventos", "cofre"), "ocultar")
        self.assertEqual(parser.get("eventos", "compartir"), "mostrar")

    def test_clave_nueva_presente_manda(self):
        parser, _escritas = self._migrar(
            "[tiktok]\nanunciar_entradas = true\n"
            "aviso_entradas = ocultar\n")
        self.assertEqual(parser.get("eventos", "entrada"), "ocultar")

    def test_sin_eventos_crea_la_seccion_sin_tocar_tiktok(self):
        parser, _escritas = self._migrar("[ui]\nfiltro_activo = todos\n")
        self.assertEqual(parser.get("eventos", "entrada"), "mostrar")
        self.assertFalse(parser.has_section("tiktok"))

    def test_eventos_presentes_no_se_migran(self):
        parser, escritas = self._migrar(
            "[eventos]\nsuperchat = mostrar\n"
            "[tiktok]\nanunciar_entradas = true\n")
        self.assertEqual(parser.get("eventos", "superchat"), "mostrar")
        self.assertEqual(escritas, [])

if __name__ == "__main__":
    unittest.main()
