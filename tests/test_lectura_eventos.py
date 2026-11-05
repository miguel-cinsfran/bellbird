"""Texto de la voz por evento del directo y tipos de mensaje."""

import unittest

from bellbird.core import config
from bellbird.core import tipos_mensaje
from bellbird.core.config import TIPO_TEXTO as TIPO_TEXTO_DESDE_CONFIG
from bellbird.core.lectura_eventos import texto_evento
from bellbird.core.tipos_mensaje import (
    TIPO_TEXTO, TIPO_SUPERCHAT, TIPO_MIEMBRO, TIPO_ENTRADA,
    TIPO_SEGUIR, TIPO_COMPARTIR, TIPO_COFRE, TIPO_ME_GUSTA,
    TIPO_ENCUESTA, TIPO_ENCUESTA_FIN, TIPO_META, TIPO_BATALLA,
    TIPO_BATALLA_FIN,
)


class TiposDeMensajeTests(unittest.TestCase):
    def test_los_nueve_tipos_siguen_valiendo_en_config(self):
        nombres = ("TIPO_TEXTO", "TIPO_SUPERCHAT", "TIPO_STICKER",
                   "TIPO_MIEMBRO", "TIPO_ENTRADA", "TIPO_SEGUIR",
                   "TIPO_COMPARTIR", "TIPO_COFRE", "TIPO_ME_GUSTA")
        for nombre in nombres:
            with self.subTest(nombre=nombre):
                self.assertIs(getattr(config, nombre),
                              getattr(tipos_mensaje, nombre))
        self.assertEqual(TIPO_TEXTO_DESDE_CONFIG, TIPO_TEXTO)


class TextoDeEventoTests(unittest.TestCase):
    def test_miembro(self):
        self.assertEqual(texto_evento(TIPO_MIEMBRO, "Ana", ""),
                         "Nuevo miembro: Ana")

    def test_entrada_sin_monto(self):
        self.assertEqual(texto_evento(TIPO_ENTRADA, "Ana", ""),
                         "Ana entró")

    def test_entrada_agrupada_dice_entraron(self):
        self.assertEqual(texto_evento(TIPO_ENTRADA, "Ana", "3"),
                         "Ana entraron")

    def test_seguir(self):
        self.assertEqual(texto_evento(TIPO_SEGUIR, "Ana", ""),
                         "Ana sigue el canal")

    def test_compartir(self):
        self.assertEqual(texto_evento(TIPO_COMPARTIR, "Ana", ""),
                         "Ana compartió el directo")

    def test_cofre(self):
        self.assertEqual(texto_evento(TIPO_COFRE, "Ana", ""),
                         "Ana envió un cofre")

    def test_me_gusta_con_monto(self):
        self.assertEqual(texto_evento(TIPO_ME_GUSTA, "Ana", "3"),
                         "Ana dio 3 me gusta")

    def test_me_gusta_sin_monto(self):
        self.assertEqual(texto_evento(TIPO_ME_GUSTA, "Ana", ""),
                         "Ana dio me gusta")

    def test_texto_y_superchat_no_son_eventos(self):
        self.assertIsNone(texto_evento(TIPO_TEXTO, "Ana", ""))
        self.assertIsNone(texto_evento(TIPO_SUPERCHAT, "Ana", "$5"))

    def test_las_encuestas_dicen_el_mensaje_tal_cual(self):
        frase = "Encuesta: ¿Qué almorzamos? Opciones: pizza y sushi"
        for tipo in (TIPO_ENCUESTA, TIPO_ENCUESTA_FIN):
            with self.subTest(tipo=tipo):
                self.assertEqual(
                    texto_evento(tipo, "", "", frase), frase)
                self.assertEqual(texto_evento(tipo, "", ""), "")

    def test_las_metas_y_batallas_dicen_el_mensaje_tal_cual(self):
        frase = "Batalla: Ana contra Fulano"
        for tipo in (TIPO_META, TIPO_BATALLA, TIPO_BATALLA_FIN):
            with self.subTest(tipo=tipo):
                self.assertEqual(
                    texto_evento(tipo, "", "", frase), frase)
                self.assertEqual(texto_evento(tipo, "", ""), "")


if __name__ == "__main__":
    unittest.main()
