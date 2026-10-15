"""Pruebas de la descripción hablada de la escena al aire."""

import unittest

from ytchat.obs import obs_escena


def elemento(identificador, nombre, indice, x=0, y=0, ancho=0, alto=0,
              alineacion=0, visible=True, bounds=None):
    transformacion = {"positionX": x, "positionY": y, "width": ancho,
                      "height": alto, "alignment": alineacion}
    if bounds is not None:
        transformacion.update(bounds)
    return {"sceneItemId": identificador, "sourceName": nombre,
            "sceneItemIndex": indice, "sceneItemEnabled": visible,
            "sceneItemTransform": transformacion}


LIENZO = (1600, 900)


class DescribirEscenaTest(unittest.TestCase):
    def test_escena_vacia(self):
        self.assertEqual(
            obs_escena.describir_escena("Juego", [], *LIENZO, {}),
            "Escena al aire: Juego. No tiene fuentes.")

    def test_una_sola_fuente_en_singular(self):
        frase = obs_escena.describir_escena(
            "Juego", [elemento(1, "Fondo", 0, 800, 450, 1600, 900, 0)],
            *LIENZO, {"Fondo": "imagen"})
        self.assertEqual(
            frase,
            "Escena al aire: Juego. 1 fuente, de adelante hacia atrás.\n"
            "1: Fondo, imagen, ocupa toda la imagen, se ve.")

    def test_varias_fuentes_en_plural(self):
        frase = obs_escena.describir_escena(
            "Juego",
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9),
             elemento(2, "Juego", 1, 800, 450, 1600, 900, 0)],
            *LIENZO, {"Panel": "navegador", "Juego": "captura de juego"})
        self.assertIn("2 fuentes, de adelante hacia atrás.", frase.splitlines()[0])

    def test_ordena_de_adelante_hacia_atras_aunque_venga_al_reves(self):
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9),
             elemento(2, "Captura", 5, 800, 450, 1600, 900, 0)],
            *LIENZO, {"Panel": "navegador", "Captura": "captura de pantalla"})
        lineas = frase.splitlines()
        self.assertTrue(lineas[1].startswith("1: Captura,"))
        self.assertTrue(lineas[2].startswith("2: Panel,"))

    def test_caso_manu_panel_tapado_por_captura_completa(self):
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9),
             elemento(2, "Captura", 1, 800, 450, 1600, 900, 0)],
            *LIENZO, {"Panel": "navegador", "Captura": "captura de pantalla"})
        self.assertEqual(
            frase,
            "Escena al aire: Principal. 2 fuentes, de adelante hacia atrás.\n"
            "1: Captura, captura de pantalla, ocupa toda la imagen, se ve.\n"
            "2: Panel, navegador, esquina inferior izquierda, "
            "460 por 620 píxeles, visible en OBS, pero no aparece en "
            "la imagen: la tapa entera Captura.")

    def test_fuente_oculta_no_dice_tapada(self):
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9, visible=False),
             elemento(2, "Captura", 1, 800, 450, 1600, 900, 0)],
            *LIENZO, {"Panel": "navegador", "Captura": "captura de pantalla"})
        self.assertIn("2: Panel, navegador, esquina inferior izquierda, "
                      "460 por 620 píxeles, oculta en OBS.", frase)

    def test_captura_oculta_no_tapa(self):
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9),
             elemento(2, "Captura", 1, 800, 450, 1600, 900, 0, visible=False)],
            *LIENZO, {"Panel": "navegador", "Captura": "captura de pantalla"})
        self.assertIn("2: Panel, navegador, esquina inferior izquierda, "
                      "460 por 620 píxeles, se ve.", frase)

    def test_tapa_leve_no_se_dice(self):
        # El frente cubre 200 por 100 de 460 por 620: 7 %, debajo del aviso.
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9),
             elemento(2, "Aviso", 1, 32, 262, 200, 100, 5)],
            *LIENZO, {"Panel": "navegador", "Aviso": "texto"})
        self.assertIn("2: Panel, navegador, esquina inferior izquierda, "
                      "460 por 620 píxeles, se ve.", frase)

    def test_nombra_a_la_que_mas_tapa(self):
        # A cubre la mitad izquierda (50 %), B una franja de arriba (30 %).
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9),
             elemento(2, "B", 1, 32, 262, 460, 186, 5),
             elemento(3, "A", 2, 32, 262, 230, 620, 5)],
            *LIENZO, {"Panel": "navegador", "A": "imagen", "B": "texto"})
        self.assertIn("se ve en parte: A tapa el 50 por ciento", frase)

    def test_tapada_entera_en_el_borde_95(self):
        # El frente cubre 460 por 589 de 460 por 620: 95 % justo.
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9),
             elemento(2, "Aviso", 1, 32, 262, 460, 589, 5)],
            *LIENZO, {"Panel": "navegador", "Aviso": "texto"})
        self.assertIn("visible en OBS, pero no aparece en la imagen: "
                      "la tapa entera Aviso", frase)

    def test_tapada_en_parte_justo_debajo_del_95(self):
        # El frente cubre 460 por 581 de 460 por 620: 94 % redondeado.
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9),
             elemento(2, "Aviso", 1, 32, 262, 460, 581, 5)],
            *LIENZO, {"Panel": "navegador", "Aviso": "texto"})
        self.assertIn("se ve en parte: Aviso tapa el 94 por ciento", frase)

    def test_tapada_en_parte_en_el_borde_10(self):
        # El frente cubre 460 por 62 de 460 por 620: 10 % justo.
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9),
             elemento(2, "Aviso", 1, 32, 262, 460, 62, 5)],
            *LIENZO, {"Panel": "navegador", "Aviso": "texto"})
        self.assertIn("se ve en parte: Aviso tapa el 10 por ciento", frase)

    def test_parcialmente_fuera_de_la_imagen(self):
        # 200 de 800 píxeles a la derecha del lienzo: 25 % fuera.
        frase = obs_escena.describir_escena(
            "Principal", [elemento(1, "Juego", 0, 1400, 450, 800, 450, 0)],
            *LIENZO, {"Juego": "captura de juego"})
        self.assertEqual(
            frase,
            "Escena al aire: Principal. 1 fuente, de adelante hacia atrás.\n"
            "1: Juego, captura de juego, cerca del borde derecho, centrado, "
            "800 por 450 píxeles, se ve y un 25 por ciento queda "
            "fuera de la imagen.")

    def test_sin_transformacion_no_rompe_el_resto(self):
        frase = obs_escena.describir_escena(
            "Principal",
            [{"sourceName": "Rota", "sceneItemIndex": 0},
             elemento(2, "Captura", 1, 800, 450, 1600, 900, 0)],
            *LIENZO, {"Rota": "imagen", "Captura": "captura de pantalla"})
        self.assertEqual(
            frase,
            "Escena al aire: Principal. 2 fuentes, de adelante hacia atrás.\n"
            "1: Captura, captura de pantalla, ocupa toda la imagen, se ve.\n"
            "2: Rota, imagen, posición desconocida, se ve.")

    def test_sin_tipo_no_deja_hueco(self):
        frase = obs_escena.describir_escena(
            "Principal", [elemento(1, "Rara", 0, 800, 450, 1600, 900, 0)],
            *LIENZO, {})
        self.assertIn("1: Rara, ocupa toda la imagen, se ve.", frase)

    def test_con_bounds_activos_el_tamano_sale_de_ahi(self):
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Foto", 0, 800, 450, 3840, 2160, 0,
                      bounds={"boundsType": "OBS_BOUNDS_SCALE_INNER",
                              "boundsWidth": 1600, "boundsHeight": 900})],
            *LIENZO, {"Foto": "imagen"})
        self.assertIn("1: Foto, imagen, ocupa toda la imagen, se ve.", frase)

    def test_una_oracion_por_linea(self):
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9),
              elemento(2, "Captura", 1, 800, 450, 1600, 900, 0)],
            *LIENZO, {"Panel": "navegador", "Captura": "captura de pantalla"})
        self.assertEqual(len(frase.splitlines()), 3)
        for linea in frase.splitlines():
            self.assertTrue(linea.endswith("."))


class ZonaCercanaTest(unittest.TestCase):
    def test_los_nueve_centros_dan_su_zona(self):
        casos = (
            ((90, 90, 120, 120), "superior-izquierda"),
            ((390, 90, 120, 120), "superior-centro"),
            ((690, 90, 120, 120), "superior-derecha"),
            ((90, 390, 120, 120), "centro-izquierda"),
            ((390, 390, 120, 120), "centro"),
            ((690, 390, 120, 120), "centro-derecha"),
            ((90, 690, 120, 120), "inferior-izquierda"),
            ((390, 690, 120, 120), "inferior-centro"),
            ((690, 690, 120, 120), "inferior-derecha"),
        )
        for rect, esperado in casos:
            with self.subTest(rect=rect):
                self.assertEqual(
                    obs_escena.zona_cercana(rect, 900, 900), esperado)

    def test_panel_grande_en_la_esquina_da_cerca_de_esa_esquina(self):
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Panel", 0, 0, 0, 460, 620, 5)],
            1360, 768, {})
        self.assertIn(
            "1: Panel, cerca de la esquina superior izquierda, "
            "460 por 620 píxeles, se ve.", frase)

    def test_la_esquina_no_decide_la_zona_sino_el_centro(self):
        # La esquina (200, 350) cae a la izquierda, el centro (300, 400)
        # al centro: si se usara la esquina daría centro-izquierda.
        self.assertEqual(
            obs_escena.zona_cercana((200, 350, 200, 100), 900, 900),
            "centro")

    def test_fuente_anclada_sigue_sin_cerca(self):
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9)],
            *LIENZO, {"Panel": "navegador"})
        self.assertIn("esquina inferior izquierda", frase)
        self.assertNotIn("cerca", frase)


if __name__ == "__main__":
    unittest.main()
