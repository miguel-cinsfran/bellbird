import sys
import threading
import unittest

from bellbird.obs import dispositivo_windows


@unittest.skipUnless(sys.platform == "win32", "COM solo existe en Windows")
class MicrofonoPredeterminadoTest(unittest.TestCase):
    def test_devuelve_un_texto_sin_lanzar(self):
        self.assertIsInstance(dispositivo_windows.microfono_predeterminado(), str)

    def test_se_puede_llamar_dos_veces_seguidas(self):
        primera = dispositivo_windows.microfono_predeterminado()
        segunda = dispositivo_windows.microfono_predeterminado()
        self.assertIsInstance(primera, str)
        self.assertIsInstance(segunda, str)

    def test_se_puede_llamar_desde_un_hilo_nuevo(self):
        resultado = {}

        def consultar():
            try:
                resultado["nombre"] = dispositivo_windows.microfono_predeterminado()
            except Exception as exc:
                resultado["error"] = exc

        hilo = threading.Thread(target=consultar)
        hilo.start()
        hilo.join(10)
        self.assertFalse(hilo.is_alive())
        self.assertNotIn("error", resultado)
        self.assertIsInstance(resultado.get("nombre"), str)


if __name__ == "__main__":
    unittest.main()
