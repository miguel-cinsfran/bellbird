"""Pruebas de la edición textual de sounds.ini (sin wx ni ventanas)."""

import unittest

from ytchat.core import sonidos_ini


TEXTO_BASE = """# Comentario de cabecera
[sonidos]
# Volumen global.
volumen = 0.7
tema = default
# Un evento ya callado.
copiar =
# Un override con ruta propia.
superchat = sounds/mis_efectos/caja.wav
# Comentario final.
"""


class TestSilenciados(unittest.TestCase):
    def test_detecta_el_evento_con_valor_vacio(self):
        self.assertEqual(sonidos_ini.silenciados(TEXTO_BASE), {"copiar"})

    def test_ignora_overrides_comentarios_y_otras_secciones(self):
        texto = TEXTO_BASE + "\n[otra]\ncopiar =\n"
        self.assertEqual(sonidos_ini.silenciados(texto), {"copiar"})

    def test_sin_seccion_no_hay_silenciados(self):
        self.assertEqual(sonidos_ini.silenciados("# nada\n"), set())


class TestConSilenciados(unittest.TestCase):
    def test_silenciar_agrega_la_linea_vacia(self):
        nuevo = sonidos_ini.con_silenciados(
            TEXTO_BASE, {"mensaje_nuevo"}, ["mensaje_nuevo"])
        self.assertIn("mensaje_nuevo", sonidos_ini.silenciados(nuevo))

    def test_volver_a_activar_quita_la_linea_vacia(self):
        callado = sonidos_ini.con_silenciados(
            TEXTO_BASE, {"copiar", "mensaje_nuevo"}, ["copiar", "mensaje_nuevo"])
        self.assertIn("copiar", sonidos_ini.silenciados(callado))
        reactivado = sonidos_ini.con_silenciados(
            callado, set(), ["copiar", "mensaje_nuevo"])
        self.assertNotIn("copiar", sonidos_ini.silenciados(reactivado))
        self.assertNotIn("mensaje_nuevo", sonidos_ini.silenciados(reactivado))

    def test_override_de_otro_evento_queda_intacto(self):
        nuevo = sonidos_ini.con_silenciados(
            TEXTO_BASE, {"copiar"}, ["copiar", "superchat"])
        self.assertIn("sounds/mis_efectos/caja.wav", nuevo)
        self.assertEqual(sonidos_ini.silenciados(nuevo), {"copiar"})

    def test_destildar_un_override_lo_deja_vacio(self):
        nuevo = sonidos_ini.con_silenciados(
            TEXTO_BASE, {"superchat"}, ["superchat"])
        self.assertIn("superchat", sonidos_ini.silenciados(nuevo))
        self.assertNotIn("caja.wav", nuevo)

    def test_conserva_comentarios_orden_y_resto(self):
        nuevo = sonidos_ini.con_silenciados(
            TEXTO_BASE, {"mensaje_nuevo"}, ["mensaje_nuevo"])
        for linea in ("# Comentario de cabecera", "# Volumen global.",
                      "volumen = 0.7", "tema = default",
                      "# Comentario final."):
            self.assertIn(linea, nuevo)

    def test_propiedad_silenciados_tras_con_silenciados(self):
        eventos = ["copiar", "mensaje_nuevo", "superchat"]
        for silenciar in (set(), {"copiar"}, {"mensaje_nuevo", "superchat"},
                          {"copiar", "mensaje_nuevo", "superchat"}):
            with self.subTest(silenciar=sorted(silenciar)):
                nuevo = sonidos_ini.con_silenciados(
                    TEXTO_BASE, silenciar, eventos)
                previos_fuera = (sonidos_ini.silenciados(TEXTO_BASE)
                                 - set(eventos))
                self.assertEqual(sonidos_ini.silenciados(nuevo),
                                 set(silenciar) | previos_fuera)


if __name__ == "__main__":
    unittest.main()
