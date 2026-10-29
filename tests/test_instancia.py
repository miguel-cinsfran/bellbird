"""Pruebas de la comprobación de instancia única de la aplicación."""

import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

from ytchat.core import instancia

RAIZ = Path(__file__).resolve().parent.parent

_NOMBRE_PRUEBA = "YTChatTTS_PruebaInstancia_Mutex"

_GUION = """
import sys
from ytchat.core import instancia
print(instancia.verificar_instancia_unica([], sys.argv[1]), flush=True)
sys.stdin.readline()
"""

_GUION_ESPERA = """
import sys
from ytchat.core import instancia
print(instancia.verificar_instancia_unica(
    ["--esperar-pid", sys.argv[2]], sys.argv[1]), flush=True)
"""


class PruebasHayOtraInstancia(unittest.TestCase):
    def test_already_exists_es_otra_instancia(self):
        self.assertTrue(instancia.hay_otra_instancia(183))

    def test_access_denied_tambien_cuenta_como_otra_instancia(self):
        # El mutex existe pero lo creó una instancia elevada o de otro usuario.
        self.assertTrue(instancia.hay_otra_instancia(5))

    def test_sin_error_no_hay_otra_instancia(self):
        self.assertFalse(instancia.hay_otra_instancia(0))


class PruebasOrdenReabrir(unittest.TestCase):
    def test_sin_orden_usa_la_de_la_app_y_agrega_la_espera(self):
        with mock.patch.object(instancia.paths, "orden_de_la_app",
                               return_value=[r"C:\Apps\Bellbird.exe"]) as base:
            self.assertEqual(instancia.orden_reabrir(123),
                             [r"C:\Apps\Bellbird.exe", "--esperar-pid", "123"])
        base.assert_called_once_with()

    def test_con_orden_agrega_la_espera_al_final(self):
        self.assertEqual(
            instancia.orden_reabrir(
                123, orden=[r"C:\Python\python.exe", r"C:\Repo\main.py"]),
            [r"C:\Python\python.exe", r"C:\Repo\main.py",
             "--esperar-pid", "123"])


class PruebasEsperarProceso(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "La espera es de Windows.")
    def test_vuelve_cuando_el_proceso_termina(self):
        hijo = subprocess.Popen(
            [sys.executable, "-B", "-c", "import time; time.sleep(1)"])
        try:
            inicio = time.monotonic()
            instancia.esperar_proceso(hijo.pid)
            transcurrido = time.monotonic() - inicio
        finally:
            hijo.wait(timeout=30)
        self.assertGreaterEqual(transcurrido, 0.8)
        self.assertLess(transcurrido, 10)

    @unittest.skipUnless(sys.platform == "win32", "La espera es de Windows.")
    def test_el_tope_corta_la_espera(self):
        hijo = subprocess.Popen(
            [sys.executable, "-B", "-c", "import time; time.sleep(5)"])
        try:
            inicio = time.monotonic()
            instancia.esperar_proceso(hijo.pid, tope=0.2)
            transcurrido = time.monotonic() - inicio
        finally:
            hijo.kill()
            hijo.wait(timeout=30)
        self.assertGreaterEqual(transcurrido, 0.15)
        self.assertLess(transcurrido, 3)

    def test_un_pid_que_ya_no_existe_vuelve_enseguida(self):
        hijo = subprocess.Popen([sys.executable, "-B", "-c", "pass"])
        hijo.wait(timeout=30)
        inicio = time.monotonic()
        instancia.esperar_proceso(hijo.pid, tope=0.2)
        self.assertLess(time.monotonic() - inicio, 1.5)


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

    @unittest.skipUnless(sys.platform == "win32", "El mutex es de Windows.")
    def test_con_esperar_pid_arranca_despues_de_que_el_primero_suelta(self):
        primero = subprocess.Popen(
            [sys.executable, "-B", "-c", _GUION, _NOMBRE_PRUEBA],
            cwd=RAIZ, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        segunda = None
        try:
            self.assertEqual(primero.stdout.readline().strip(), "True")
            segunda = subprocess.Popen(
                [sys.executable, "-B", "-c", _GUION_ESPERA,
                 _NOMBRE_PRUEBA, str(primero.pid)],
                cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True)
            time.sleep(0.3)
            self.assertIsNone(segunda.poll(), "la segunda no esperó al primero")
            primero.stdin.write("\n")
            primero.stdin.flush()
            salida, error = segunda.communicate(timeout=30)
            self.assertEqual(salida.strip(), "True", error)
        finally:
            if segunda is not None and segunda.poll() is None:
                segunda.kill()
                segunda.communicate()
            if primero.poll() is None:
                primero.stdin.write("\n")
                primero.stdin.flush()
            primero.wait(timeout=30)
            primero.stdin.close()
            primero.stdout.close()
            primero.stderr.close()


if __name__ == "__main__":
    unittest.main()
