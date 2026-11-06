"""Pruebas de las transformaciones puras de una fuente de OBS."""

import unittest

from guyrapu.obs import transformar_fuente
from guyrapu.obs.obs_escena import FilaFuente


def fuente(**cambios):
    datos = {
        "positionX": 100.0, "positionY": 200.0,
        "width": 400.0, "height": 300.0,
        "sourceWidth": 400.0, "sourceHeight": 300.0,
        "alignment": 5, "rotation": 0.0,
        "scaleX": 1.0, "scaleY": 1.0,
        "boundsType": "OBS_BOUNDS_NONE",
        "boundsAlignment": 0, "boundsWidth": 0, "boundsHeight": 0,
    }
    datos.update(cambios)
    return datos


def fuente_medida():
    return fuente(
        positionX=300.0, positionY=200.0, width=400.0, height=200.0,
        sourceWidth=400.0, sourceHeight=200.0)


class TextoDeTamanoTest(unittest.TestCase):

    def test_una_fraccion_comun_se_dice_con_palabras(self):
        self.assertEqual(
            transformar_fuente.texto_de_tamano(400, 1600),
            "un cuarto del vídeo")
        self.assertEqual(
            transformar_fuente.texto_de_tamano(800, 1600),
            "la mitad del vídeo")

    def test_fuera_de_las_fracciones_dice_el_porcentaje_del_ancho(self):
        self.assertEqual(
            transformar_fuente.texto_de_tamano(460, 1600),
            "29 por ciento del ancho")

    def test_un_punto_de_diferencia_sigue_siendo_la_fraccion(self):
        self.assertEqual(
            transformar_fuente.texto_de_tamano(416, 1600),
            "un cuarto del vídeo")

    def test_sin_lienzo_no_inventa_un_tamano(self):
        self.assertEqual(transformar_fuente.texto_de_tamano(400, 0), "")


class NombreDeCopiaTest(unittest.TestCase):

    def test_la_primera_copia(self):
        self.assertEqual(
            transformar_fuente.nombre_de_copia(["Cámara"], "Cámara"),
            "Cámara - copia")

    def test_si_ya_existe_usa_el_numero_siguiente(self):
        self.assertEqual(
            transformar_fuente.nombre_de_copia(
                ["Cámara", "Cámara - copia", "Cámara - copia 2"], "Cámara"),
            "Cámara - copia 3")

    def test_no_distingue_mayusculas(self):
        self.assertEqual(
            transformar_fuente.nombre_de_copia(
                ["CÁMARA - COPIA"], "Cámara"), "Cámara - copia 2")


class TransformacionesTest(unittest.TestCase):

    def test_centrar_pone_el_centro_en_el_medio_del_lienzo(self):
        nueva = transformar_fuente.centrar(fuente(), 1600, 900)
        self.assertEqual(nueva["alignment"], 0)
        self.assertAlmostEqual(nueva["positionX"], 800)
        self.assertAlmostEqual(nueva["positionY"], 450)

    def test_ajustar_usa_el_lienzo_como_cuadro_y_lo_centra(self):
        nueva = transformar_fuente.ajustar(fuente(), 1600, 900)
        self.assertEqual(nueva["boundsType"], "OBS_BOUNDS_SCALE_INNER")
        self.assertEqual(nueva["boundsAlignment"], 0)
        self.assertEqual(nueva["boundsWidth"], 1600)
        self.assertEqual(nueva["boundsHeight"], 900)
        self.assertAlmostEqual(nueva["positionX"], 800)
        self.assertAlmostEqual(nueva["positionY"], 450)

    def test_llenar_usa_el_cuadro_exterior(self):
        nueva = transformar_fuente.llenar(fuente(), 1600, 900)
        self.assertEqual(nueva["boundsType"], "OBS_BOUNDS_SCALE_OUTER")
        self.assertEqual(nueva["boundsWidth"], 1600)
        self.assertEqual(nueva["boundsHeight"], 900)

    def test_voltear_horizontal_cambia_el_signo_y_conserva_el_centro(self):
        original = fuente()
        centro = transformar_fuente.centro_de(original)
        nueva = transformar_fuente.voltear_horizontal(original)
        self.assertEqual(nueva["scaleX"], -1)
        self.assertEqual(nueva["scaleY"], 1)
        self.assertCentro(centro, transformar_fuente.centro_de(nueva))

    def test_voltear_vertical_cambia_el_signo_y_conserva_el_centro(self):
        original = fuente()
        centro = transformar_fuente.centro_de(original)
        nueva = transformar_fuente.voltear_vertical(original)
        self.assertEqual(nueva["scaleX"], 1)
        self.assertEqual(nueva["scaleY"], -1)
        self.assertCentro(centro, transformar_fuente.centro_de(nueva))

    def test_girar_conserva_el_centro(self):
        original = fuente()
        centro = transformar_fuente.centro_de(original)
        for grados in (90, -90, 180):
            with self.subTest(grados=grados):
                nueva = transformar_fuente.girar(original, grados)
                self.assertCentro(
                    centro, transformar_fuente.centro_de(nueva))

    def test_voltear_horizontal_deja_la_posicion_medida(self):
        nueva = transformar_fuente.voltear_horizontal(fuente_medida())
        self.assertEqual(nueva["positionX"], 700)
        self.assertEqual(nueva["positionY"], 200)

    def test_voltear_vertical_deja_la_posicion_medida(self):
        nueva = transformar_fuente.voltear_vertical(fuente_medida())
        self.assertEqual(nueva["positionX"], 300)
        self.assertEqual(nueva["positionY"], 400)

    def test_girar_90_deja_la_posicion_medida(self):
        nueva = transformar_fuente.girar(fuente_medida(), 90)
        self.assertEqual(nueva["rotation"], 90)
        self.assertEqual(nueva["positionX"], 600)
        self.assertEqual(nueva["positionY"], 100)

    def test_caja_visible_usa_la_misma_formula(self):
        self.assertEqual(
            transformar_fuente.caja_visible(fuente_medida()),
            (300, 200, 400, 200))

    def test_la_caja_conserva_el_centro_al_voltear_y_girar(self):
        base = fuente_medida()
        ya_volteada_y_girada = transformar_fuente.girar(
            transformar_fuente.voltear_horizontal(base), 90)
        con_cuadro = transformar_fuente.ajustar(base, 1600, 900)
        for original in (base, ya_volteada_y_girada, con_cuadro):
            centro = self._centro_de_caja(original)
            for nueva in (
                    transformar_fuente.voltear_horizontal(original),
                    transformar_fuente.voltear_vertical(original),
                    transformar_fuente.girar(original, 90)):
                self.assertCentro(
                    centro, self._centro_de_caja(nueva))

    def _centro_de_caja(self, transformacion):
        izquierda, arriba, ancho, alto = transformar_fuente.caja_visible(
            transformacion)
        return (izquierda + ancho / 2, arriba + alto / 2)

    def test_cuatro_giros_a_la_derecha_vuelven_al_principio(self):
        original = fuente()
        nueva = original
        for _ in range(4):
            nueva = transformar_fuente.girar(nueva, 90)
        self.assertAlmostEqual(nueva["rotation"] % 360, 0)
        self.assertAlmostEqual(nueva["positionX"], original["positionX"])
        self.assertAlmostEqual(nueva["positionY"], original["positionY"])

    def test_restablecer_vuelve_arriba_a_la_izquierda_y_sin_efectos(self):
        nueva = transformar_fuente.restablecer(
            fuente(rotation=90, scaleX=-1, scaleY=-1,
                   boundsType="OBS_BOUNDS_SCALE_INNER",
                   boundsWidth=800, boundsHeight=600,
                   cropLeft=10, cropRight=20, cropTop=30, cropBottom=40))
        self.assertEqual(nueva["positionX"], 0)
        self.assertEqual(nueva["positionY"], 0)
        self.assertEqual(nueva["alignment"], 5)
        self.assertEqual(nueva["rotation"], 0)
        self.assertEqual(nueva["scaleX"], 1)
        self.assertEqual(nueva["scaleY"], 1)
        self.assertEqual(nueva["boundsType"], "OBS_BOUNDS_NONE")
        self.assertEqual(nueva["cropLeft"], 0)
        self.assertEqual(nueva["cropRight"], 0)
        self.assertEqual(nueva["cropTop"], 0)
        self.assertEqual(nueva["cropBottom"], 0)

    def test_una_fuente_ya_girada_tambien_conserva_el_centro(self):
        original = fuente(rotation=45)
        centro = transformar_fuente.centro_de(original)
        nueva = transformar_fuente.girar(original, 90)
        self.assertCentro(centro, transformar_fuente.centro_de(nueva))

    def assertCentro(self, esperado, obtenido):
        self.assertAlmostEqual(esperado[0], obtenido[0])
        self.assertAlmostEqual(esperado[1], obtenido[1])


class LimpiarTransformacionTest(unittest.TestCase):

    REAL = {
        "alignment": 5, "boundsAlignment": 0, "boundsHeight": 0.0,
        "boundsType": "OBS_BOUNDS_NONE", "boundsWidth": 0.0,
        "cropBottom": 0, "cropLeft": 0, "cropRight": 0,
        "cropToBounds": False, "cropTop": 0, "height": 200.0,
        "positionX": 0.0, "positionY": 0.0, "rotation": 0.0,
        "scaleX": 1.0, "scaleY": 1.0, "sourceHeight": 200.0,
        "sourceWidth": 400.0, "width": 400.0,
    }

    def test_voltear_girar_y_centrar_no_dejan_claves_de_solo_lectura(self):
        for calculo, argumentos in (
                (transformar_fuente.voltear_horizontal, ()),
                (transformar_fuente.girar, (90,)),
                (transformar_fuente.centrar, (1600, 900))):
            with self.subTest(calculo=calculo.__name__):
                limpia = transformar_fuente.limpiar_transformacion(
                    calculo(self.REAL, *argumentos))
                self.assertNotIn("width", limpia)
                self.assertNotIn("height", limpia)
                self.assertNotIn("sourceWidth", limpia)
                self.assertNotIn("sourceHeight", limpia)
                self.assertNotIn("cropToBounds", limpia)
                self.assertNotIn("boundsWidth", limpia)
                self.assertNotIn("boundsHeight", limpia)
                self.assertNotIn("boundsAlignment", limpia)


class FraseDeAccionTest(unittest.TestCase):

    def test_nombra_la_accion_y_repite_donde_quedo(self):
        fila = FilaFuente(
            "Cámara", "Cámara", True, False, tipo="cámara",
            posicion="abajo a la derecha", tamano="un cuarto del vídeo")
        self.assertEqual(
            transformar_fuente.frase_de_accion(fila, "volteada horizontalmente"),
            "Cámara volteada horizontalmente. Abajo a la derecha. "
            "Un cuarto del vídeo.")

    def test_sin_tamano_no_deja_una_frase_vacia(self):
        fila = FilaFuente(
            "Cámara", "Cámara", True, False,
            posicion="ocupa todo el vídeo")
        self.assertEqual(
            transformar_fuente.frase_de_accion(fila, "centrada"),
            "Cámara centrada. Ocupa todo el vídeo.")


if __name__ == "__main__":
    unittest.main()
