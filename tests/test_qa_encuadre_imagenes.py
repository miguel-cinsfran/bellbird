"""Pruebas de las imágenes vivas del escenario de encuadre del banco.

Se importa `qa/encuadre_imagenes.py` por ruta, como el resto de las pruebas
del banco, para no depender de que `qa/` sea un paquete.
"""

import importlib.util
import tempfile
import threading
import time
import unittest
from pathlib import Path

try:
    import cv2
    import numpy
except ImportError:
    cv2 = None
    numpy = None

_RUTA = Path(__file__).resolve().parent.parent / "qa" / "encuadre_imagenes.py"
_modulo = importlib.util.spec_from_file_location("encuadre_imagenes_qa", _RUTA)
encuadre_imagenes = importlib.util.module_from_spec(_modulo)
_modulo.loader.exec_module(encuadre_imagenes)


def _decodificar(ruta):
    datos = Path(ruta).read_bytes()
    return cv2.imdecode(numpy.frombuffer(datos, dtype=numpy.uint8),
                        cv2.IMREAD_COLOR)


@unittest.skipIf(cv2 is None, "falta OpenCV o numpy")
class TestVariantes(unittest.TestCase):

    def setUp(self):
        self._temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporal.cleanup)
        self.carpeta = Path(self._temporal.name)

    def _comprobar(self, primera, segunda):
        self.assertTrue(Path(primera).is_file())
        self.assertTrue(Path(segunda).is_file())
        self.assertNotEqual(Path(primera).read_bytes(),
                            Path(segunda).read_bytes())
        cuadro_a = _decodificar(primera)
        cuadro_b = _decodificar(segunda)
        self.assertEqual(cuadro_a.shape, cuadro_b.shape)
        distintos = numpy.any(cuadro_a != cuadro_b, axis=2)
        self.assertEqual(int(numpy.count_nonzero(distintos)), 1)

    def test_las_dos_variantes_de_la_foto_difieren_en_un_pixel(self):
        primera, segunda = encuadre_imagenes.variantes_foto(self.carpeta)
        self._comprobar(primera, segunda)

    def test_las_dos_variantes_del_gris_difieren_en_un_pixel(self):
        primera, segunda = encuadre_imagenes.variantes_gris(self.carpeta)
        self._comprobar(primera, segunda)


class _Gestor:
    """Gestor de OBS doble que anota cada `SetInputSettings`."""

    def __init__(self, falla=False):
        self.falla = falla
        self.pedidos = []
        self._cerrojo = threading.Lock()

    def _pedir(self, orden, datos):
        with self._cerrojo:
            self.pedidos.append(dict(datos["inputSettings"]))
        if self.falla:
            raise OSError("OBS no contestó")
        return {}


class TestAlternador(unittest.TestCase):

    def setUp(self):
        self._temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporal.cleanup)
        carpeta = Path(self._temporal.name)
        self.variantes = {}
        for cual in ("foto", "gris"):
            primera = carpeta / f"{cual}-a.bmp"
            segunda = carpeta / f"{cual}-b.bmp"
            primera.write_bytes(cual.encode("ascii") + b"-a")
            segunda.write_bytes(cual.encode("ascii") + b"-b")
            self.variantes[cual] = (primera, segunda)

    def _esperar(self, condicion, segundos=2.0):
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            if condicion():
                return True
            time.sleep(0.01)
        return False

    def _alternador(self, gestor, intervalo=0.05):
        alternador = encuadre_imagenes.Alternador(
            gestor, "Prueba Bellbird encuadre", self.variantes,
            intervalo=intervalo)
        self.addCleanup(alternador.detener)
        return alternador

    def test_alterna_las_dos_variantes_de_la_imagen_elegida(self):
        gestor = _Gestor()
        self._alternador(gestor)

        self.assertTrue(self._esperar(lambda: len(gestor.pedidos) >= 3))

        enviadas = {Path(p["file"]).name for p in gestor.pedidos}
        self.assertEqual(enviadas, {"foto-a.bmp", "foto-b.bmp"})

    def test_mostrar_cambia_a_la_otra_imagen_en_el_momento(self):
        gestor = _Gestor()
        alternador = self._alternador(gestor, intervalo=10.0)

        antes = time.monotonic()
        instante = alternador.mostrar("gris")

        self.assertGreaterEqual(instante, antes)
        self.assertEqual(len(gestor.pedidos), 1)
        self.assertEqual(Path(gestor.pedidos[0]["file"]).name, "gris-a.bmp")

    def test_un_fallo_del_gestor_se_guarda_sin_matar_el_hilo(self):
        gestor = _Gestor(falla=True)
        alternador = self._alternador(gestor)

        self.assertTrue(self._esperar(lambda: len(gestor.pedidos) >= 2))

        self.assertIsNotNone(alternador.fallo)
        self.assertTrue(alternador.hilo.is_alive())

    def test_tras_detener_no_manda_mas_y_el_hilo_termina(self):
        gestor = _Gestor()
        alternador = self._alternador(gestor)
        self.assertTrue(self._esperar(lambda: len(gestor.pedidos) >= 1))

        alternador.detener()
        cuantos = len(gestor.pedidos)
        time.sleep(0.2)

        self.assertEqual(len(gestor.pedidos), cuantos)
        self.assertFalse(alternador.hilo.is_alive())


if __name__ == "__main__":
    unittest.main()
