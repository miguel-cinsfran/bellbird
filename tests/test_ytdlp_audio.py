from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from bellbird.downloads import ytdlp_bin


class PruebasDescargarAudio(unittest.TestCase):

    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.destino = Path(self.temporal.name) / "audio.webm"

    def tearDown(self):
        self.temporal.cleanup()

    def _respuesta(self, codigo=0):
        return mock.Mock(returncode=codigo)

    def _proceso(self, codigo=0, lineas=()):
        proceso = mock.Mock()
        proceso.stdout = lineas
        proceso.wait.return_value = codigo
        proceso.poll.return_value = codigo
        proceso.returncode = codigo
        proceso.kill = mock.Mock()
        return proceso

    def test_sin_ejecutable_no_inicia_subproceso(self):
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value=None), \
                mock.patch.object(ytdlp_bin.subprocess, "run") as ejecutar:
            self.assertFalse(ytdlp_bin.descargar_audio("A" * 11, self.destino))
        ejecutar.assert_not_called()

    def test_archivo_utilizable_devuelve_verdadero(self):
        def ejecutar(*_args, **_kwargs):
            self.destino.write_bytes(b"x" * ytdlp_bin.TAMANIO_MINIMO)
            return self._respuesta()
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen",
                                  side_effect=lambda *_a, **_k: (ejecutar(), self._proceso())[1]):
            self.assertTrue(ytdlp_bin.descargar_audio("A" * 11, self.destino))

    def test_archivo_ausente_devuelve_falso(self):
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen", return_value=self._proceso()):
            self.assertFalse(ytdlp_bin.descargar_audio("A" * 11, self.destino))

    def test_archivo_corto_devuelve_falso(self):
        self.destino.write_bytes(b"x" * (ytdlp_bin.TAMANIO_MINIMO - 1))
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen", return_value=self._proceso()):
            self.assertFalse(ytdlp_bin.descargar_audio("A" * 11, self.destino))

    def test_error_del_proceso_devuelve_falso(self):
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen", return_value=self._proceso(1)):
            self.assertFalse(ytdlp_bin.descargar_audio("A" * 11, self.destino))

    def test_timeout_no_se_propaga(self):
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen",
                                  side_effect=subprocess.TimeoutExpired("yt-dlp", 90)):
            self.assertFalse(ytdlp_bin.descargar_audio("A" * 11, self.destino))

    def test_invocacion_oculta_la_consola(self):
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen", return_value=self._proceso()) as ejecutar:
            ytdlp_bin.descargar_audio("A" * 11, self.destino)
        self.assertEqual(getattr(subprocess, "CREATE_NO_WINDOW", 0),
                         ejecutar.call_args.kwargs["creationflags"])

    def test_progreso_entrega_porcentajes_enteros(self):
        lineas = (
            "PROG 10 100 NA 1 1 audio.webm\n",
            "PROG 80 100 NA 1 1 audio.webm\n",
        )
        avisos = []
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen",
                                  return_value=self._proceso(1, lineas)):
            ytdlp_bin.descargar_audio("A" * 11, self.destino, avisos.append)
        self.assertEqual([10, 80], avisos)

    def test_argumentos_sin_quiet_con_progreso(self):
        # Verifica que no se use --quiet y sí --newline y --progress-template.
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen",
                                  return_value=self._proceso()) as crear:
            ytdlp_bin.descargar_audio("A" * 11, self.destino)
        argumentos = crear.call_args[0][0]
        self.assertNotIn("--quiet", argumentos)
        self.assertIn("--newline", argumentos)
        self.assertIn("--progress-template", argumentos)
        self.assertIn("--no-warnings", argumentos)

    def test_tope_corta_descarga_colgada_sin_salida(self):
        # Proceso que no imprime nada y no termina: debe cortarse por tope.
        class _SalidaBloqueada:
            def __iter__(self):
                return self

            def __next__(self):
                time.sleep(10)
                return "nunca termina"

        proceso = mock.Mock()
        proceso.stdout = _SalidaBloqueada()
        proceso.poll.return_value = None
        proceso.returncode = None
        proceso.kill = mock.Mock()
        # wait debe no bloquear indefinidamente; simulamos que tras kill termina
        def _espera(*_a, **_kw):
            return 0
        proceso.wait.side_effect = _espera
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen", return_value=proceso), \
                mock.patch("bellbird.core.subprocesos.terminar_arbol") as cortar:
            inicio = time.monotonic()
            resultado = ytdlp_bin.descargar_audio("A" * 11, self.destino, tope_segundos=1)
            duracion = time.monotonic() - inicio
        self.assertFalse(resultado)
        self.assertLess(duracion, 3)
        cortar.assert_called_once_with(proceso)


class PruebasRamasDescargarAudio(PruebasDescargarAudio):
    """Caracterización de las ramas que la cobertura del 16/10/2026 mostró
    sin ejecutar en descargar_audio: se fijan contra el código de hoy."""

    def test_vinculo_que_falla_no_impide_descarga(self):
        self.destino.write_bytes(b"x" * ytdlp_bin.TAMANIO_MINIMO)
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen", return_value=self._proceso()), \
                mock.patch("bellbird.core.subprocesos.vincular_a_la_app",
                           side_effect=RuntimeError("sin trabajo")):
            self.assertTrue(ytdlp_bin.descargar_audio("A" * 11, self.destino))

    def test_salida_nula_termina_sin_colgarse(self):
        proceso = self._proceso()
        proceso.stdout = None
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen", return_value=proceso):
            self.assertFalse(ytdlp_bin.descargar_audio("A" * 11, self.destino))

    def test_lector_que_falla_termina(self):
        class _SalidaRota:
            def __iter__(self):
                return self

            def __next__(self):
                raise ValueError("salida rota")

        proceso = self._proceso()
        proceso.stdout = _SalidaRota()
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen", return_value=proceso):
            self.assertFalse(ytdlp_bin.descargar_audio("A" * 11, self.destino))

    def test_terminar_que_falla_en_tope_igual_corta(self):
        class _SalidaBloqueada:
            def __iter__(self):
                return self

            def __next__(self):
                time.sleep(10)
                return "nunca termina"

        proceso = mock.Mock()
        proceso.stdout = _SalidaBloqueada()
        proceso.poll.return_value = None
        proceso.returncode = None
        proceso.wait.return_value = 0
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen", return_value=proceso), \
                mock.patch("bellbird.core.subprocesos.terminar_arbol",
                           side_effect=RuntimeError("no se pudo")) as cortar:
            inicio = time.monotonic()
            resultado = ytdlp_bin.descargar_audio("A" * 11, self.destino, tope_segundos=1)
            duracion = time.monotonic() - inicio
        self.assertFalse(resultado)
        self.assertLess(duracion, 3)
        cortar.assert_called_once_with(proceso)

    def test_espera_que_falla_en_tope_igual_corta(self):
        class _SalidaBloqueada:
            def __iter__(self):
                return self

            def __next__(self):
                time.sleep(10)
                return "nunca termina"

        proceso = mock.Mock()
        proceso.stdout = _SalidaBloqueada()
        proceso.poll.return_value = None
        proceso.returncode = None
        proceso.wait.side_effect = RuntimeError("wait roto")
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen", return_value=proceso), \
                mock.patch("bellbird.core.subprocesos.terminar_arbol"):
            inicio = time.monotonic()
            resultado = ytdlp_bin.descargar_audio("A" * 11, self.destino, tope_segundos=1)
            duracion = time.monotonic() - inicio
        self.assertFalse(resultado)
        self.assertLess(duracion, 3)

    def test_proceso_terminado_con_lector_muerto_sale(self):
        hilo = mock.Mock()
        hilo.is_alive.return_value = False
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen", return_value=self._proceso()), \
                mock.patch("threading.Thread", return_value=hilo):
            inicio = time.monotonic()
            resultado = ytdlp_bin.descargar_audio("A" * 11, self.destino)
            duracion = time.monotonic() - inicio
        self.assertFalse(resultado)
        self.assertLess(duracion, 5)

    def test_segunda_espera_corta_si_no_termina(self):
        proceso = mock.Mock()
        proceso.stdout = ()
        proceso.poll.return_value = None
        proceso.returncode = None
        proceso.wait.side_effect = RuntimeError("wait roto")
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen", return_value=proceso), \
                mock.patch("bellbird.core.subprocesos.terminar_arbol") as cortar:
            inicio = time.monotonic()
            resultado = ytdlp_bin.descargar_audio("A" * 11, self.destino, tope_segundos=1)
            duracion = time.monotonic() - inicio
        self.assertFalse(resultado)
        self.assertLess(duracion, 5)
        cortar.assert_called_once_with(proceso)

    def test_espera_final_que_falla_usa_returncode(self):
        self.destino.write_bytes(b"x" * ytdlp_bin.TAMANIO_MINIMO)
        proceso = self._proceso()
        proceso.wait.side_effect = RuntimeError("wait roto")
        proceso.returncode = 0
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen", return_value=proceso):
            self.assertTrue(ytdlp_bin.descargar_audio("A" * 11, self.destino))

    def test_espera_final_nula_usa_cero(self):
        self.destino.write_bytes(b"x" * ytdlp_bin.TAMANIO_MINIMO)
        proceso = mock.Mock()
        proceso.stdout = ()
        proceso.poll.return_value = 0
        proceso.wait.return_value = None
        proceso.returncode = None
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen", return_value=proceso):
            self.assertTrue(ytdlp_bin.descargar_audio("A" * 11, self.destino))

    def test_linea_sin_progreso_con_aviso_no_llama(self):
        avisos = []
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen",
                                   return_value=self._proceso(1, ("basura\n",))):
            ytdlp_bin.descargar_audio("A" * 11, self.destino, avisos.append)
        self.assertEqual([], avisos)

    def test_progreso_sin_aviso_no_falla(self):
        lineas = ("PROG 50 100 NA 1 1 audio.webm\n",)
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen",
                                   return_value=self._proceso(1, lineas)):
            self.assertFalse(ytdlp_bin.descargar_audio("A" * 11, self.destino))

    def test_cola_rota_igual_termina(self):
        import queue
        cola = mock.Mock()
        cola.put.side_effect = RuntimeError("cola rota")
        cola.get.side_effect = queue.Empty
        cola.empty.return_value = True
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen", return_value=self._proceso()), \
                mock.patch("queue.Queue", return_value=cola):
            inicio = time.monotonic()
            resultado = ytdlp_bin.descargar_audio("A" * 11, self.destino)
            duracion = time.monotonic() - inicio
        self.assertFalse(resultado)
        self.assertLess(duracion, 5)

    def test_segunda_espera_con_terminar_roto_igual_corta(self):
        proceso = mock.Mock()
        proceso.stdout = ()
        proceso.poll.return_value = None
        proceso.returncode = None
        proceso.wait.return_value = 0
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen", return_value=proceso), \
                mock.patch("bellbird.core.subprocesos.terminar_arbol",
                           side_effect=RuntimeError("no se pudo")):
            inicio = time.monotonic()
            resultado = ytdlp_bin.descargar_audio("A" * 11, self.destino, tope_segundos=1)
            duracion = time.monotonic() - inicio
        self.assertFalse(resultado)
        self.assertLess(duracion, 5)

    def test_lector_vivo_que_no_entrega_sigue_hasta_el_tope(self):
        hilo = mock.Mock()
        hilo.is_alive.return_value = True
        proceso = self._proceso()
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(ytdlp_bin.subprocess, "Popen", return_value=proceso), \
                mock.patch("threading.Thread", return_value=hilo), \
                mock.patch("bellbird.core.subprocesos.terminar_arbol") as cortar:
            inicio = time.monotonic()
            resultado = ytdlp_bin.descargar_audio("A" * 11, self.destino, tope_segundos=1)
            duracion = time.monotonic() - inicio
        self.assertFalse(resultado)
        self.assertLess(duracion, 5)
        cortar.assert_called_once_with(proceso)

    def test_ruta_que_falla_se_propaga(self):
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp",
                               side_effect=RuntimeError("ruta rota")):
            with self.assertRaises(RuntimeError):
                ytdlp_bin.descargar_audio("A" * 11, self.destino)

    def test_ejecucion_real_con_binario_que_falla(self):
        # Sin dobles de Popen: el envoltorio lanza un proceso de verdad
        # (python con argumentos de yt-dlp, que termina con error) y
        # devuelve falso sin dejar archivo.
        avisos = []
        with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value=sys.executable):
            inicio = time.monotonic()
            resultado = ytdlp_bin.descargar_audio(
                "A" * 11, self.destino, avisos.append, tope_segundos=30)
            duracion = time.monotonic() - inicio
        self.assertFalse(resultado)
        self.assertEqual([], avisos)
        self.assertFalse(self.destino.exists())
        self.assertLess(duracion, 30)


if __name__ == "__main__":
    unittest.main()
