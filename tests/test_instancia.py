"""Pruebas de la comprobación de instancia única de la aplicación."""

import subprocess
import sys
import unittest
from pathlib import Path

from ytchat.core import instancia

RAIZ = Path(__file__).resolve().parent.parent

_NOMBRE_PRUEBA = "YTChatTTS_PruebaInstancia_Mutex"

_GUION = """
import sys
from ytchat.core import instancia
print(instancia.verificar_instancia_unica(sys.argv[1]), flush=True)
sys.stdin.readline()
"""


class PruebasHayOtraInstancia(unittest.TestCase):
    def test_already_exists_es_otra_instancia(self):
        self.assertTrue(instancia.hay_otra_instancia(183))

    def test_access_denied_tambien_cuenta_como_otra_instancia(self):
        # El mutex existe pero lo creó una instancia elevada o de otro usuario.
        self.assertTrue(instancia.hay_otra_instancia(5))

    def test_sin_error_no_hay_otra_instancia(self):
        self.assertFalse(instancia.hay_otra_instancia(0))


class PruebasVerificarInstanciaUnica(unittest.TestCase):
    def test_el_nombre_del_mutex_de_la_app_no_cambia(self):
        self.assertEqual(instancia._NOMBRE_MUTEX,
                         "YTChatTTS_SingleInstance_Mutex")

    @unittest.skipUnless(sys.platform == "win32", "El mutex es de Windows.")
    def test_la_segunda_instancia_en_otro_proceso_da_falso(self):
        primero = subprocess.Popen(
            [sys.executable, "-B", "-c", _GUION, _NOMBRE_PRUEBA],
            cwd=RAIZ, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(primero.stdout.readline().strip(), "True")
            segunda = subprocess.run(
                [sys.executable, "-B", "-c", _GUION, _NOMBRE_PRUEBA],
                cwd=RAIZ, input="\n", capture_output=True, text=True,
                timeout=30)
            self.assertEqual(segunda.stdout.strip(), "False", segunda.stderr)
        finally:
            if primero.poll() is None:
                primero.stdin.write("\n")
                primero.stdin.flush()
            primero.wait(timeout=30)
            primero.stdin.close()
            primero.stdout.close()
            primero.stderr.close()


if __name__ == "__main__":
    unittest.main()
