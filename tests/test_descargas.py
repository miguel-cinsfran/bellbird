from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from tests.pseudo_prueba import con_pseudo
from bellbird.downloads import descargas
from bellbird.downloads.argumentos_ytdlp import recortar_url_registro
from bellbird.downloads.descargas import (
    GestorDescargas,
    INTERVALO_PROGRESO_S,
    analizar_url,
    argumentos_descarga,
    construir_outtmpl,
    debe_emitir_progreso,
    descargar,
    frase_aviso_descarga,
    gestor,
    reiniciar_gestor,
    tiene_ffmpeg,
    _vigilar_cancelacion,
)
from bellbird.downloads.restos_descarga import (
    limpiar_restos_descarga, nombre_base_descarga)


class TestDebeEmitirProgreso(unittest.TestCase):
    def test_primer_aviso(self): self.assertTrue(debe_emitir_progreso(None, 10, 0))
    def test_aviso_final(self): self.assertTrue(debe_emitir_progreso(10, 10.01, 100))
    def test_aviso_al_intervalo(self): self.assertTrue(debe_emitir_progreso(10, 10.5, 40))
    def test_aviso_dentro_del_intervalo(self): self.assertFalse(debe_emitir_progreso(10, 10.01, 40))


class TestRecortarUrlRegistro(unittest.TestCase):
    def test_deja_identificador_y_quita_parametros(self):
        url = "https://www.youtube.com/watch?v=abc123&list=secreta&token=oculto"
        self.assertEqual(recortar_url_registro(url), "abc123")


class TestFraseAvisoDescarga(unittest.TestCase):
    def test_completada_incluye_nombre(self):
        self.assertEqual(frase_aviso_descarga("completado", "", "archivo.mp4"),
                         "Descarga completada: archivo.mp4")

    def test_error_incluye_motivo(self):
        self.assertEqual(frase_aviso_descarga("error", "sin espacio", ""),
                         "Error en la descarga: sin espacio")

    def test_cancelada_no_agrega_mensaje(self):
        self.assertEqual(frase_aviso_descarga("cancelado", "motivo", "archivo"),
                         "Descarga cancelada")

    def test_progreso_no_se_anuncia(self):
        self.assertEqual(frase_aviso_descarga("descargando", "", "archivo"), "")


class TestConstruirOuttmpl(unittest.TestCase):
    def test_sin_enumerar(self):
        salida = construir_outtmpl({"carpeta": "/tmp/Descargas"}, False)
        self.assertNotIn("playlist_index", salida)
        self.assertIn("%(title)s", salida)
    def test_incluye_carpeta(self):
        self.assertEqual(Path(construir_outtmpl({"carpeta": "/tmp/Descargas"}, False)).parent,
                         Path("/tmp/Descargas"))
    def test_con_enumerar(self):
        self.assertIn("playlist_index", construir_outtmpl({"carpeta": "/tmp"}, True))

    def test_enumerar_no_deja_na_en_videos_sueltos(self):
        # «%(playlist_index)02d» a secas daba «NA - Título» fuera de una playlist.
        salida = Path(construir_outtmpl({"carpeta": "/tmp"}, True)).name
        self.assertTrue(salida.startswith("%(playlist_index&{:02d} - |)s"), salida)
        try:
            from yt_dlp import YoutubeDL
        except Exception:
            return
        ydl = YoutubeDL({"quiet": True})
        suelto = ydl.evaluate_outtmpl(salida, {"title": "T", "id": "x", "ext": "mp4"})
        en_lista = ydl.evaluate_outtmpl(
            salida, {"title": "T", "id": "x", "ext": "mp4", "playlist_index": 3})
        self.assertEqual(suelto, "T [x].mp4")
        self.assertEqual(en_lista, "03 - T [x].mp4")
    def test_carpeta_por_defecto(self): self.assertIn("Descargas", construir_outtmpl({}, False))
    def test_carpeta_windows(self): self.assertIn("Descargas", construir_outtmpl({"carpeta": r"C:\Users\foo\Descargas"}, False))


class TestAnalizarUrl(unittest.TestCase):
    def resultado(self, datos, codigo=0, error=""):
        return mock.Mock(stdout=json.dumps(datos), stderr=error, returncode=codigo)

    def test_video(self):
        with mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp"), \
                mock.patch.object(descargas.subprocess, "run", return_value=self.resultado({
                    "_type": "video", "id": "abc", "title": "Mi vídeo"})):
            res = analizar_url("https://example.com/v")
        self.assertEqual((res["tipo"], res["id"], res["cuenta"]), ("video", "abc", 1))

    def test_playlist(self):
        datos = {"_type": "playlist", "id": "PL", "title": "Lista", "entries": [{"id": "1"}]}
        with mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp"), \
                mock.patch.object(descargas.subprocess, "run", return_value=self.resultado(datos)):
            res = analizar_url("https://example.com/lista")
        self.assertEqual((res["tipo"], res["cuenta"]), ("playlist", 1))

    def test_sin_programa(self):
        with mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp", return_value=None):
            res = analizar_url("https://example.com/v")
        self.assertEqual(res["tipo"], "error")

    def test_fallo_del_programa(self):
        with mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp"), \
                mock.patch.object(descargas.subprocess, "run", return_value=self.resultado({}, 1, "URL inválida")):
            res = analizar_url("https://example.com/v")
        self.assertIn("inválida", res["mensaje"])

    def test_pide_un_unico_json_plano_con_tope(self):
        # --dump-json emitía un JSON por entrada en las playlists («Extra data»).
        with mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp"), \
                mock.patch.object(descargas.subprocess, "run",
                                  return_value=self.resultado({"id": "abc"})) as run:
            analizar_url("https://example.com/lista")
        args = run.call_args.args[0]
        self.assertIn("-J", args)
        self.assertIn("--flat-playlist", args)
        self.assertNotIn("--dump-json", args)
        self.assertEqual(run.call_args.kwargs["timeout"], descargas.TIEMPO_ESPERA_ANALISIS)

    def test_tope_agotado_es_error_y_no_revienta(self):
        with mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp"), \
                mock.patch.object(descargas.subprocess, "run",
                                  side_effect=descargas.subprocess.TimeoutExpired("yt-dlp", 60)):
            res = analizar_url("https://example.com/v")
        self.assertEqual(res["tipo"], "error")

    def test_respuesta_vacia_dice_enlace_vacio(self):
        with mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp"), \
                mock.patch.object(descargas.subprocess, "run", return_value=self.resultado({})):
            res = analizar_url("https://example.com/vacia")
        self.assertEqual(res["mensaje"], "Enlace vacío")


class TestArgumentosDescarga(unittest.TestCase):
    def opciones(self, formato): return {"formato": formato, "bitrate": 256, "carpeta": "/tmp"}
    def test_mp3_lleva_conversion(self):
        args = argumentos_descarga("https://example.com/v", self.opciones("mp3"), False)
        self.assertIn("-x", args); self.assertIn("mp3", args); self.assertIn("256K", args)
    def test_mp4_no_lleva_conversion(self):
        args = argumentos_descarga("https://example.com/v", self.opciones("mp4"), False)
        self.assertNotIn("-x", args); self.assertNotIn("--audio-format", args)
        self.assertNotIn("--audio-quality", args)
    def test_pasa_resolucion_y_bitrate_a_la_linea(self):
        args = argumentos_descarga(
            "url", {"formato": "mp4", "bitrate": 192,
                    "resolucion": 720, "carpeta": "/tmp"}, False)
        self.assertTrue(any("res:720" in a for a in args), args)
        args = argumentos_descarga(
            "url", {"formato": "mp3", "bitrate": 320,
                    "resolucion": 0, "carpeta": "/tmp"}, False)
        self.assertIn("320K", args)
    def test_no_lleva_quiet(self):
        self.assertNotIn("--quiet", argumentos_descarga("https://example.com/v", self.opciones("mp4"), False))
    def test_url_al_final(self):
        self.assertEqual(argumentos_descarga("-url", self.opciones("mp4"), False)[-2:],
                         ["--", "-url"])
    def test_lleva_plantilla_y_salida(self):
        args = argumentos_descarga("url", self.opciones("mp4"), True)
        self.assertIn("--progress-template", args); self.assertIn("-o", args)

    def test_pide_plantilla_de_descarga_y_de_postproceso(self):
        args = argumentos_descarga("url", self.opciones("mp4"), False)
        self.assertEqual(args.count("--progress-template"), 2)

    def test_fuerza_utf8_en_la_salida(self):
        args = argumentos_descarga("url", self.opciones("mp4"), False)
        indice = args.index("--encoding")
        self.assertEqual(args[indice + 1], "utf-8")
    def test_usa_ruta_de_ffmpeg_recibida(self):
        args = argumentos_descarga("url", self.opciones("mp3"), False,
                                   r"C:\ffmpeg")
        indice = args.index("--ffmpeg-location")
        self.assertEqual(args[indice:indice + 2], ["--ffmpeg-location", r"C:\ffmpeg"])

    def test_sin_ffmpeg_resuelto_no_agrega_ffmpeg(self):
        with mock.patch.object(descargas.ffmpeg_bin, "ruta_ffmpeg", return_value=None):
            args = argumentos_descarga("url", self.opciones("mp3"), False)
        self.assertNotIn("--ffmpeg-location", args)

    def test_usa_el_resolvedor_unico_de_ffmpeg(self):
        with mock.patch.object(descargas.ffmpeg_bin, "ruta_ffmpeg",
                               return_value=r"C:\app\ffmpeg.exe"):
            args = argumentos_descarga("url", self.opciones("mp3"), False)
        indice = args.index("--ffmpeg-location")
        self.assertEqual(args[indice + 1], r"C:\app\ffmpeg.exe")

    def test_enlace_de_video_con_lista_baja_solo_el_video(self):
        args = argumentos_descarga("https://example.com/watch?v=X&list=Y",
                                   self.opciones("mp4"), False)
        self.assertIn("--no-playlist", args)
        self.assertLess(args.index("--no-playlist"), args.index("--"))

    def test_pide_la_ruta_final_sin_perder_el_progreso(self):
        # --print implica --quiet, que apaga el progreso: --progress lo recupera.
        args = argumentos_descarga("url", self.opciones("mp4"), False)
        indice = args.index("--print")
        self.assertEqual(args[indice + 1],
                         f"after_move:{descargas.PREFIJO_RUTA_FINAL} %(filepath)s")
        self.assertIn("--progress", args)
        self.assertIn("--progress-template", args)


class TestDescargar(unittest.TestCase):
    def proceso(self, lineas):
        proceso = mock.MagicMock()
        proceso.returncode = 0
        proceso.poll.return_value = 0
        proceso.stdout.readline.side_effect = [*lineas, ""]
        return proceso

    def preparar(self, proceso):
        return mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp"), \
            mock.patch.object(descargas, "tiene_ffmpeg", return_value=True), \
            mock.patch.object(descargas.subprocess, "Popen", return_value=proceso)

    def test_pasa_progreso_al_callback(self):
        proceso = self.proceso(["PROGD 5 10 NA 2 3 NA NA nombre con espacios.mp4\n"])
        progresos = []; estados = []
        with self.preparar(proceso)[0], self.preparar(proceso)[1], self.preparar(proceso)[2]:
            descargar("url", {"formato": "mp4"}, lambda *a: progresos.append(a),
                      lambda *a: estados.append(a), threading.Event())
        self.assertEqual(progresos, [(50.0, 2.0, 3, "nombre con espacios.mp4")])
        self.assertEqual(estados[-1], ("completado", ""))

    def test_la_ruta_final_reemplaza_el_nombre_del_fragmento(self):
        proceso = self.proceso([
            "PROGD 5 10 NA 2 3 NA NA C:/d/video [x].f140.m4a\n",
            f"{descargas.PREFIJO_RUTA_FINAL} C:/d/video [x].mp4\n",
        ])
        progresos = []; estados = []
        with self.preparar(proceso)[0], self.preparar(proceso)[1], self.preparar(proceso)[2]:
            descargar("url", {"formato": "mp4"}, lambda *a: progresos.append(a),
                      lambda *a: estados.append(a), threading.Event())
        self.assertEqual(progresos[-1], (100.0, None, None, "video [x].mp4"))
        self.assertEqual(estados[-1], ("completado", ""))

    def test_cancelar_borra_los_restos_de_la_carpeta(self):
        with tempfile.TemporaryDirectory() as carpeta:
            base = Path(carpeta) / "Vídeo [abc]"
            restos = [base.with_name(base.name + ".f140.m4a.part"),
                      base.with_name(base.name + ".f137.mp4"),
                      base.with_name(base.name + ".mp4.ytdl")]
            intactos = [base.with_name(base.name + ".mp4"),
                        Path(carpeta) / "Otro [zzz].mp4.part"]
            for ruta in restos + intactos:
                ruta.write_bytes(b"x")
            proceso = self.proceso([
                f"PROGD 5 10 NA 2 3 NA NA {base}.f140.m4a\n",
                f"PROGD 6 10 NA 2 3 NA NA {base}.f140.m4a\n",
            ])
            evento = threading.Event(); estados = []
            with self.preparar(proceso)[0], self.preparar(proceso)[1], self.preparar(proceso)[2]:
                descargar("url", {"formato": "mp4", "carpeta": carpeta},
                          lambda *a: evento.set(), lambda *a: estados.append(a), evento)
            self.assertEqual(estados[-1], ("cancelado", "Descarga cancelada"))
            self.assertFalse(any(ruta.exists() for ruta in restos))
            self.assertTrue(all(ruta.exists() for ruta in intactos))

    def test_ignora_lineas_no_progreso(self):
        proceso = self.proceso(["[youtube] Extracting URL\n"])
        callback = mock.Mock()
        with self.preparar(proceso)[0], self.preparar(proceso)[1], self.preparar(proceso)[2]:
            descargar("url", {"formato": "mp4"}, callback, lambda *a: None, threading.Event())
        callback.assert_not_called()

    def test_frena_progresos_seguidos(self):
        lineas = ["PROGD 5 10 NA 2 3 NA NA nombre.mp4\n"] * 20
        proceso = self.proceso(lineas)
        progreso = mock.Mock()
        with self.preparar(proceso)[0], self.preparar(proceso)[1], \
                self.preparar(proceso)[2], \
                mock.patch.object(descargas.time, "monotonic", return_value=10):
            descargar("url", {"formato": "mp4"}, progreso, lambda *a: None,
                      threading.Event())
        self.assertLess(progreso.call_count, len(lineas))

    def test_cancelar_mata_el_proceso(self):
        proceso = self.proceso([]); evento = threading.Event(); evento.set(); estados = []
        with self.preparar(proceso)[0], self.preparar(proceso)[1], self.preparar(proceso)[2]:
            descargar("url", {"formato": "mp4"}, lambda *a: None,
                      lambda *a: estados.append(a), evento)
        self.assertEqual(estados[-1], ("cancelado", "Descarga cancelada"))
        proceso.kill.assert_called_once()

    def test_cancelar_durante_progreso_mata_el_proceso(self):
        proceso = self.proceso([
            "PROGD 5 10 NA 2 3 NA NA nombre.mp4\n",
            "PROGD 6 10 NA 2 3 NA NA nombre.mp4\n",
        ])
        evento = threading.Event(); estados = []

        def progreso(*args):
            evento.set()

        with self.preparar(proceso)[0], self.preparar(proceso)[1], self.preparar(proceso)[2]:
            descargar("url", {"formato": "mp4"}, progreso,
                      lambda *a: estados.append(a), evento)
        self.assertEqual(estados[-1], ("cancelado", "Descarga cancelada"))
        proceso.kill.assert_called_once()

    def test_cancelar_sin_nuevas_lineas_mata_e_informa(self):
        class ProcesoBloqueado:
            def __init__(self):
                self.inicio_lectura = threading.Event()
                self.terminado = threading.Event()
                self.codigo = None
                self.kill_count = 0
                self.stdout = self

            def poll(self):
                return self.codigo

            def kill(self):
                self.kill_count += 1
                self.codigo = -9
                self.terminado.set()

            def wait(self):
                self.terminado.wait(0.5)
                return self.codigo

            def readline(self):
                self.inicio_lectura.set()
                self.terminado.wait(0.5)
                return ""

        proceso = ProcesoBloqueado()
        evento = threading.Event(); estados = []
        with self.preparar(proceso)[0], self.preparar(proceso)[1], \
                self.preparar(proceso)[2]:
            hilo = threading.Thread(
                target=descargar,
                args=("url", {"formato": "mp4"}, lambda *a: None,
                      lambda *a: estados.append(a), evento),
            )
            hilo.start()
            self.assertTrue(proceso.inicio_lectura.wait(1))
            evento.set()
            hilo.join(1)
        self.assertFalse(hilo.is_alive())
        self.assertEqual(estados[-1], ("cancelado", "Descarga cancelada"))
        self.assertEqual(proceso.kill_count, 1)

    def test_vigilante_mata_al_cancelar(self):
        proceso = mock.Mock()
        proceso.poll.return_value = None
        evento = threading.Event()
        evento.set()
        self.assertTrue(_vigilar_cancelacion(proceso, evento, 0.01))
        proceso.kill.assert_called_once()

    def test_vigilante_no_mata_si_termina(self):
        proceso = mock.Mock()
        proceso.poll.return_value = 0
        self.assertFalse(_vigilar_cancelacion(proceso, threading.Event(), 0.01))
        proceso.kill.assert_not_called()

    def test_cancelar_despues_de_terminar_marca_estado(self):
        proceso = self.proceso([]); evento = threading.Event(); estados = []
        proceso.wait.side_effect = evento.set
        with self.preparar(proceso)[0], self.preparar(proceso)[1], self.preparar(proceso)[2]:
            descargar("url", {"formato": "mp4"}, lambda *a: None,
                      lambda *a: estados.append(a), evento)
        self.assertEqual(estados[-1], ("cancelado", "Descarga cancelada"))
        proceso.kill.assert_not_called()

    def test_codigo_no_cero_es_error(self):
        proceso = self.proceso([]); proceso.returncode = 2; estados = []
        with self.preparar(proceso)[0], self.preparar(proceso)[1], self.preparar(proceso)[2]:
            descargar("url", {"formato": "mp4"}, lambda *a: None,
                      lambda *a: estados.append(a), threading.Event())
        self.assertEqual(estados[-1][0], "error")

    def test_error_de_edad_dice_el_motivo_y_lo_registra(self):
        guion = (
            "import sys\n"
            "sys.stdout.write(\n"
            "    'ERROR: [youtube] O2yixU7XjGU: Sign in to confirm your age. '\n"
            "    'Use --cookies-from-browser.\\n')\n"
            "sys.stdout.flush()\n"
            "sys.exit(1)\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            falso = Path(tmp) / "falso_ytdlp.py"
            falso.write_text(guion, encoding="utf-8")
            estados = []
            with mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp",
                                    return_value=sys.executable), \
                    mock.patch.object(descargas, "tiene_ffmpeg",
                                       return_value=True), \
                    mock.patch.object(descargas, "argumentos_descarga",
                                       return_value=[str(falso)]), \
                    self.assertLogs(descargas.logger,
                                     level="WARNING") as registro:
                descargar("url", {"formato": "mp4", "carpeta": tmp},
                          lambda *a: None, lambda *a: estados.append(a),
                          threading.Event())
        self.assertEqual(
            estados[-1],
            ("error", "El vídeo tiene restricción de edad y YouTube pide "
             "iniciar sesión."))
        self.assertTrue(any("O2yixU7XjGU" in linea and "código 1" in linea
                            for linea in registro.output))

    def test_lista_avisa_indice_total_y_ruta(self):
        proceso = self.proceso([
            "PROGD 5 10 NA 2 3 1 2 C:/d/a.mp4\n",
            f"{descargas.PREFIJO_RUTA_FINAL} C:/d/a.mp4\n",
        ])
        detalles = []
        with self.preparar(proceso)[0], self.preparar(proceso)[1], self.preparar(proceso)[2]:
            descargar("url", {"formato": "mp4"}, lambda *a: None,
                      lambda *a: None, threading.Event(),
                      al_detalle=detalles.append)
        self.assertIn({"procesando": False, "indice": 1, "total": 2}, detalles)
        self.assertIn({"ruta": "C:/d/a.mp4"}, detalles)

    def test_procesando_avisa_sin_convertirlo_en_parcial(self):
        proceso = self.proceso([
            "PROC started MoveFiles\n",
            "PROC started ExtractAudio\n",
        ])
        detalles = []; estados = []
        with self.preparar(proceso)[0], self.preparar(proceso)[1], self.preparar(proceso)[2]:
            descargar("url", {"formato": "mp4"}, lambda *a: None,
                      lambda *a: estados.append(a), threading.Event(),
                      al_detalle=detalles.append)
        self.assertEqual(detalles, [{"procesando": True}])
        self.assertEqual(estados[-1], ("completado", ""))

    def test_error_tras_un_video_de_lista_es_parcial(self):
        proceso = self.proceso([
            "PROGD 5 10 NA 2 3 1 2 C:/d/a.mp4\n",
            f"{descargas.PREFIJO_RUTA_FINAL} C:/d/a.mp4\n",
            "ERROR: [youtube] abc: Private video.\n",
        ])
        proceso.returncode = 1
        estados = []
        with self.preparar(proceso)[0], self.preparar(proceso)[1], self.preparar(proceso)[2]:
            descargar("url", {"formato": "mp4"}, lambda *a: None,
                      lambda *a: estados.append(a), threading.Event())
        self.assertEqual(estados[-1], ("parcial", "1 de 2 vídeos"))

    def test_completado_de_lista_cuenta_los_videos(self):
        proceso = self.proceso([
            "PROGD 5 10 NA 2 3 1 2 C:/d/a.mp4\n",
            f"{descargas.PREFIJO_RUTA_FINAL} C:/d/a.mp4\n",
            "PROGD 5 10 NA 2 3 2 2 C:/d/b.mp4\n",
            f"{descargas.PREFIJO_RUTA_FINAL} C:/d/b.mp4\n",
        ])
        estados = []
        with self.preparar(proceso)[0], self.preparar(proceso)[1], self.preparar(proceso)[2]:
            descargar("url", {"formato": "mp4"}, lambda *a: None,
                      lambda *a: estados.append(a), threading.Event())
        self.assertEqual(estados[-1], ("completado", "2 vídeos"))

    def test_sin_programa_es_error(self):
        estados = []
        with mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp", return_value=None):
            descargar("url", {}, lambda *a: None, lambda *a: estados.append(a), threading.Event())
        self.assertEqual(estados[-1][0], "error")


class TestMatarArbol(unittest.TestCase):
    """kill() solo mata a yt-dlp; el ffmpeg hijo seguía uniendo audio y vídeo."""

    def test_en_windows_baja_el_arbol_con_taskkill_y_luego_kill(self):
        proceso = mock.Mock(pid=1234)
        with mock.patch.object(descargas.os, "name", "nt"), \
                mock.patch.object(descargas.subprocess, "run") as run:
            descargas._matar_arbol(proceso)
        self.assertEqual(run.call_args.args[0],
                         ["taskkill", "/T", "/F", "/PID", "1234"])
        proceso.kill.assert_called_once()

    def test_si_taskkill_falla_igual_hace_kill(self):
        proceso = mock.Mock(pid=1234)
        with mock.patch.object(descargas.os, "name", "nt"), \
                mock.patch.object(descargas.subprocess, "run", side_effect=OSError("no")):
            descargas._matar_arbol(proceso)
        proceso.kill.assert_called_once()

    def test_sin_pid_real_no_lanza_taskkill(self):
        proceso = mock.Mock()   # pid es un Mock, como en las demás pruebas
        with mock.patch.object(descargas.subprocess, "run") as run:
            descargas._matar_arbol(proceso)
        run.assert_not_called()
        proceso.kill.assert_called_once()


class TestLimpiarRestos(unittest.TestCase):

    def test_nombre_base_quita_fragmento_part_y_extension(self):
        for nombre in ("C:/d/Título [id].f140.m4a.part", "Título [id].f137.mp4",
                       "Título [id].mp4.ytdl", "Título [id].mp4", "Título [id].mp4.part"):
            self.assertEqual(nombre_base_descarga(nombre), "Título [id]", nombre)

    def test_sin_nombre_no_borra_nada(self):
        with tempfile.TemporaryDirectory() as carpeta:
            (Path(carpeta) / "a.part").write_bytes(b"x")
            self.assertEqual(limpiar_restos_descarga(carpeta, ""), [])
            self.assertTrue((Path(carpeta) / "a.part").exists())

    def test_borra_solo_temporales_de_esa_descarga(self):
        with tempfile.TemporaryDirectory() as carpeta:
            nombres = ["V [id].f140.m4a.part", "V [id].f137.mp4", "V [id].mp4.ytdl",
                       "V [id].mp4.part", "V [id].mp4", "V [id].jpg", "W [id].mp4.part"]
            for nombre in nombres:
                (Path(carpeta) / nombre).write_bytes(b"x")
            borrados = limpiar_restos_descarga(carpeta, "V [id].f140.m4a")
            self.assertEqual(sorted(borrados), ["V [id].f137.mp4", "V [id].f140.m4a.part",
                                                "V [id].mp4.part", "V [id].mp4.ytdl"])
            self.assertEqual(sorted(r.name for r in Path(carpeta).iterdir()),
                             ["V [id].jpg", "V [id].mp4", "W [id].mp4.part"])

    def test_carpeta_inexistente_no_revienta(self):
        self.assertEqual(limpiar_restos_descarga("/no/existe", "a.mp4"), [])


class TestGestorDescargas(unittest.TestCase):
    def opciones(self): return {"formato": "mp4", "bitrate": 192, "carpeta": "/tmp"}

    def test_cancelar_durante_el_analisis_no_lanza_la_descarga(self):
        gestor = GestorDescargas(self.opciones())
        seguir = threading.Event()
        estados = []
        terminado = threading.Event()

        def analizar(_url):
            seguir.wait(1)
            return {"tipo": "video"}

        def estado(_id, valor, _mensaje):
            estados.append(valor)
            terminado.set()

        with mock.patch.object(descargas, "analizar_url", side_effect=analizar), \
                mock.patch.object(descargas, "descargar") as descargar_mock:
            item_id = gestor.encolar("url", lambda *a: None, estado)
            gestor.cancelar(item_id)
            seguir.set()
            self.assertTrue(terminado.wait(1))
        descargar_mock.assert_not_called()
        self.assertEqual(estados, ["cancelado"])

    def test_el_item_lleva_la_carpeta_elegida_al_encolar(self):
        gestor = GestorDescargas(self.opciones())
        with mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp", return_value=None):
            id_ = gestor.encolar("url", lambda *a: None, lambda *a: None)
        self.assertEqual(gestor.obtener(id_).carpeta, "/tmp")
    def test_encolar_almacena_item(self):
        gestor = GestorDescargas(self.opciones())
        with mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp", return_value=None):
            id_ = gestor.encolar("url", lambda *a: None, lambda *a: None)
        self.assertEqual(gestor.obtener(id_).url, "url")
    def test_cancelar_marca_evento(self):
        gestor = GestorDescargas(self.opciones())
        with mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp", return_value=None):
            id_ = gestor.encolar("url", lambda *a: None, lambda *a: None)
        gestor.cancelar(id_); self.assertTrue(gestor._eventos[id_].is_set())
    def test_cancelar_inexistente(self): GestorDescargas(self.opciones()).cancelar("no-existe")
    def test_obtener_inexistente(self): self.assertIsNone(GestorDescargas(self.opciones()).obtener("no-existe"))
    def test_set_opciones(self):
        gestor = GestorDescargas(self.opciones()); gestor.set_opciones({"formato": "mp3"})
        self.assertEqual(gestor._opciones["formato"], "mp3")

    def test_encolar_devuelve_id_antes_de_analizar(self):
        gestor = GestorDescargas(self.opciones())
        analisis_iniciado = threading.Event()
        terminar_analisis = threading.Event()
        progresos = []

        def analizar(_url):
            analisis_iniciado.set()
            terminar_analisis.wait(1)
            return {"tipo": "video", "titulo": "Título conocido"}

        with mock.patch.object(descargas, "analizar_url", side_effect=analizar), \
                mock.patch.object(descargas, "descargar"):
            item_id = gestor.encolar("url", lambda *args: progresos.append(args),
                                     lambda *args: None)
            self.assertEqual(gestor.obtener(item_id).nombre, "url")
            self.assertTrue(analisis_iniciado.wait(1))
            terminar_analisis.set()
            for _ in range(100):
                if progresos:
                    break
                threading.Event().wait(0.01)

        self.assertEqual(progresos[0][4], "Título conocido")

    def test_el_nombre_de_la_lista_no_lo_pisa_cada_video(self):
        gestor = GestorDescargas(self.opciones())
        hecho = threading.Event()

        def descargar_falsa(_url, _opciones, progreso, estado, _cancelar,
                            _detalle=None):
            progreso(0, "", "", "vídeo suelto")
            estado("completado", "")
            hecho.set()

        with mock.patch.object(
                descargas, "analizar_url",
                return_value={"tipo": "playlist", "titulo": "Lista",
                              "cuenta": 2}), \
                mock.patch.object(descargas, "descargar",
                                  side_effect=descargar_falsa):
            item_id = gestor.encolar("url", lambda *a: None, lambda *a: None)
            self.assertTrue(hecho.wait(1))
        self.assertEqual(gestor.obtener(item_id).nombre, "Lista")

    def test_el_detalle_de_cada_video_llega_al_item(self):
        gestor_prueba = GestorDescargas(self.opciones())
        proceso = mock.MagicMock()
        proceso.returncode = 0
        proceso.poll.return_value = 0
        proceso.stdout.readline.side_effect = [
            "PROGD 5 10 NA 2 3 1 2 C:/d/a.mp4\n",
            f"{descargas.PREFIJO_RUTA_FINAL} C:/d/a.mp4\n",
            "PROGD 5 10 NA 2 3 2 2 C:/d/b.mp4\n",
            f"{descargas.PREFIJO_RUTA_FINAL} C:/d/b.mp4\n",
            "",
        ]
        finales = {}
        terminado = threading.Event()
        total_al_arrancar = []

        def progreso(item_id, *_args):
            # El total ya está puesto por analizar_url antes de la primera
            # línea de yt-dlp: lo lee el detalle después, no antes.
            if not total_al_arrancar:
                total_al_arrancar.append(gestor_prueba.obtener(item_id).total)

        def estado(item_id, valor, mensaje):
            finales[item_id] = (valor, mensaje)
            if valor in ("completado", "parcial", "cancelado", "error"):
                terminado.set()

        with mock.patch.object(
                descargas, "analizar_url",
                return_value={"tipo": "playlist", "titulo": "Lista",
                              "cuenta": 2}), \
                mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp",
                                  return_value="yt-dlp"), \
                mock.patch.object(descargas, "tiene_ffmpeg",
                                  return_value=True), \
                mock.patch.object(descargas.subprocess, "Popen",
                                  return_value=proceso):
            item_id = gestor_prueba.encolar("url", progreso, estado)
            self.assertTrue(terminado.wait(5))
        item = gestor_prueba.obtener(item_id)
        self.assertEqual(total_al_arrancar, [2])
        self.assertEqual(item.rutas, ["C:/d/a.mp4", "C:/d/b.mp4"])
        self.assertEqual((item.total, item.indice), (2, 2))
        self.assertEqual(item.nombre, "Lista")
        self.assertEqual(finales[item_id], ("completado", "2 vídeos"))


def _esperar_hasta(condicion, tiempo=5.0):
    """Espera corta por una condición de hilos, sin sleeps fijos largos."""
    limite = time.time() + tiempo
    while time.time() < limite:
        if condicion():
            return True
        threading.Event().wait(0.01)
    return condicion()


class TestGestorDescargasLimite(unittest.TestCase):
    """La cola es una cola de verdad: dos a la vez, en orden de encolado."""

    def opciones(self): return {"formato": "mp4", "bitrate": 192, "carpeta": "/tmp"}

    def _registrador(self, finales):
        candado = threading.Lock()

        def estado(item_id, estado, _mensaje):
            with candado:
                finales[item_id] = estado
        return estado

    def test_como_mucho_dos_descargas_a_la_vez(self):
        gestor = GestorDescargas(self.opciones())
        liberar = threading.Event()
        candado = threading.Lock()
        dentro = 0
        maximo = 0
        entradas = []
        finales = {}

        def descargar_simulada(_url, _opciones, _progreso, estado, _cancelar, _detalle=None):
            nonlocal dentro, maximo
            with candado:
                dentro += 1
                maximo = max(maximo, dentro)
                entradas.append(_url)
            try:
                liberar.wait(5)
            finally:
                with candado:
                    dentro -= 1
            estado("completado", "")

        with mock.patch.object(descargas, "analizar_url",
                               return_value={"tipo": "video"}), \
                mock.patch.object(descargas, "descargar",
                                  side_effect=descargar_simulada):
            ids = [gestor.encolar(f"url-{i}", lambda *a: None,
                                  self._registrador(finales)) for i in range(5)]
            self.assertTrue(_esperar_hasta(lambda: len(entradas) >= 2))
            with candado:
                self.assertEqual(len(entradas), 2)
                self.assertLessEqual(maximo, 2)
            liberar.set()
            self.assertTrue(_esperar_hasta(lambda: len(finales) == 5, tiempo=10))
        with candado:
            self.assertEqual(maximo, 2)
        self.assertEqual([finales[i] for i in ids], ["completado"] * 5)
        self.assertTrue(all(gestor.obtener(i).estado == "completado" for i in ids))

    def test_el_orden_de_entrada_es_el_de_encolado(self):
        gestor = GestorDescargas(self.opciones())
        candado = threading.Lock()
        entradas = []
        finales = {}

        def descargar_simulada(url, _opciones, _progreso, estado, _cancelar, _detalle=None):
            with candado:
                entradas.append(url)
            estado("completado", "")

        with mock.patch.object(descargas, "analizar_url",
                               return_value={"tipo": "video"}), \
                mock.patch.object(descargas, "descargar",
                                  side_effect=descargar_simulada):
            urls = [f"url-{i}" for i in range(5)]
            for url in urls:
                gestor.encolar(url, lambda *a: None, self._registrador(finales))
            self.assertTrue(_esperar_hasta(lambda: len(finales) == 5, tiempo=10))
        self.assertEqual(entradas, urls)

    def test_cancelado_mientras_espera_no_lanza_nada(self):
        gestor = GestorDescargas(self.opciones())
        liberar = threading.Event()
        candado = threading.Lock()
        entradas = []
        finales = {}

        def descargar_simulada(url, _opciones, _progreso, estado, _cancelar, _detalle=None):
            with candado:
                entradas.append(url)
            liberar.wait(5)
            estado("completado", "")

        with mock.patch.object(descargas, "analizar_url",
                               return_value={"tipo": "video"}) as analizar_mock, \
                mock.patch.object(descargas, "descargar",
                                  side_effect=descargar_simulada):
            primero = gestor.encolar("url-0", lambda *a: None,
                                     self._registrador(finales))
            segundo = gestor.encolar("url-1", lambda *a: None,
                                     self._registrador(finales))
            self.assertTrue(_esperar_hasta(lambda: len(entradas) == 2))
            tercero = gestor.encolar("url-2", lambda *a: None,
                                     self._registrador(finales))
            gestor.cancelar(tercero)
            self.assertTrue(_esperar_hasta(lambda: finales.get(tercero) == "cancelado"))
            # El cancelado no lanzó nada y no le quitó el turno a los demás.
            self.assertEqual(analizar_mock.call_count, 2)
            self.assertEqual(list(entradas), ["url-0", "url-1"])
            cuarto = gestor.encolar("url-3", lambda *a: None,
                                    self._registrador(finales))
            liberar.set()
            self.assertTrue(_esperar_hasta(
                lambda: len([i for i in (primero, segundo, cuarto)
                             if finales.get(i) == "completado"]) == 3, tiempo=10))
        self.assertEqual(finales[tercero], "cancelado")
        self.assertEqual(gestor.obtener(tercero).estado, "cancelado")
        self.assertIn("url-3", list(entradas))

    def test_si_descargar_falla_el_turno_se_libera(self):
        gestor = GestorDescargas(self.opciones())
        candado = threading.Lock()
        entradas = []
        finales = {}

        def descargar_simulada(url, _opciones, _progreso, estado, _cancelar, _detalle=None):
            with candado:
                entradas.append(url)
            if url == "url-falla":
                raise RuntimeError("falla simulada")
            estado("completado", "")

        with mock.patch.object(descargas, "analizar_url",
                               return_value={"tipo": "video"}), \
                mock.patch.object(descargas, "descargar",
                                  side_effect=descargar_simulada):
            fallido = gestor.encolar("url-falla", lambda *a: None,
                                     self._registrador(finales))
            ok1 = gestor.encolar("url-ok-1", lambda *a: None,
                                 self._registrador(finales))
            ok2 = gestor.encolar("url-ok-2", lambda *a: None,
                                 self._registrador(finales))
            self.assertTrue(_esperar_hasta(lambda: len(finales) == 3, tiempo=10))
        self.assertEqual(sorted(entradas), ["url-falla", "url-ok-1", "url-ok-2"])
        self.assertEqual(finales[fallido], "error")
        self.assertEqual(finales[ok1], "completado")
        self.assertEqual(finales[ok2], "completado")

    def test_encolado_conserva_las_opciones_vigentes_al_encolar(self):
        # Con los dos turnos ocupados, cambiar las opciones no afecta al
        # ítem que espera: descarga con las primeras y su carpeta coincide.
        primeras = {"formato": "mp3", "bitrate": 192, "carpeta": "/tmp/primera",
                    "enumerar": False}
        segundas = {"formato": "mp4", "bitrate": 256, "carpeta": "/tmp/segunda",
                    "enumerar": True}
        gestor = GestorDescargas(dict(primeras))
        liberar = threading.Event()
        candado = threading.Lock()
        entradas = []
        recibidas = {}
        finales = {}

        def descargar_simulada(url, opciones, _progreso, estado, _cancelar, _detalle=None):
            with candado:
                entradas.append(url)
                recibidas[url] = dict(opciones)
            liberar.wait(5)
            estado("completado", "")

        with mock.patch.object(descargas, "analizar_url",
                               return_value={"tipo": "video"}), \
                mock.patch.object(descargas, "descargar",
                                  side_effect=descargar_simulada):
            gestor.encolar("url-0", lambda *a: None, self._registrador(finales))
            gestor.encolar("url-1", lambda *a: None, self._registrador(finales))
            self.assertTrue(_esperar_hasta(lambda: len(entradas) >= 2))
            tercero = gestor.encolar("url-2", lambda *a: None,
                                     self._registrador(finales))
            gestor.set_opciones(segundas)
            liberar.set()
            self.assertTrue(_esperar_hasta(lambda: len(finales) == 3, tiempo=10))
        self.assertEqual(recibidas["url-2"], primeras)
        self.assertEqual(gestor.obtener(tercero).carpeta, recibidas["url-2"]["carpeta"])

    def test_el_turno_respeta_la_fila_aunque_arranquen_al_reves(self):
        # Sin la fila por _orden, el semáforo atiende en orden de arranque.
        gestor = GestorDescargas(self.opciones())
        hilos = []
        candado = threading.Lock()
        entradas = []
        finales = {}
        liberar = threading.Event()

        def crear_sin_arrancar(destino, nombre, *args, **kwargs):
            # El encolar arranca lo que crear_hilo devuelve: se le entrega
            # un falso con start mudo y el hilo real queda guardado sin
            # arrancar para lanzarlo después en orden inverso.
            pargs = kwargs.get("args", ())
            hilo = threading.Thread(target=destino, args=pargs,
                                    name=nombre, daemon=True)
            hilos.append(hilo)
            falso = mock.Mock()
            falso.start = lambda: None
            return falso

        def descargar_simulada(url, _opciones, _progreso, estado, _cancelar, _detalle=None):
            with candado:
                entradas.append(url)
            liberar.wait(5)
            estado("completado", "")

        try:
            with mock.patch.object(descargas, "analizar_url",
                                   return_value={"tipo": "video"}), \
                    mock.patch.object(descargas, "descargar",
                                      side_effect=descargar_simulada), \
                    mock.patch.object(descargas.diagnostico, "crear_hilo",
                                      new=crear_sin_arrancar):
                urls = [f"url-{i}" for i in range(5)]
                for url in urls:
                    gestor.encolar(url, lambda *a: None,
                                   self._registrador(finales))
                self.assertEqual(len(hilos), 5)
                for hilo in reversed(hilos):
                    hilo.start()
                self.assertTrue(_esperar_hasta(lambda: len(entradas) >= 2))
                with candado:
                    self.assertEqual(list(entradas[:2]), urls[:2])
                liberar.set()
                self.assertTrue(_esperar_hasta(lambda: len(finales) == 5,
                                              tiempo=10))
        finally:
            liberar.set()
            for hilo in hilos:
                hilo.join(5)
        self.assertFalse(any(h.is_alive() for h in hilos))
        self.assertEqual(list(entradas), urls)


class TestEsperarTurno(unittest.TestCase):
    def test_esperar_turno_con_evento_puesto_no_toma_turno(self):
        gestor = GestorDescargas({"formato": "mp4", "bitrate": 192, "carpeta": "/tmp"})
        gestor._turnos = mock.Mock()
        gestor._empezados = set()
        evento = threading.Event()
        evento.set()
        self.assertFalse(gestor._esperar_turno("x", evento))
        gestor._turnos.acquire.assert_not_called()
        self.assertEqual(gestor._empezados, set())


class TestOlvidar(unittest.TestCase):
    def test_terminado_se_va_y_no_bloquea_al_siguiente(self):
        from bellbird.downloads import fila_descargas as regla
        from bellbird.downloads.descargas import ItemDescarga
        gestor = GestorDescargas({"formato": "mp4", "bitrate": 192, "carpeta": "/tmp"})
        terminado = ItemDescarga("t", "http://x", "video", estado="completado")
        siguiente = ItemDescarga("s", "http://x", "video", estado="en_cola")
        for it in (terminado, siguiente):
            gestor._items[it.id] = it
            gestor._orden.append(it.id)
            gestor._eventos[it.id] = threading.Event()
        gestor.olvidar("t")
        self.assertIsNone(gestor.obtener("t"))
        self.assertNotIn("t", gestor._orden)
        self.assertNotIn("t", gestor._eventos)
        self.assertFalse(regla.bloqueado_por_anterior(
            "s", gestor._orden, gestor._empezados, gestor._items, gestor._eventos))

    def test_activo_se_queda(self):
        from bellbird.downloads.descargas import ItemDescarga
        gestor = GestorDescargas({"formato": "mp4", "bitrate": 192, "carpeta": "/tmp"})
        activo = ItemDescarga("a", "http://x", "video", estado="descargando")
        gestor._items[activo.id] = activo
        gestor._orden.append(activo.id)
        gestor._eventos[activo.id] = threading.Event()
        gestor.olvidar("a")
        self.assertIs(gestor.obtener("a"), activo)
        self.assertIn("a", gestor._orden)


class TestGestorUnico(unittest.TestCase):
    def tearDown(self):
        reiniciar_gestor()

    def test_devuelve_el_mismo_objeto(self):
        self.assertIs(gestor(), gestor())

    def test_reiniciar_crea_otro_gestor(self):
        anterior = gestor()
        reiniciar_gestor()
        self.assertIsNot(anterior, gestor())

    def test_suscriptor_recibe_estado_final(self):
        estados = []
        gestor_prueba = GestorDescargas({"formato": "mp4"})
        gestor_prueba.suscribir_fin(lambda estado, *_: estados.append(estado))
        terminado = threading.Event()

        def descarga_simulada(_url, _opciones, _progreso, estado, _cancelar, _detalle=None):
            estado("completado", "")
            terminado.set()

        with mock.patch.object(descargas, "analizar_url", return_value={}), \
                mock.patch.object(descargas, "descargar", descarga_simulada):
            gestor_prueba.encolar("https://youtu.be/abc", lambda *_: None,
                                 lambda *_: None)
            self.assertTrue(terminado.wait(1))
        self.assertEqual(estados, ["completado"])

    def test_suscriptor_recibe_el_item_para_el_historial(self):
        recibidos = []
        gestor_prueba = GestorDescargas({"formato": "mp4", "carpeta": "/tmp"})
        gestor_prueba.suscribir_fin(lambda *args: recibidos.append(args))
        terminado = threading.Event()

        def descarga_simulada(_url, _opciones, _progreso, estado, _cancelar, _detalle=None):
            estado("completado", "")
            terminado.set()

        with mock.patch.object(descargas, "analizar_url", return_value={}), \
                mock.patch.object(descargas, "descargar", descarga_simulada):
            item_id = gestor_prueba.encolar("https://youtu.be/abc", lambda *_: None,
                                            lambda *_: None)
            self.assertTrue(terminado.wait(1))
        estado, _mensaje, _nombre, item = recibidos[-1]
        self.assertEqual((estado, item.id, item.carpeta), ("completado", item_id, "/tmp"))

    def test_suscriptor_con_error_no_impide_a_los_demas(self):
        estados = []
        gestor_prueba = GestorDescargas({"formato": "mp4"})

        def suscriptor_roto(*_):
            raise RuntimeError("suscriptor roto")

        gestor_prueba.suscribir_fin(suscriptor_roto)
        gestor_prueba.suscribir_fin(lambda estado, *_: estados.append(estado))
        terminado = threading.Event()

        def descarga_simulada(_url, _opciones, _progreso, estado, _cancelar, _detalle=None):
            estado("completado", "")
            terminado.set()

        with mock.patch.object(descargas, "analizar_url", return_value={}), \
                mock.patch.object(descargas, "descargar", descarga_simulada):
            gestor_prueba.encolar("https://youtu.be/abc", lambda *_: None,
                                 lambda *_: None)
            self.assertTrue(terminado.wait(1))
        self.assertEqual(estados, ["completado"])


class TestFfmpeg(unittest.TestCase):
    def test_devuelve_bool(self): self.assertIsInstance(tiene_ffmpeg(), bool)
    def test_faltante_informa_error(self):
        estados = []
        with mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp"), \
                mock.patch.object(descargas, "tiene_ffmpeg", return_value=False):
            descargar("url", {}, lambda *a: None, lambda *a: estados.append(a), threading.Event())
        self.assertIn("ffmpeg", estados[-1][1])


class TestPseudoFrases(unittest.TestCase):
    """Pseudotraducción de los avisos: lo que oye el usuario sale marcado."""

    def test_frases_de_aviso_salen_marcadas(self):
        with con_pseudo():
            frases = [
                descargas.frase_aviso_descarga("completado", "", "video.mp4"),
                descargas.frase_aviso_descarga("completado", "", ""),
                descargas.frase_aviso_descarga("completado", "3 vídeos",
                                               "video.mp4"),
                descargas.frase_aviso_descarga("parcial", "1 de 3 vídeos",
                                               "video.mp4"),
                descargas.frase_aviso_descarga("error", "sin espacio", ""),
                descargas.frase_aviso_descarga("error", "", ""),
                descargas.frase_aviso_descarga("cancelado", "motivo", "video.mp4"),
            ]
        self.assertTrue(frases)
        for frase in frases:
            self.assertTrue(frase.startswith("[¡"), frase)

    def test_sin_programa_sale_marcado(self):
        with con_pseudo(), \
                mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp",
                                  return_value=None):
            mensaje = descargas.analizar_url("https://example.com/v")["mensaje"]
            estados = []
            descargas.descargar("url", {}, lambda *a: None,
                                lambda *a: estados.append(a),
                                threading.Event())
        self.assertTrue(mensaje.startswith("[¡"), mensaje)
        self.assertTrue(estados[-1][1].startswith("[¡"), estados[-1])

    def test_fallo_del_programa_sale_marcado(self):
        vacio = mock.Mock(stdout="", stderr="", returncode=1)
        with con_pseudo(), \
                mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp",
                                  return_value="yt-dlp"), \
                mock.patch.object(descargas.subprocess, "run",
                                  return_value=vacio):
            mensaje = descargas.analizar_url("https://example.com/v")["mensaje"]
        self.assertTrue(mensaje.startswith("[¡"), mensaje)

    def test_url_vacia_sale_marcada(self):
        nulo = mock.Mock(stdout="null", stderr="", returncode=0)
        with con_pseudo(), \
                mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp",
                                  return_value="yt-dlp"), \
                mock.patch.object(descargas.subprocess, "run",
                                  return_value=nulo):
            mensaje = descargas.analizar_url("https://example.com/v")["mensaje"]
        self.assertTrue(mensaje.startswith("[¡"), mensaje)

    def test_sin_ffmpeg_sale_marcado(self):
        estados = []
        with con_pseudo(), \
                mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp",
                                  return_value="yt-dlp"), \
                mock.patch.object(descargas, "tiene_ffmpeg",
                                  return_value=False):
            descargas.descargar("url", {}, lambda *a: None,
                                lambda *a: estados.append(a),
                                threading.Event())
        self.assertTrue(estados[-1][1].startswith("[¡"), estados[-1])

    def test_cancelado_sale_marcado(self):
        proceso = mock.MagicMock()
        proceso.returncode = 0
        proceso.poll.return_value = 0
        proceso.stdout.readline.side_effect = ["", ""]
        evento = threading.Event()
        evento.set()
        estados = []
        with con_pseudo(), \
                mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp",
                                  return_value="yt-dlp"), \
                mock.patch.object(descargas, "tiene_ffmpeg",
                                  return_value=True), \
                mock.patch.object(descargas.subprocess, "Popen",
                                  return_value=proceso):
            descargas.descargar("url", {"formato": "mp4"}, lambda *a: None,
                                lambda *a: estados.append(a), evento)
        self.assertTrue(estados[-1][1].startswith("[¡"), estados[-1])

    def test_codigo_no_cero_sale_marcado(self):
        proceso = mock.MagicMock()
        proceso.returncode = 2
        proceso.poll.return_value = 0
        proceso.stdout.readline.side_effect = ["", ""]
        estados = []
        with con_pseudo(), \
                mock.patch.object(descargas.ytdlp_bin, "ruta_ytdlp",
                                  return_value="yt-dlp"), \
                mock.patch.object(descargas, "tiene_ffmpeg",
                                  return_value=True), \
                mock.patch.object(descargas.subprocess, "Popen",
                                  return_value=proceso):
            descargas.descargar("url", {"formato": "mp4"}, lambda *a: None,
                                lambda *a: estados.append(a),
                                threading.Event())
        self.assertTrue(estados[-1][1].startswith("[¡"), estados[-1])


if __name__ == "__main__": unittest.main()
