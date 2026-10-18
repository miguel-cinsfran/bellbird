import ctypes
import os
import subprocess
import sys
import tempfile
import time
import threading
import unittest
from unittest import mock
from unittest.mock import patch

from ytchat.core import subprocesos
from ytchat.core.subprocesos import (
    Estado,
    ejecutar,
    sin_carpeta_dll_heredada,
)


class PruebasSubprocesos(unittest.TestCase):

    def test_hijo_cero_exito_y_recolectado(self):
        capturados = []
        real = subprocess.Popen

        def envolver(*a, **k):
            p = real(*a, **k)
            capturados.append(p)
            return p

        with patch.object(subprocesos.subprocess, "Popen", side_effect=envolver):
            estado = ejecutar([sys.executable, "-c", "import sys; sys.exit(0)"],
                              tope_segundos=5)
        self.assertEqual(Estado.exito, estado)
        self.assertTrue(capturados)
        for p in capturados:
            self.assertIsNotNone(p.poll(), "hijo no recolectado")
            self.assertEqual(0, p.returncode)

    def test_hijo_distinto_de_cero_fallo(self):
        estado = ejecutar([sys.executable, "-c", "import sys; sys.exit(2)"],
                          tope_segundos=5)
        self.assertEqual(Estado.fallo, estado)

    def test_hijo_dormido_evento_desde_otro_hilo_cancelado(self):
        evento = threading.Event()
        capturados = []
        real = subprocess.Popen

        def envolver(*a, **k):
            p = real(*a, **k)
            capturados.append(p)
            return p

        def marcar():
            time.sleep(0.2)
            evento.set()

        hilo = threading.Thread(target=marcar)
        hilo.start()
        inicio = time.monotonic()
        with patch.object(subprocesos.subprocess, "Popen", side_effect=envolver):
            estado = ejecutar([sys.executable, "-c", "import time; time.sleep(10)"],
                              cancel_event=evento, tope_segundos=10)
        duracion = time.monotonic() - inicio
        hilo.join(timeout=2)
        self.assertEqual(Estado.cancelado, estado)
        self.assertLess(duracion, 4, f"tardó {duracion:.2f}s, debe volver rápido")
        for p in capturados:
            self.assertIsNotNone(p.poll(), "hijo cancelado no recolectado")

    def test_hijo_dormido_supera_tope_vencido(self):
        capturados = []
        real = subprocess.Popen

        def envolver(*a, **k):
            p = real(*a, **k)
            capturados.append(p)
            return p

        inicio = time.monotonic()
        with patch.object(subprocesos.subprocess, "Popen", side_effect=envolver):
            estado = ejecutar([sys.executable, "-c", "import time; time.sleep(10)"],
                              tope_segundos=1)
        duracion = time.monotonic() - inicio
        self.assertEqual(Estado.vencido, estado)
        self.assertLess(duracion, 4, f"tardó {duracion:.2f}s")
        self.assertGreaterEqual(duracion, 0.8)
        for p in capturados:
            self.assertIsNotNone(p.poll(), "hijo vencido no recolectado")

    def test_evento_ya_marcado_lanza_y_cancela(self):
        # Frontera real: evento marcado antes de lanzar debe igual lanzar y recolectar
        evento = threading.Event()
        evento.set()
        capturados = []
        real = subprocess.Popen

        def envolver(*a, **k):
            p = real(*a, **k)
            capturados.append(p)
            return p

        inicio = time.monotonic()
        with patch.object(subprocesos.subprocess, "Popen", side_effect=envolver):
            estado = ejecutar([sys.executable, "-c", "import time; time.sleep(10)"],
                              cancel_event=evento, tope_segundos=10)
        duracion = time.monotonic() - inicio
        self.assertEqual(Estado.cancelado, estado)
        self.assertLess(duracion, 4)
        self.assertTrue(capturados)
        for p in capturados:
            self.assertIsNotNone(p.poll())

    def test_vincular_ignora_lo_que_no_es_un_popen_real(self):
        falso = mock.Mock(pid=4242)
        nucleo = mock.Mock()
        with patch.object(subprocesos.os, "name", "nt"), \
                patch.object(subprocesos, "_job_app",
                             return_value=object()), \
                patch.object(ctypes, "WinDLL", return_value=nucleo):
            subprocesos.vincular_a_la_app(falso)
        nucleo.OpenProcess.assert_not_called()
        nucleo.AssignProcessToJobObject.assert_not_called()

    def test_os_error_al_arrancar_devuelve_fallo(self):
        with patch.object(subprocesos.subprocess, "Popen", side_effect=OSError("no existe")):
            estado = ejecutar(["no_existe_binario_xyz"], tope_segundos=2)
        self.assertEqual(Estado.fallo, estado)

    def test_excepcion_de_programacion_en_poll_propaga_y_no_deja_hijo_vivo(self):
        capturados = []
        real_popen = subprocess.Popen

        def envolver(*args, **kwargs):
            proceso = real_popen(*args, **kwargs)
            capturados.append(proceso)
            original_poll = proceso.poll

            def poll_falla(*a, **k):
                raise RuntimeError("falla de programación")

            proceso.poll = poll_falla
            proceso._poll_original = original_poll
            return proceso

        with patch.object(subprocesos.subprocess, "Popen", side_effect=envolver):
            with self.assertRaises(RuntimeError):
                ejecutar([sys.executable, "-c", "import time; time.sleep(10)"],
                         tope_segundos=5)

        self.assertTrue(capturados)
        for proceso in capturados:
            try:
                if hasattr(proceso, "_poll_original"):
                    proceso.poll = proceso._poll_original
                self.assertIsNotNone(proceso.poll(), "hijo sigue vivo tras excepción de programación")
            finally:
                try:
                    proceso.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    pass


@unittest.skipUnless(os.name == "nt", "SetDllDirectoryW es solo de Windows")
class PruebasCarpetaDllHeredada(unittest.TestCase):
    """El hijo no debe heredar la carpeta de DLL que fijó el cargador."""

    GUION = (
        "import ctypes\n"
        "from ctypes import wintypes\n"
        "nucleo = ctypes.WinDLL('kernel32')\n"
        "nucleo.GetDllDirectoryW.argtypes = [wintypes.DWORD, wintypes.LPWSTR]\n"
        "nucleo.GetDllDirectoryW.restype = wintypes.DWORD\n"
        "bufer = ctypes.create_unicode_buffer(32768)\n"
        "nucleo.GetDllDirectoryW(32768, bufer)\n"
        "print(bufer.value)\n"
    )

    def setUp(self):
        from ctypes import wintypes
        self._nucleo = ctypes.WinDLL("kernel32", use_last_error=True)
        self._nucleo.GetDllDirectoryW.argtypes = [wintypes.DWORD,
                                                  wintypes.LPWSTR]
        self._nucleo.GetDllDirectoryW.restype = wintypes.DWORD
        self._nucleo.SetDllDirectoryW.argtypes = [wintypes.LPCWSTR]
        self._nucleo.SetDllDirectoryW.restype = wintypes.BOOL
        self._anterior = self._leer()
        self.addCleanup(self._restaurar)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.carpeta = self._tmp.name

    def _leer(self):
        bufer = ctypes.create_unicode_buffer(32768)
        largo = self._nucleo.GetDllDirectoryW(32768, bufer)
        return bufer.value if largo > 0 else ""

    def _restaurar(self):
        self._nucleo.SetDllDirectoryW(self._anterior or None)

    def test_el_hijo_no_hereda_la_carpeta_y_al_salir_vuelve(self):
        self._nucleo.SetDllDirectoryW(self.carpeta)
        self.assertEqual(self.carpeta, self._leer())
        guion = os.path.join(self.carpeta, "lee.py")
        with open(guion, "w", encoding="utf-8") as archivo:
            archivo.write(self.GUION)
        with sin_carpeta_dll_heredada():
            salida = subprocess.run([sys.executable, guion],
                                    capture_output=True, text=True,
                                    encoding="utf-8")
        self.assertEqual("", salida.stdout.strip(),
                         "el hijo heredó la carpeta de DLL")
        self.assertEqual(self.carpeta, self._leer(),
                         "no se restauró la carpeta al salir")

    def test_restaura_aunque_el_bloque_lance(self):
        self._nucleo.SetDllDirectoryW(self.carpeta)
        with self.assertRaises(RuntimeError):
            with sin_carpeta_dll_heredada():
                self.assertEqual("", self._leer())
                raise RuntimeError("falla a propósito")
        self.assertEqual(self.carpeta, self._leer())

    def test_carpeta_vacia_no_toca_el_estado(self):
        nucleo = mock.Mock()
        nucleo.GetDllDirectoryW.side_effect = lambda tam, bufer: 0
        with mock.patch.object(ctypes, "WinDLL", return_value=nucleo):
            with sin_carpeta_dll_heredada():
                pass
        nucleo.SetDllDirectoryW.assert_not_called()

    def test_bloque_que_lanza_con_fallo_al_quitar_propaga(self):
        nucleo = mock.Mock()

        def leer(tam, bufer):
            bufer.value = self.carpeta
            return len(self.carpeta)

        nucleo.GetDllDirectoryW.side_effect = leer
        nucleo.SetDllDirectoryW.return_value = 0
        with mock.patch.object(ctypes, "WinDLL", return_value=nucleo):
            with self.assertRaises(OSError) as contexto:
                with sin_carpeta_dll_heredada():
                    raise OSError("x")
        self.assertEqual("x", str(contexto.exception))

    def test_bloque_que_lanza_con_quita_exitosa_propaga_y_restaura(self):
        nucleo = mock.Mock()

        def leer(tam, bufer):
            bufer.value = self.carpeta
            return len(self.carpeta)

        nucleo.GetDllDirectoryW.side_effect = leer
        nucleo.SetDllDirectoryW.return_value = 1
        with mock.patch.object(ctypes, "WinDLL", return_value=nucleo):
            with self.assertRaises(OSError) as contexto:
                with sin_carpeta_dll_heredada():
                    raise OSError("x")
        self.assertEqual("x", str(contexto.exception))
        nucleo.SetDllDirectoryW.assert_called_with(self.carpeta)


if __name__ == "__main__":
    unittest.main()
