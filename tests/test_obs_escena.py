"""Pruebas de la descripción hablada de la escena al aire."""

import unittest

from tests.pseudo_prueba import con_pseudo
from guyrapu.obs import obs_escena


def elemento(identificador, nombre, indice, x=0, y=0, ancho=0, alto=0,
              alineacion=0, visible=True, bounds=None, bloqueada=False):
    transformacion = {"positionX": x, "positionY": y, "width": ancho,
                      "height": alto, "alignment": alineacion}
    if bounds is not None:
        transformacion.update(bounds)
    return {"sceneItemId": identificador, "sourceName": nombre,
            "sceneItemIndex": indice, "sceneItemEnabled": visible,
            "sceneItemLocked": bloqueada,
            "sceneItemTransform": transformacion}


LIENZO = (1600, 900)


class DescribirEscenaTest(unittest.TestCase):
    def test_escena_vacia(self):
        self.assertEqual(
            obs_escena.describir_escena("Juego", [], *LIENZO, {}),
            "Escena actual: Juego. No tiene fuentes.")

    def test_escena_pedida_no_dice_actual(self):
        self.assertEqual(
            obs_escena.describir_escena("Juego", [], *LIENZO, {},
                                        actual=False),
            "Escena: Juego. No tiene fuentes.")

    def test_escena_pedida_con_fuentes_no_dice_actual(self):
        frase = obs_escena.describir_escena(
            "Juego", [elemento(1, "Fondo", 0, 800, 450, 1600, 900, 0)],
            *LIENZO, {"Fondo": "imagen"}, actual=False)
        self.assertEqual(
            frase.splitlines()[0],
            "Escena: Juego. 1 fuente, de adelante hacia atrás.")

    def test_una_sola_fuente_en_singular(self):
        frase = obs_escena.describir_escena(
            "Juego", [elemento(1, "Fondo", 0, 800, 450, 1600, 900, 0)],
            *LIENZO, {"Fondo": "imagen"})
        self.assertEqual(
            frase,
            "Escena actual: Juego. 1 fuente, de adelante hacia atrás.\n"
            "1: Fondo, imagen, ocupa todo el vídeo, se ve.")

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
            "Escena actual: Principal. 2 fuentes, de adelante hacia atrás.\n"
            "1: Captura, captura de pantalla, ocupa todo el vídeo, se ve.\n"
            "2: Panel, navegador, abajo a la izquierda, "
            "29 por ciento del ancho, visible en OBS, pero no aparece en "
            "el vídeo: la tapa entera Captura.")

    def test_fuente_oculta_no_dice_tapada(self):
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9, visible=False),
             elemento(2, "Captura", 1, 800, 450, 1600, 900, 0)],
            *LIENZO, {"Panel": "navegador", "Captura": "captura de pantalla"})
        self.assertIn("2: Panel, navegador, abajo a la izquierda, "
                      "29 por ciento del ancho, oculta en OBS.", frase)

    def test_captura_oculta_no_tapa(self):
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9),
             elemento(2, "Captura", 1, 800, 450, 1600, 900, 0, visible=False)],
            *LIENZO, {"Panel": "navegador", "Captura": "captura de pantalla"})
        self.assertIn("2: Panel, navegador, abajo a la izquierda, "
                      "29 por ciento del ancho, se ve.", frase)

    def test_tapa_leve_no_se_dice(self):
        # El frente cubre 200 por 100 de 460 por 620: 7 %, debajo del aviso.
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9),
             elemento(2, "Aviso", 1, 32, 262, 200, 100, 5)],
            *LIENZO, {"Panel": "navegador", "Aviso": "texto"})
        self.assertIn("2: Panel, navegador, abajo a la izquierda, "
                      "29 por ciento del ancho, se ve.", frase)

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
        self.assertIn("visible en OBS, pero no aparece en el vídeo: "
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
            "Escena actual: Principal. 1 fuente, de adelante hacia atrás.\n"
            "1: Juego, captura de juego, cerca de la posición centro a la derecha, "
            "la mitad del vídeo, se ve y un 25 por ciento queda "
            "fuera del vídeo.")

    def test_sin_transformacion_no_rompe_el_resto(self):
        frase = obs_escena.describir_escena(
            "Principal",
            [{"sourceName": "Rota", "sceneItemIndex": 0},
             elemento(2, "Captura", 1, 800, 450, 1600, 900, 0)],
            *LIENZO, {"Rota": "imagen", "Captura": "captura de pantalla"})
        self.assertEqual(
            frase,
            "Escena actual: Principal. 2 fuentes, de adelante hacia atrás.\n"
            "1: Captura, captura de pantalla, ocupa todo el vídeo, se ve.\n"
            "2: Rota, imagen, posición desconocida, se ve.")

    def test_sin_tipo_no_deja_hueco(self):
        frase = obs_escena.describir_escena(
            "Principal", [elemento(1, "Rara", 0, 800, 450, 1600, 900, 0)],
            *LIENZO, {})
        self.assertIn("1: Rara, ocupa todo el vídeo, se ve.", frase)

    def test_con_bounds_activos_el_tamano_sale_de_ahi(self):
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Foto", 0, 800, 450, 3840, 2160, 0,
                      bounds={"boundsType": "OBS_BOUNDS_SCALE_INNER",
                              "boundsWidth": 1600, "boundsHeight": 900})],
            *LIENZO, {"Foto": "imagen"})
        self.assertIn("1: Foto, imagen, ocupa todo el vídeo, se ve.", frase)

    def test_una_oracion_por_linea(self):
        frase = obs_escena.describir_escena(
            "Principal",
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9),
              elemento(2, "Captura", 1, 800, 450, 1600, 900, 0)],
            *LIENZO, {"Panel": "navegador", "Captura": "captura de pantalla"})
        self.assertEqual(len(frase.splitlines()), 3)
        for linea in frase.splitlines():
            self.assertTrue(linea.endswith("."))


class FilasDeEscenaTest(unittest.TestCase):
    def test_el_ejemplo_de_e3_sin_numero_ni_punto(self):
        elementos = [
            elemento(1, "Chat en el vídeo", 1, 1568, 882, 460, 620, 10,
                     bloqueada=True),
            elemento(2, "Cámara", 0, 800, 450, 1600, 900, 0),
        ]
        filas = obs_escena.filas_de_escena(
            elementos, *LIENZO,
            {"Chat en el vídeo": "navegador", "Cámara": "cámara"})
        self.assertEqual(
            [fila.texto for fila in filas],
            ["Chat en el vídeo, navegador, abajo a la derecha, "
             "29 por ciento del ancho, se ve, bloqueada",
             "Cámara, cámara, ocupa todo el vídeo, se ve en parte: "
             "Chat en el vídeo tapa el 20 por ciento"])
        self.assertEqual([fila.nombre for fila in filas],
                         ["Chat en el vídeo", "Cámara"])

    def test_una_fuente_oculta_lo_dice(self):
        filas = obs_escena.filas_de_escena(
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9, visible=False)],
            *LIENZO, {"Panel": "navegador"})
        self.assertEqual(
            filas[0].texto,
            "Panel, navegador, abajo a la izquierda, 29 por ciento del ancho, "
            "oculta en OBS")
        self.assertFalse(filas[0].visible)

    def test_una_fraccion_comun_se_dice_con_palabras(self):
        filas = obs_escena.filas_de_escena(
            [elemento(1, "Panel", 0, 0, 0, 400, 300, 5)],
            *LIENZO, {"Panel": "navegador"})
        self.assertEqual(filas[0].tamano, "un cuarto del vídeo")
        self.assertEqual(filas[0].tipo, "navegador")

    def test_fuera_de_las_fracciones_dice_el_porcentaje_del_ancho(self):
        filas = obs_escena.filas_de_escena(
            [elemento(1, "Panel", 0, 0, 0, 460, 620, 5)],
            *LIENZO, {"Panel": "navegador"})
        self.assertEqual(filas[0].tamano, "29 por ciento del ancho")

    def test_una_bloqueada_termina_en_bloqueada(self):
        filas = obs_escena.filas_de_escena(
            [elemento(1, "Panel", 0, 32, 882, 460, 620, 9, bloqueada=True)],
            *LIENZO, {"Panel": "navegador"})
        self.assertTrue(filas[0].texto.endswith(", bloqueada"))
        self.assertTrue(filas[0].bloqueada)

    def test_cada_linea_de_la_descripcion_es_la_fila_sin_bloqueo(self):
        elementos = [
            elemento(1, "Panel", 0, 32, 882, 460, 620, 9),
            elemento(2, "Captura", 1, 800, 450, 1600, 900, 0),
            elemento(3, "Aviso", 2, 32, 262, 200, 100, 5, visible=False),
        ]
        tipos = {"Panel": "navegador", "Captura": "captura de pantalla",
                 "Aviso": "texto"}
        filas = obs_escena.filas_de_escena(elementos, *LIENZO, tipos)
        lineas = obs_escena.describir_escena(
            "Principal", elementos, *LIENZO, tipos).splitlines()
        self.assertEqual(len(lineas), len(filas) + 1)
        for numero, (linea, fila) in enumerate(zip(lineas[1:], filas), 1):
            with self.subTest(numero=numero):
                self.assertEqual(linea, f"{numero}: {fila.texto}.")


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
            "1: Panel, cerca de la posición arriba a la izquierda, "
            "un tercio del vídeo, se ve.", frase)

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
        self.assertIn("abajo a la izquierda", frase)
        self.assertNotIn("cerca", frase)


class TestPseudoTextos(unittest.TestCase):
    """Bajo pseudotraducción, cada frase al usuario sale marcada."""

    def test_escenas_salen_marcadas_y_conservan_los_datos(self):
        with con_pseudo():
            vacia = obs_escena.describir_escena("Juego", [], *LIENZO, {})
            llena = obs_escena.describir_escena(
                "Principal",
                [elemento(1, "Panel", 0, 32, 882, 460, 620, 9),
                 elemento(2, "Captura", 1, 800, 450, 1600, 900, 0)],
                *LIENZO, {"Panel": "navegador", "Captura": "captura"})
        for frase in (vacia, llena):
            with self.subTest(frase=frase):
                self.assertTrue(frase.startswith("[¡"), frase)
        self.assertIn("Juego", vacia)
        self.assertIn("Principal", llena)
        self.assertIn("Panel", llena)
        self.assertIn("Captura", llena)


if __name__ == "__main__":
    unittest.main()
