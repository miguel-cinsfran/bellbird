"""Pruebas del detector de rostros YuNet, ejecutadas de verdad, sin dobles."""

import ast
import importlib.util
import unittest
from pathlib import Path
from unittest import mock

from bellbird.camera import detector_rostros, encuadre
from bellbird.camera.detector_rostros import (
    DetectorNoDisponible,
    DetectorRostros,
    ImagenIlegible,
    disponible,
)

FOTO = Path(__file__).resolve().parent / "datos" / "rostro.jpg"


class TestDisponible(unittest.TestCase):

    def test_en_falso_cuando_find_spec_no_encuentra_cv2(self):
        with mock.patch.object(importlib.util, "find_spec",
                               return_value=None):
            self.assertFalse(disponible())

    def test_importar_el_modulo_no_importa_cv2_ni_numpy(self):
        ruta = Path(detector_rostros.__file__)
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in arbol.body:
            if isinstance(nodo, ast.Import):
                for nombre in nodo.names:
                    self.assertNotIn(nombre.name.split(".")[0],
                                     ("cv2", "numpy"))
            elif isinstance(nodo, ast.ImportFrom):
                self.assertNotIn((nodo.module or "").split(".")[0],
                                 ("cv2", "numpy"))


@unittest.skipUnless(disponible(), "falta OpenCV o numpy")
class TestFotoReal(unittest.TestCase):

    def test_un_solo_rostro_centrado_con_confianza(self):
        cuadro = DetectorRostros().analizar(FOTO.read_bytes())
        self.assertEqual(len(cuadro.rostros), 1)
        rostro = cuadro.rostros[0]
        centro_x = (rostro.x + rostro.ancho / 2) / cuadro.ancho
        centro_y = (rostro.y + rostro.alto / 2) / cuadro.alto
        self.assertAlmostEqual(centro_x, 0.50, delta=0.05)
        self.assertAlmostEqual(centro_y, 0.30, delta=0.05)
        self.assertLess(rostro.ojo_izquierda[0], rostro.ojo_derecha[0])
        self.assertGreater(rostro.confianza, 0.9)

    def test_la_misma_foto_en_bmp_da_lo_mismo(self):
        import cv2
        import numpy
        datos = FOTO.read_bytes()
        imagen = cv2.imdecode(
            numpy.frombuffer(datos, dtype=numpy.uint8), cv2.IMREAD_COLOR)
        _ok, bmp = cv2.imencode(".bmp", imagen)
        cuadro_jpg = DetectorRostros().analizar(datos)
        cuadro_bmp = DetectorRostros().analizar(bytes(bmp))
        self.assertEqual(len(cuadro_bmp.rostros), 1)
        self.assertEqual(len(cuadro_jpg.rostros), 1)
        for cuadro in (cuadro_jpg, cuadro_bmp):
            rostro = cuadro.rostros[0]
            centro_x = (rostro.x + rostro.ancho / 2) / cuadro.ancho
            centro_y = (rostro.y + rostro.alto / 2) / cuadro.alto
            self.assertAlmostEqual(centro_x, 0.50, delta=0.05)
            self.assertAlmostEqual(centro_y, 0.30, delta=0.05)
            self.assertGreater(rostro.confianza, 0.9)

    def test_gris_lisa_sin_rostros_y_sin_luz_de_rostro(self):
        import cv2
        import numpy
        gris = numpy.full((120, 160, 3), 128, dtype=numpy.uint8)
        _ok, png = cv2.imencode(".png", gris)
        cuadro = DetectorRostros().analizar(bytes(png))
        self.assertEqual(cuadro.rostros, ())
        self.assertIsNone(cuadro.luz_rostro)
        self.assertAlmostEqual(cuadro.luz_fondo, 128.0, delta=1.0)

    def test_mismos_bytes_misma_huella_y_un_pixel_otra(self):
        import cv2
        import numpy
        datos = FOTO.read_bytes()
        detector = DetectorRostros()
        self.assertEqual(detector.analizar(datos).huella,
                         detector.analizar(datos).huella)
        base = numpy.zeros((50, 60, 3), dtype=numpy.uint8)
        _ok, primero = cv2.imencode(".png", base)
        cambiada = base.copy()
        cambiada[10, 10, 0] = 1
        _ok, segundo = cv2.imencode(".png", cambiada)
        self.assertNotEqual(detector.analizar(bytes(primero)).huella,
                            detector.analizar(bytes(segundo)).huella)

    def test_bytes_que_no_son_imagen_lanzan_ilegible(self):
        with self.assertRaises(ImagenIlegible):
            DetectorRostros().analizar(b"esto no es una imagen")

    def test_ruta_de_modelo_inexistente_lanza_no_disponible(self):
        detector = DetectorRostros(ruta_modelo="falta/modelo.onnx")
        with self.assertRaises(DetectorNoDisponible):
            detector.analizar(FOTO.read_bytes())

    def test_nariz_entre_los_ojos_y_encuadre_sin_giro_ni_inclinacion(self):
        cuadro = DetectorRostros().analizar(FOTO.read_bytes())
        rostro = cuadro.rostros[0]
        izquierda = min(rostro.ojo_izquierda[0], rostro.ojo_derecha[0])
        derecha = max(rostro.ojo_izquierda[0], rostro.ojo_derecha[0])
        self.assertGreater(rostro.nariz[0], izquierda)
        self.assertLess(rostro.nariz[0], derecha)
        debajo = max(rostro.ojo_izquierda[1], rostro.ojo_derecha[1])
        self.assertGreater(rostro.nariz[1], debajo)
        estado = encuadre.analizar(cuadro.rostros, cuadro.ancho, cuadro.alto)
        self.assertNotIn("girado", estado.problemas)
        self.assertNotIn("inclinado", estado.problemas)

    def test_frase_de_extremo_a_extremo_no_es_ningun_rostro(self):
        cuadro = DetectorRostros().analizar(FOTO.read_bytes())
        estado = encuadre.analizar(
            cuadro.rostros, cuadro.ancho, cuadro.alto,
            luz_rostro=cuadro.luz_rostro, luz_fondo=cuadro.luz_fondo)
        self.assertNotEqual(encuadre.frase(estado), "Ningún rostro.")


if __name__ == "__main__":
    unittest.main()
