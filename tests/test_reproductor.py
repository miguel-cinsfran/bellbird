"""Pruebas de los avisos de los controles del reproductor.

Las clases con ventana las corre el advisor (abren ventanas de verdad y
aquí no se corren): aquí solo se corren las que usan paneles con dobles.
"""

import unittest
from unittest import mock
import threading
import time
import types
import sys

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False

from ytchat.player import motor_vlc
from ytchat.player import reproductor
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import destruir


_MONOTONIC_REAL = time.monotonic


class RelojMonotonic:
    def __init__(self, primero, despues):
        self._llamadas = 0
        self._primero = primero
        self._despues = despues
        self._hilo = threading.get_ident()
        self._real = _MONOTONIC_REAL

    def __call__(self):
        if threading.get_ident() != self._hilo:
            return self._real()
        self._llamadas += 1
        return self._primero if self._llamadas == 1 else self._despues


FORMATOS_SEPARADOS = [
    {"format_id": "233", "height": None, "vcodec": "none",
     "acodec": None, "abr": None, "tbr": None, "url": "audio-233"},
    {"format_id": "234", "height": None, "vcodec": "none",
     "acodec": None, "abr": None, "tbr": None, "url": "audio-234"},
    {"format_id": "269", "height": 144, "vcodec": "avc1.42C00B",
     "acodec": "none", "abr": 0, "tbr": 269.034, "url": "video-144"},
    {"format_id": "229", "height": 240, "vcodec": "avc1.4D4015",
     "acodec": "none", "abr": 0, "tbr": 507.418, "url": "video-240"},
    {"format_id": "230", "height": 360, "vcodec": "avc1.4D401E",
     "acodec": "none", "abr": 0, "tbr": 1000.0, "url": "video-360"},
    {"format_id": "231", "height": 480, "vcodec": "avc1.4D401F",
     "acodec": "none", "abr": 0, "tbr": 1500.0, "url": "video-480"},
    {"format_id": "232", "height": 720, "vcodec": "avc1.4D401F",
     "acodec": "none", "abr": 0, "tbr": 2500.0, "url": "video-720"},
    {"format_id": "270", "height": 1080, "vcodec": "avc1.640028",
     "acodec": "none", "abr": 0, "tbr": 4500.0, "url": "video-1080"},
]


class TestSeleccionFormatos(unittest.TestCase):

    def test_elige_audio_con_acodec_nulo(self):
        self.assertIn(
            reproductor._mejor_audio({"formats": FORMATOS_SEPARADOS}),
            ("audio-233", "audio-234"),
        )

    def test_elige_video_1080_sin_progresivo(self):
        self.assertEqual(
            reproductor._video_para_altura(
                {"formats": FORMATOS_SEPARADOS}, 10000),
            ("video-1080", False),
        )

    def test_elige_video_480_sin_progresivo(self):
        self.assertEqual(
            reproductor._video_para_altura(
                {"formats": FORMATOS_SEPARADOS}, 480),
            ("video-480", False),
        )

    def test_a_igual_altura_gana_mayor_tbr(self):
        formatos = [
            {"vcodec": "avc1", "acodec": "none", "height": 720,
             "tbr": 2000, "url": "video-720-lento"},
            {"vcodec": "avc1", "acodec": "none", "height": 720,
             "tbr": 3000, "url": "video-720-rapido"},
        ]
        self.assertEqual(
            reproductor._video_para_altura({"formats": formatos}, 1000),
            ("video-720-rapido", False),
        )

    def test_sin_progresivo_elige_la_menor_altura_no_superior(self):
        formatos = [
            {"vcodec": "avc1", "acodec": "none", "height": 720,
             "url": "video-720"},
            {"vcodec": "avc1", "acodec": "none", "height": 1080,
             "url": "video-1080"},
        ]
        self.assertEqual(
            reproductor._video_para_altura({"formats": formatos}, 480),
            ("video-720", False),
        )

    def test_sin_progresivo_elige_la_menor_altura_disponible(self):
        formatos = [
            {"vcodec": "avc1", "acodec": "none", "height": 720,
             "url": "video-720"},
            {"vcodec": "avc1", "acodec": "none", "height": 1080,
             "url": "video-1080"},
        ]
        self.assertEqual(
            reproductor._video_para_altura({"formats": formatos}, 144),
            ("video-720", False),
        )

    def test_descarta_guion_grafico_como_audio(self):
        formato = {"vcodec": "none", "acodec": "none", "url": "grafico"}
        self.assertEqual(reproductor._mejor_audio({"formats": [formato]}), "")

    def test_conserva_la_seleccion_progresiva(self):
        formatos = [
            {"vcodec": "avc1", "acodec": "mp4a", "height": 360,
             "url": "progresivo-360"},
            {"vcodec": "avc1", "acodec": "mp4a", "height": 720,
             "url": "progresivo-720"},
        ]
        self.assertEqual(
            reproductor._video_para_altura({"formats": formatos}, 720),
            ("progresivo-720", True),
        )

    def test_prefiere_idioma_alto_antes_que_bitrate(self):
        formatos = [
            {"vcodec": "none", "acodec": None, "abr": 320,
             "language_preference": 1, "url": "doblaje"},
            {"vcodec": "none", "acodec": None, "abr": 128,
             "language_preference": 10, "url": "original"},
        ]
        self.assertEqual(
            reproductor._mejor_audio({"formats": formatos}), "original")


class TestPreferirHls(unittest.TestCase):

    def test_hay_hls_se_queda_solo_con_esas(self):
        formatos = [
            {"protocol": "https", "url": "dash-crudo"},
            {"protocol": "m3u8_native", "vcodec": "avc1", "url": "hls"},
        ]
        self.assertEqual(reproductor._preferir_hls(formatos),
                         [{"protocol": "m3u8_native", "vcodec": "avc1", "url": "hls"}])

    def test_hls_solo_de_audio_no_filtra(self):
        # Quedarse con una familia HLS sin vídeo dejaría el directo sin imagen.
        formatos = [
            {"protocol": "https", "vcodec": "avc1", "acodec": "none", "url": "dash-video"},
            {"protocol": "m3u8_native", "vcodec": "none", "acodec": "mp4a", "url": "hls-audio"},
        ]
        self.assertEqual(reproductor._preferir_hls(formatos), formatos)

    def test_sin_hls_deja_la_lista_igual(self):
        formatos = [{"protocol": "https", "url": "dash-crudo"}]
        self.assertEqual(reproductor._preferir_hls(formatos), formatos)

    def test_lista_vacia(self):
        self.assertEqual(reproductor._preferir_hls([]), [])

    def test_protocolo_ausente_no_rompe(self):
        formatos = [{"url": "sin-protocolo"}]
        self.assertEqual(reproductor._preferir_hls(formatos), formatos)


class TestFuentesParaDirecto(unittest.TestCase):

    def test_directo_mezcla_hls_y_dash_crudo_gana_hls(self):
        # Lo que se vio con un directo real: la misma extracción trae
        # variantes m3u8 (HLS, la que entienden VLC/ffmpeg) y variantes
        # «https»/DASH-en-crudo (protocolo de secuencias propio de YouTube,
        # que ffmpeg no sabe abrir directo: "Invalid data found").
        info = {"formats": [
            {"vcodec": "avc1", "acodec": "none", "height": 1080,
             "protocol": "https", "url": "video-dash-crudo"},
            {"vcodec": "none", "acodec": "mp4a", "protocol": "https",
             "url": "audio-dash-crudo"},
            {"vcodec": "avc1", "acodec": "none", "height": 1080,
             "protocol": "m3u8_native", "url": "video-hls"},
            {"vcodec": "none", "acodec": "mp4a", "protocol": "m3u8_native",
             "url": "audio-hls"},
        ]}
        self.assertEqual(
            reproductor.fuentes_para_directo(info),
            ("video-hls", "audio-hls"))

    def test_hls_con_video_pero_sin_audio_toma_el_audio_de_la_lista_completa(self):
        # Antes: _mejor_audio sobre la familia HLS devolvía "" y el directo
        # sonaba mudo aunque hubiera un audio DASH disponible.
        info = {"formats": [
            {"vcodec": "avc1", "acodec": "none", "height": 720,
             "protocol": "m3u8_native", "url": "video-hls"},
            {"vcodec": "none", "acodec": "mp4a", "protocol": "https",
             "url": "audio-dash"},
        ]}
        self.assertEqual(reproductor.fuentes_para_directo(info),
                         ("video-hls", "audio-dash"))

    def test_hls_solo_de_audio_no_deja_el_directo_sin_video(self):
        info = {"formats": [
            {"vcodec": "avc1", "acodec": "none", "height": 720,
             "protocol": "https", "url": "video-dash"},
            {"vcodec": "none", "acodec": "mp4a", "protocol": "m3u8_native",
             "url": "audio-hls"},
        ]}
        self.assertEqual(reproductor.fuentes_para_directo(info),
                         ("video-dash", "audio-hls"))

    def test_url_superior_gana_sobre_las_demás_fuentes(self):
        info = {
            "url": "superior",
            "formats": FORMATOS_SEPARADOS,
            "requested_formats": [
                {"vcodec": "avc1", "acodec": "none", "url": "video"},
                {"vcodec": "none", "acodec": "mp4a", "url": "audio"},
            ],
        }
        self.assertEqual(reproductor.fuentes_para_directo(info), ("superior", ""))

    def test_usa_formato_progresivo(self):
        info = {"formats": [
            {"vcodec": "avc1", "acodec": "mp4a", "height": 720,
             "url": "progresivo"},
        ]}
        self.assertEqual(reproductor.fuentes_para_directo(info), ("progresivo", ""))

    def test_usa_video_y_audio_de_formats(self):
        self.assertEqual(
            reproductor.fuentes_para_directo({"formats": FORMATOS_SEPARADOS}),
            ("video-1080", "audio-233"),
        )

    def test_usa_el_par_solicitado_si_formats_no_sirve(self):
        info = {"formats": [], "requested_formats": [
            {"vcodec": "avc1", "acodec": "none", "url": "video-solicitado"},
            {"vcodec": "none", "acodec": "mp4a", "url": "audio-solicitado"},
        ]}
        self.assertEqual(
            reproductor.fuentes_para_directo(info),
            ("video-solicitado", "audio-solicitado"),
        )

    def test_sin_fuentes_devuelve_vacio(self):
        self.assertEqual(reproductor.fuentes_para_directo({}), ("", ""))


class TestReproducirDirecto(unittest.TestCase):

    def setUp(self):
        # El relevo lee la ventana HLS por red al arrancar: aquí no hay red.
        parche = mock.patch.object(reproductor.relevo_ffmpeg, "leer_ventana_hls",
                                   return_value=None)
        parche.start()
        self.addCleanup(parche.stop)

    def _panel(self, info):
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._info = info
        panel._inst = mock.Mock()
        player = mock.Mock()
        panel._player = player
        panel._vol = 75
        panel._muted = False
        panel._timer = mock.Mock()
        panel.lbl_estado = mock.Mock()
        panel._video_id = "vid"
        panel._gen = 0
        panel._relevo_gen = 0
        panel._relevo_ffmpeg = None
        panel._asegurar_player = mock.Mock(return_value=True)
        panel._error_carga = mock.Mock()
        panel._mostrar_pausa = mock.Mock()
        return panel

    def _hilo_sincrono(self):
        """Reemplaza diagnostico.crear_hilo por algo que corre en el
        momento, y wx.CallAfter por una llamada directa: así el relevo (que
        en producción va a un hilo aparte para no bloquear la GUI) se puede
        probar sin hilos reales."""
        hilo = mock.Mock()

        def crear(target, _nombre):
            hilo.target = target
            return hilo

        hilo.start.side_effect = lambda: hilo.target()
        return (
            mock.patch.object(reproductor.diagnostico, "crear_hilo", side_effect=crear),
            mock.patch.object(reproductor.wx, "CallAfter", side_effect=lambda fn, *a: fn(*a)),
        )

    def test_directo_con_pares_separados_usa_el_relevo_de_ffmpeg(self):
        panel = self._panel({"is_live": True, "formats": [], "requested_formats": [
            {"vcodec": "avc1", "acodec": "none", "url": "video-solicitado"},
            {"vcodec": "none", "acodec": "mp4a", "url": "audio-solicitado"},
        ]})
        medio = mock.Mock()
        panel._inst.media_new.return_value = medio
        relevo = mock.Mock()
        relevo.iniciar.return_value = "tcp://127.0.0.1:5555"

        parche_hilo, parche_callafter = self._hilo_sincrono()
        with parche_hilo, parche_callafter, \
                mock.patch.object(reproductor.relevo_ffmpeg, "RelevoFfmpeg",
                                  return_value=relevo) as clase_relevo, \
                mock.patch.object(reproductor.time, "sleep"):
            panel._reproducir_calidad(None, reproducir=False)

        clase_relevo.assert_called_once_with("video-solicitado", "audio-solicitado", 0)
        panel._inst.media_new.assert_called_once_with("tcp://127.0.0.1:5555")
        opciones = [c.args[0] for c in medio.add_option.call_args_list]
        self.assertFalse(any(o.startswith(":input-slave=") for o in opciones))
        self.assertIs(panel._relevo_ffmpeg, relevo)
        self.assertFalse(panel._tiene_esclavo)
        panel._error_carga.assert_not_called()

    def test_directo_si_el_relevo_no_arranca_cae_a_input_slave(self):
        panel = self._panel({"is_live": True, "formats": [], "requested_formats": [
            {"vcodec": "avc1", "acodec": "none", "url": "video-solicitado"},
            {"vcodec": "none", "acodec": "mp4a", "url": "audio-solicitado"},
        ]})
        medio = mock.Mock()
        panel._inst.media_new.return_value = medio
        relevo = mock.Mock()
        relevo.iniciar.return_value = None  # sin ffmpeg disponible, por ejemplo

        parche_hilo, parche_callafter = self._hilo_sincrono()
        with parche_hilo, parche_callafter, \
                mock.patch.object(reproductor.relevo_ffmpeg, "RelevoFfmpeg",
                                  return_value=relevo):
            panel._reproducir_calidad(None, reproducir=False)

        panel._inst.media_new.assert_called_once_with("video-solicitado")
        medio.add_option.assert_any_call(":input-slave=audio-solicitado")
        self.assertIsNone(panel._relevo_ffmpeg)
        panel._error_carga.assert_not_called()

    def test_directo_descarta_el_relevo_si_ya_no_es_el_ultimo_pedido(self):
        # El usuario cambió de vídeo (o desconectó) mientras el relevo
        # arrancaba: el resultado, si llega tarde, no debe usarse ni dejar
        # el proceso de ffmpeg huérfano.
        panel = self._panel({"is_live": True, "formats": [], "requested_formats": [
            {"vcodec": "avc1", "acodec": "none", "url": "video-solicitado"},
            {"vcodec": "none", "acodec": "mp4a", "url": "audio-solicitado"},
        ]})
        relevo = mock.Mock()
        relevo.iniciar.return_value = "tcp://127.0.0.1:5555"

        callbacks = []
        with mock.patch.object(reproductor.diagnostico, "crear_hilo",
                               side_effect=lambda target, _n: mock.Mock(
                                   start=lambda: target())), \
                mock.patch.object(reproductor.wx, "CallAfter",
                                  side_effect=lambda fn, *a: callbacks.append(
                                      lambda: fn(*a))), \
                mock.patch.object(reproductor.relevo_ffmpeg, "RelevoFfmpeg",
                                  return_value=relevo), \
                mock.patch.object(reproductor.time, "sleep"):
            panel._reproducir_calidad(None, reproducir=False)
            panel._video_id = "otro-vid"  # cambió de vídeo antes de que llegue
            callbacks[0]()

        relevo.detener.assert_called_once()
        self.assertIsNone(panel._relevo_ffmpeg)
        panel._inst.media_new.assert_not_called()

    def test_directo_sin_fuentes_deja_diagnostico(self):
        panel = self._panel({"is_live": True, "formats": [],
                             "requested_formats": []})
        with mock.patch.object(reproductor.logger, "warning") as warning:
            panel._reproducir_calidad(None, reproducir=False)

        warning.assert_called_once_with(
            "reproducir directo sin fuentes: url_superior=%s formats=%d "
            "requested_formats=%d is_live=%s", "no", 0, 0, True)
        panel._error_carga.assert_called_once_with()


class _YoutubeDL:
    def __init__(self, opciones):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def extract_info(self, *args, **kwargs):
        return {"formats": [{"vcodec": "avc1", "height": 720}]}


class TestInfoVideo(unittest.TestCase):

    def test_info_video_con_programa_no_importa_el_modulo(self):
        info = {"formats": [{"vcodec": "avc1", "height": 1080}]}
        with mock.patch.object(reproductor.ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(reproductor.ytdlp_bin, "info_video", return_value=info), \
                mock.patch.dict(sys.modules, {"yt_dlp": None}):
            self.assertIs(info, reproductor._info_video("A" * 11))

    def test_info_video_sin_programa_usa_el_modulo(self):
        modulo = types.SimpleNamespace(YoutubeDL=_YoutubeDL)
        with mock.patch.object(reproductor.ytdlp_bin, "ruta_ytdlp", return_value=None), \
                mock.patch.object(reproductor.ytdlp_bin, "info_video", return_value=None) as programa, \
                mock.patch.dict(sys.modules, {"yt_dlp": modulo}):
            self.assertEqual(
                {"formats": [{"vcodec": "avc1", "height": 720}]},
                reproductor._info_video("A" * 11),
            )
        programa.assert_not_called()

    def test_info_video_con_programa_que_falla_no_reintenta_con_el_modulo(self):
        # El programa agotó sus 30 s (o falló): repetir con el módulo sumaba
        # otros 20-30 s de «Cargando vídeo…» para el mismo desenlace.
        modulo = types.SimpleNamespace(YoutubeDL=mock.Mock())
        with mock.patch.object(reproductor.ytdlp_bin, "ruta_ytdlp", return_value="yt-dlp.exe"), \
                mock.patch.object(reproductor.ytdlp_bin, "info_video", return_value=None), \
                mock.patch.dict(sys.modules, {"yt_dlp": modulo}):
            with self.assertRaises(RuntimeError):
                reproductor._info_video("A" * 11)
        modulo.YoutubeDL.assert_not_called()


class TestAvisoReproductor(unittest.TestCase):

    def test_sin_reproductor(self):
        self.assertEqual(
            reproductor.aviso_reproductor(False, False),
            "El reproductor no está disponible")

    def test_reproductor_sin_medio(self):
        self.assertEqual(
            reproductor.aviso_reproductor(True, False),
            "No hay ningún vídeo cargado")

    def test_reproductor_con_medio(self):
        self.assertEqual(reproductor.aviso_reproductor(True, True), "")


class TestSoloAudio(unittest.TestCase):
    """Cableado de «Reproducir solo el audio»: el medio nuevo se arma con
    «:no-video» salvo que el audio venga como esclavo."""

    def _panel(self):
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._inst = mock.Mock()
        panel._player = mock.Mock()
        panel._vol = 75
        panel._muted = False
        panel._timer = mock.Mock()
        panel._estado_inicio = mock.Mock()
        panel._fijar_estado = mock.Mock()
        panel._mostrar_pausa = mock.Mock()
        panel._solo_audio = False
        return panel

    def _medio(self, panel):
        medio = mock.Mock()
        panel._inst.media_new.return_value = medio
        return medio

    def _opciones(self, medio):
        return [c.args[0] for c in medio.add_option.call_args_list]

    def test_flujo_agrega_no_video_con_la_preferencia_puesta(self):
        panel = self._panel()
        panel._url_flujo = "https://flujo.example/stream.flv"
        panel._asegurar_player = mock.Mock(return_value=True)
        panel._cancelar_busqueda = mock.Mock()
        panel._cancelar_transporte = mock.Mock()
        medio = self._medio(panel)
        panel.set_solo_audio(True)
        panel._reproducir_flujo(reproducir=False)
        self.assertIn(":no-video", self._opciones(medio))

    def test_flujo_no_agrega_no_video_sin_la_preferencia(self):
        panel = self._panel()
        panel._url_flujo = "https://flujo.example/stream.flv"
        panel._asegurar_player = mock.Mock(return_value=True)
        panel._cancelar_busqueda = mock.Mock()
        panel._cancelar_transporte = mock.Mock()
        medio = self._medio(panel)
        panel.set_solo_audio(False)
        panel._reproducir_flujo(reproducir=False)
        self.assertNotIn(":no-video", self._opciones(medio))

    def test_calidad_sin_esclavo_agrega_no_video(self):
        panel = self._panel()
        panel._tiene_esclavo = False
        panel._audio_local = None
        medio = self._medio(panel)
        panel.set_solo_audio(True)
        panel._continuar_reproducir_calidad("https://video", "", True, False)
        self.assertIn(":no-video", self._opciones(medio))

    def test_calidad_con_esclavo_conserva_la_imagen(self):
        # Con el audio como input-slave, «:no-video» deja el medio mudo.
        panel = self._panel()
        panel._tiene_esclavo = False
        medio = self._medio(panel)
        panel.set_solo_audio(True)
        panel._continuar_reproducir_calidad(
            "https://video", "https://audio", True, False)
        self.assertNotIn(":no-video", self._opciones(medio))

    def test_constructor_lee_la_preferencia_del_config(self):
        with mock.patch.object(reproductor.wx.Panel, "__init__", return_value=None), \
                mock.patch.object(reproductor.ReproductorPanel, "SetBackgroundColour"), \
                mock.patch.object(reproductor.ReproductorPanel, "SetForegroundColour"), \
                mock.patch.object(reproductor, "disponible", return_value=True), \
                mock.patch.object(reproductor.ReproductorPanel, "_build_ui"), \
                mock.patch.object(reproductor.ReproductorPanel, "_precalentar"):
            panel = reproductor.ReproductorPanel(
                None, {"reproductor_solo_audio": True})
        self.assertTrue(panel._solo_audio)


class TestOpcionesMedio(unittest.TestCase):

    def test_grabado_tiene_mas_colchon_de_red_que_directo(self):
        grabado = dict(opcion[1:].split("=", 1)
                       for opcion in reproductor.opciones_medio(False))
        directo = dict(opcion[1:].split("=", 1)
                       for opcion in reproductor.opciones_medio(True))
        self.assertGreater(int(grabado["network-caching"]),
                           int(directo["network-caching"]))

    def test_ambos_medios_declaran_las_dos_opciones_de_buffer(self):
        for es_directo in (False, True):
            opciones = reproductor.opciones_medio(es_directo)
            self.assertEqual(len(opciones), 2)
            self.assertTrue(any(opcion.startswith(":network-caching=")
                                for opcion in opciones))
            self.assertTrue(any(opcion.startswith(":live-caching=")
                                for opcion in opciones))

    def test_sin_solo_audio_no_agrega_no_video(self):
        for es_directo in (False, True):
            self.assertNotIn(":no-video", reproductor.opciones_medio(es_directo))

    def test_solo_audio_agrega_no_video_a_grabado_y_directo(self):
        for es_directo in (False, True):
            opciones = reproductor.opciones_medio(es_directo, solo_audio=True)
            self.assertEqual(opciones[-1], ":no-video")
            # Las de búfer siguen: sin ellas el directo pierde su colchón.
            self.assertTrue(any(opcion.startswith(":network-caching=")
                                for opcion in opciones))
            self.assertTrue(any(opcion.startswith(":live-caching=")
                                for opcion in opciones))


class TestAvisoDeCorte(unittest.TestCase):

    def test_avisa_al_caer_el_buffer_por_primera_vez(self):
        self.assertTrue(reproductor.aviso_de_corte(99, None))

    def test_avisa_al_recuperarse_el_buffer(self):
        self.assertTrue(reproductor.aviso_de_corte(100, 99))

    def test_no_avisa_cada_evento_durante_un_corte(self):
        self.assertEqual(reproductor.aviso_de_corte(80, 99), "")


class TestRelojMonotonic(unittest.TestCase):

    def test_otro_hilo_recibe_tiempo_real_y_no_consume_valores(self):
        reloj = RelojMonotonic(1.0, 1.25)
        ajenos = []
        hilo = threading.Thread(target=lambda: ajenos.append(reloj()))
        hilo.start()
        hilo.join()
        self.assertEqual(len(ajenos), 1)
        self.assertNotIn(ajenos[0], (1.0, 1.25))
        self.assertEqual(reloj._llamadas, 0)
        self.assertEqual(reloj(), 1.0)
        self.assertEqual(reloj(), 1.25)


class TestPrecalentamiento(unittest.TestCase):

    def _panel(self):
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._precalentamiento_cancelado = False
        return panel

    def test_precalienta_en_silencio(self):
        panel = self._panel()
        orden = []
        hilo = mock.Mock()

        def crear(target, _nombre):
            hilo.target = target
            return hilo

        def iniciar():
            hilo.target()

        hilo.start.side_effect = iniciar
        panel._asegurar_instancia = lambda: orden.append("trabajo") or True
        with mock.patch.object(reproductor, "anunciar") as anunciar, \
                mock.patch.object(reproductor.diagnostico, "crear_hilo",
                                   side_effect=crear), \
                mock.patch.object(reproductor.wx, "CallAfter",
                                   side_effect=lambda fn: fn()):
            panel._precalentar()

        self.assertEqual(orden, ["trabajo"])
        anunciar.assert_not_called()

    def test_si_falla_no_anuncia_nada(self):
        panel = self._panel()
        hilo = mock.Mock()
        def crear(target, _nombre):
            hilo.target = target
            return hilo
        hilo.start.side_effect = lambda: hilo.target()
        panel._asegurar_instancia = mock.Mock(side_effect=RuntimeError("fallo"))
        with mock.patch.object(reproductor, "anunciar") as anunciar, \
                mock.patch.object(reproductor.diagnostico, "crear_hilo",
                                   side_effect=crear):
            panel._precalentar()

        anunciar.assert_not_called()

    def test_si_se_cierra_no_anuncia_nada(self):
        panel = self._panel()
        callbacks = []
        hilo = mock.Mock()
        def crear(target, _nombre):
            hilo.target = target
            return hilo
        hilo.start.side_effect = lambda: hilo.target()
        panel._asegurar_instancia = mock.Mock(return_value=True)
        with mock.patch.object(reproductor, "anunciar") as anunciar, \
                mock.patch.object(reproductor.diagnostico, "crear_hilo",
                                   side_effect=crear), \
                mock.patch.object(reproductor.wx, "CallAfter",
                                   side_effect=lambda fn: callbacks.append(fn)):
            panel._precalentar()
            panel._precalentamiento_cancelado = True
            callbacks[0]()

        anunciar.assert_not_called()

    def test_el_constructor_no_precalienta(self):
        with mock.patch.object(reproductor.wx.Panel, "__init__", return_value=None), \
                mock.patch.object(reproductor.ReproductorPanel, "SetBackgroundColour"), \
                mock.patch.object(reproductor.ReproductorPanel, "SetForegroundColour"), \
                mock.patch.object(reproductor, "disponible", return_value=True), \
                mock.patch.object(reproductor.ReproductorPanel, "_build_ui"), \
                mock.patch.object(reproductor.ReproductorPanel, "_precalentar") as precalentar:
            reproductor.ReproductorPanel(None, {})

        precalentar.assert_not_called()


class TestEventosVlc(unittest.TestCase):

    def _panel_para_detener(self, gestor=None):
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._gen = 0
        panel._cargando = True
        panel._destino_pendiente = object()
        panel._intencion_reproducir = True
        panel._timer_progreso = mock.Mock()
        panel._player = mock.Mock()
        panel._gestor_eventos_vlc = gestor
        return panel

    def _panel_con_eventos(self):
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._player = mock.Mock()
        panel._gestor_eventos_vlc = None
        return panel

    def test_engancha_eventos_solo_con_registro_detallado(self):
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._player = None
        panel._inst = mock.Mock()
        panel._asegurar_instancia = mock.Mock(return_value=True)
        panel._video = mock.Mock()
        panel._fijar_salida = mock.Mock()
        panel._enganchar_eventos_vlc = mock.Mock()
        with mock.patch.object(reproductor, "_registro_detallado_activo",
                               return_value=False):
            self.assertTrue(panel._asegurar_player())
        panel._enganchar_eventos_vlc.assert_called_once()
        panel._enganchar_eventos_vlc.reset_mock()
        panel._player = None
        with mock.patch.object(reproductor, "_registro_detallado_activo",
                               return_value=True):
            self.assertTrue(panel._asegurar_player())
        panel._enganchar_eventos_vlc.assert_called_once()

    def test_enganchar_eventos_conserva_el_gestor(self):
        panel = self._panel_con_eventos()
        gestor = mock.Mock()
        panel._player.event_manager.return_value = gestor
        tipos = types.SimpleNamespace(**{
            nombre: object() for nombre in (
                "MediaPlayerPlaying", "MediaPlayerPaused", "MediaPlayerStopped",
                "MediaPlayerEndReached", "MediaPlayerEncounteredError",
                "MediaPlayerBuffering")})

        with mock.patch.object(motor_vlc, "modulo",
                               return_value=types.SimpleNamespace(EventType=tipos)):
            panel._enganchar_eventos_vlc()

        self.assertIs(panel._gestor_eventos_vlc, gestor)

    def test_enganchar_eventos_usa_el_mismo_gestor_para_los_seis_tipos(self):
        panel = self._panel_con_eventos()
        gestor = mock.Mock()
        panel._player.event_manager.return_value = gestor
        tipos = types.SimpleNamespace(**{
            nombre: object() for nombre in (
                "MediaPlayerPlaying", "MediaPlayerPaused", "MediaPlayerStopped",
                "MediaPlayerEndReached", "MediaPlayerEncounteredError",
                "MediaPlayerBuffering")})

        with mock.patch.object(motor_vlc, "modulo",
                               return_value=types.SimpleNamespace(EventType=tipos)), \
             mock.patch.object(reproductor, "_registro_detallado_activo", return_value=True):
            panel._enganchar_eventos_vlc()

        self.assertEqual(gestor.event_attach.call_count, 6)

    def test_detener_en_segundo_plano_conserva_el_gestor_hasta_liberar(self):
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._gen = 0
        panel._cargando = True
        panel._destino_pendiente = object()
        panel._intencion_reproducir = True
        panel._timer_progreso = mock.Mock()
        player = mock.Mock()
        panel._player = player
        gestor = object()
        panel._gestor_eventos_vlc = gestor
        hilo = mock.Mock()
        hilo.start = mock.Mock()

        with mock.patch.object(reproductor.diagnostico, "crear_hilo",
                               return_value=hilo) as crear_hilo:
            panel._detener(silencioso=True, en_segundo_plano=True)

        cierre = crear_hilo.call_args.args[0]
        self.assertIsNone(panel._gestor_eventos_vlc)
        self.assertIn(gestor, cierre.__defaults__)
        player.release.side_effect = lambda: self.assertIn(gestor, cierre.__defaults__)
        cierre()
        player.release.assert_called_once_with()

    def test_detener_en_segundo_plano_suelta_la_ventana_de_video(self):
        panel = self._panel_para_detener()
        player = panel._player
        hilo = mock.Mock()
        with mock.patch.object(reproductor.diagnostico, "crear_hilo",
                               return_value=hilo):
            panel._detener(silencioso=True, en_segundo_plano=True)
        player.set_hwnd.assert_called_once_with(0)
        hilo.start.assert_called_once_with()

    def test_detener_suelta_la_ventana_antes_de_crear_el_hilo(self):
        panel = self._panel_para_detener()
        player = panel._player
        hilo = mock.Mock()

        def crear_hilo(_cerrar, _nombre):
            self.assertTrue(player.set_hwnd.called)
            return hilo

        with mock.patch.object(reproductor.diagnostico, "crear_hilo",
                               side_effect=crear_hilo):
            panel._detener(silencioso=True, en_segundo_plano=True)

        player.set_hwnd.assert_called_once_with(0)

    def test_detener_normal_no_suelta_la_ventana_de_video(self):
        panel = self._panel_para_detener()
        player = panel._player
        panel._detener(silencioso=True, en_segundo_plano=False)
        player.set_hwnd.assert_not_called()
        self.assertIs(panel._player, player)

    def test_detener_continua_si_no_puede_soltar_la_ventana(self):
        panel = self._panel_para_detener()
        panel._player.set_hwnd.side_effect = RuntimeError("sin salida")
        hilo = mock.Mock()
        with mock.patch.object(reproductor.diagnostico, "crear_hilo",
                               return_value=hilo) as crear_hilo:
            panel._detener(silencioso=True, en_segundo_plano=True)
        crear_hilo.assert_called_once()
        hilo.start.assert_called_once_with()

    def test_detener_en_segundo_plano_sin_gestor_de_eventos(self):
        panel = self._panel_para_detener(gestor=None)
        hilo = mock.Mock()
        with mock.patch.object(reproductor.diagnostico, "crear_hilo",
                               return_value=hilo):
            panel._detener(silencioso=True, en_segundo_plano=True)
        self.assertIsNone(panel._player)
        hilo.start.assert_called_once_with()

    def test_constructor_inicializa_el_gestor_de_eventos(self):
        """Evita AttributeError al cerrar por detrás sin registro detallado."""
        self.assertIn("_gestor_eventos_vlc",
                      reproductor.ReproductorPanel.__init__.__code__.co_names)


class TestAvisoAlReproducir(unittest.TestCase):

    def test_reproducir_sin_medio_anuncia(self):
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._listo = True
        panel._video_id = ""
        panel._url_flujo = ""
        panel._asegurar_player = lambda: True
        panel._player = mock.Mock()
        panel._intencion_reproducir = False
        panel._player.get_state.return_value = object()

        with mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._toggle_play()

        anunciar.assert_called_once_with("No hay ningún vídeo cargado")

    def _panel_sin_medio(self):
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._listo = True
        panel._video_id = ""
        panel._url_flujo = ""
        panel._player = None
        return panel

    def test_silenciar_sin_medio_anuncia(self):
        with mock.patch.object(reproductor, "anunciar") as anunciar:
            self._panel_sin_medio()._toggle_mute()
        anunciar.assert_called_once_with("No hay ningún vídeo cargado")

    def test_silenciar_sin_reproductor_anuncia_indisponible(self):
        panel = self._panel_sin_medio()
        panel._listo = False
        with mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._toggle_mute()
        anunciar.assert_called_once_with("El reproductor no está disponible")

    def test_buscar_sin_medio_anuncia(self):
        with mock.patch.object(reproductor, "anunciar") as anunciar:
            self._panel_sin_medio()._buscar_rel(10_000)
        anunciar.assert_called_once_with("No hay ningún vídeo cargado")

    def test_buscar_con_medio_sin_reproductor_no_toca_el_relevo(self):
        panel = self._panel_sin_medio()
        panel._video_id = "video-cargado"
        panel._relevo_fuentes = ("https://flujo.example/stream", None)
        panel._es_directo_actual = lambda: True
        panel._saltar_en_relevo = mock.Mock()
        with mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._buscar_rel(10_000)
        panel._saltar_en_relevo.assert_not_called()
        anunciar.assert_not_called()

    def test_pantalla_completa_sin_reproductor_anuncia(self):
        panel = self._panel_sin_medio()
        panel._listo = False
        panel._asegurar_player = lambda: False
        with mock.patch.object(reproductor, "anunciar") as anunciar:
            panel.alternar_pantalla_completa()
        anunciar.assert_called_once_with("El reproductor no está disponible")

    def test_reproducir_sin_reproductor_anuncia(self):
        panel = self._panel_sin_medio()
        panel._listo = False
        panel._asegurar_player = lambda: False
        with mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._toggle_play()
        anunciar.assert_called_once_with("El reproductor no está disponible")

    def test_reproducir_con_medio_no_anuncia_falta_de_medio(self):
        panel = self._panel_sin_medio()
        panel._video_id = "video-cargado"
        panel._asegurar_player = lambda: False
        with mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._toggle_play()
        anunciar.assert_not_called()

        panel._video_id = ""
        with mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._toggle_play()
        anunciar.assert_called_once_with("No hay ningún vídeo cargado")

    def test_reproducir_con_flujo_no_anuncia_falta_de_medio(self):
        panel = self._panel_sin_medio()
        panel._url_flujo = "https://flujo.example/stream"
        panel._asegurar_player = lambda: False
        with mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._toggle_play()
        anunciar.assert_not_called()

    def _panel_con_player_vacio(self):
        panel = self._panel_sin_medio()
        panel._player = mock.Mock()
        panel._vol = 50
        panel._muted = False
        panel._fs = None
        panel.sld_pos = mock.Mock()
        panel.sld_vol = mock.Mock()
        panel._asegurar_player = mock.Mock(return_value=True)
        return panel

    def _comprobar_guarda_sin_medio(self, accion):
        panel = self._panel_con_player_vacio()
        with mock.patch.object(reproductor, "anunciar") as anunciar:
            accion(panel)
        anunciar.assert_called_once_with("No hay ningún vídeo cargado")
        for nombre in ("audio_set_mute", "audio_set_volume", "set_time",
                       "set_position", "play", "pause"):
            getattr(panel._player, nombre).assert_not_called()
        self.assertEqual(panel._vol, 50)
        panel.sld_vol.SetValue.assert_not_called()
        panel.sld_pos.SetValue.assert_not_called()
        panel._asegurar_player.assert_not_called()

    def test_acciones_sobre_el_medio_sin_video_anuncian_y_no_tocan_nada(self):
        acciones = {
            "reproducir o pausar": lambda p: p._toggle_play(),
            "detener": lambda p: p._detener(),
            "silenciar": lambda p: p._toggle_mute(),
            "subir volumen": lambda p: p.ajustar_volumen(+20),
            "bajar volumen": lambda p: p.ajustar_volumen(-20),
            "flecha de volumen": lambda p: p._vol_flecha(+1),
            "retroceder": lambda p: p._buscar_rel(-60_000),
            "avanzar": lambda p: p._buscar_rel(+60_000),
            "saltar a porcentaje": lambda p: p._buscar_porcentaje(50),
            "mover deslizador de posición": lambda p: p._on_sld_pos(None),
            "pantalla completa": lambda p: p.alternar_pantalla_completa(),
        }
        for nombre, accion in acciones.items():
            with self.subTest(accion=nombre):
                self._comprobar_guarda_sin_medio(accion)

    def test_reproducir_sin_medio_no_crea_el_reproductor(self):
        panel = self._panel_con_player_vacio()
        player = panel._player
        with mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._toggle_play()
        panel._asegurar_player.assert_not_called()
        self.assertIs(panel._player, player)
        anunciar.assert_called_once_with("No hay ningún vídeo cargado")

    def test_accion_sin_panel_anuncia_indisponible(self):
        from ytchat.ui import gui
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._rep_panel = None
        with mock.patch.object(gui, "anunciar") as anunciar:
            frame._rep_accion("_toggle_play")
        anunciar.assert_called_once_with("El reproductor no está disponible")


class TestRelevoRobustez(unittest.TestCase):
    """Caminos de fallo del relevo de ffmpeg: listener que no llega, ffmpeg
    que muere, VLC en «error», excepción al abrir el medio."""

    INFO = {"is_live": True, "formats": [], "requested_formats": [
        {"vcodec": "avc1", "acodec": "none", "url": "video-solicitado"},
        {"vcodec": "none", "acodec": "mp4a", "url": "audio-solicitado"},
    ]}

    def setUp(self):
        parche = mock.patch.object(reproductor.relevo_ffmpeg, "leer_ventana_hls",
                                   return_value=None)
        parche.start()
        self.addCleanup(parche.stop)

    def _panel(self):
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._info = dict(self.INFO)
        panel._inst = mock.Mock()
        panel._inst.media_new.return_value = mock.Mock()
        panel._player = mock.Mock()
        panel._vol = 75
        panel._muted = False
        panel._timer = mock.Mock()
        panel.lbl_estado = mock.Mock()
        panel._video_id = "vid"
        panel._gen = 0
        panel._relevo_gen = 0
        panel._relevo_ffmpeg = None
        panel._cargando = False
        panel._asegurar_player = mock.Mock(return_value=True)
        panel._error_carga = mock.Mock()
        panel._mostrar_pausa = mock.Mock()
        panel._fijar_estado = mock.Mock()
        panel._detener = mock.Mock()
        panel._topologia_actual = mock.Mock(return_value="relevo")
        return panel

    def _sincrono(self):
        return (
            mock.patch.object(reproductor.diagnostico, "crear_hilo",
                              side_effect=lambda target, _n: mock.Mock(start=target)),
            mock.patch.object(reproductor.wx, "CallAfter",
                              side_effect=lambda fn, *a: fn(*a)),
        )

    def _relevo(self, direccion="tcp://127.0.0.1:5555", listo=True, activo=True):
        relevo = mock.Mock()
        relevo.iniciar.return_value = direccion
        relevo.esperar_listo.return_value = listo
        relevo.activo.return_value = activo
        return relevo

    def test_si_el_listener_no_llega_se_mata_el_relevo_y_cae_a_input_slave(self):
        panel = self._panel()
        relevo = self._relevo(listo=False)
        hilo, callafter = self._sincrono()
        with hilo, callafter, mock.patch.object(
                reproductor.relevo_ffmpeg, "RelevoFfmpeg", return_value=relevo):
            panel._reproducir_calidad(None, reproducir=False)
        relevo.detener.assert_called_once()
        panel._inst.media_new.assert_called_once_with("video-solicitado")
        self.assertIsNone(panel._relevo_ffmpeg)
        self.assertTrue(panel._tiene_esclavo)
        self.assertFalse(panel._cargando)

    def test_si_ffmpeg_murio_antes_del_callback_no_se_usa_su_direccion(self):
        panel = self._panel()
        relevo = self._relevo(activo=False)
        hilo, callafter = self._sincrono()
        with hilo, callafter, mock.patch.object(
                reproductor.relevo_ffmpeg, "RelevoFfmpeg", return_value=relevo):
            panel._reproducir_calidad(None, reproducir=False)
        relevo.detener.assert_called_once()
        panel._inst.media_new.assert_called_once_with("video-solicitado")
        self.assertIsNone(panel._relevo_ffmpeg)

    def test_la_carga_sigue_en_curso_mientras_el_relevo_se_prepara(self):
        panel = self._panel()
        relevo = self._relevo()
        callbacks = []
        with mock.patch.object(reproductor.diagnostico, "crear_hilo",
                               side_effect=lambda target, _n: mock.Mock(start=target)), \
                mock.patch.object(reproductor.wx, "CallAfter",
                                  side_effect=lambda fn, *a: callbacks.append(lambda: fn(*a))), \
                mock.patch.object(reproductor.relevo_ffmpeg, "RelevoFfmpeg",
                                  return_value=relevo):
            panel._reproducir_calidad(None, reproducir=False)
            self.assertTrue(panel._cargando)   # Reproducir no debe relanzar yt-dlp
            callbacks[0]()
        self.assertFalse(panel._cargando)
        self.assertIs(panel._relevo_ffmpeg, relevo)

    def test_excepcion_al_abrir_el_medio_detiene_el_relevo(self):
        panel = self._panel()
        relevo = self._relevo()
        panel._inst.media_new.side_effect = RuntimeError("VLC no abre")
        hilo, callafter = self._sincrono()
        with hilo, callafter, mock.patch.object(
                reproductor.relevo_ffmpeg, "RelevoFfmpeg", return_value=relevo):
            panel._reproducir_calidad(None, reproducir=False)
        relevo.detener.assert_called_once()
        self.assertIsNone(panel._relevo_ffmpeg)
        panel._error_carga.assert_called_once_with()

    def test_error_de_vlc_con_relevo_vivo_reintenta_la_conexion(self):
        panel = self._panel()
        panel._relevo_ffmpeg = self._relevo()
        panel._relevo_reintentos = 0
        with mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._fallo_reproduccion()
        panel._player.play.assert_called_once()
        panel._detener.assert_not_called()
        anunciar.assert_not_called()
        self.assertEqual(panel._relevo_reintentos, 1)

    def test_error_de_vlc_agotados_los_reintentos_para_y_avisa(self):
        panel = self._panel()
        panel._relevo_ffmpeg = self._relevo()
        panel._relevo_reintentos = 3
        with mock.patch.object(reproductor, "anunciar") as anunciar, \
                mock.patch("ytchat.voice.sound_player.reproducir") as sonido:
            panel._fallo_reproduccion()
        panel._player.play.assert_not_called()
        panel._detener.assert_called_once_with(silencioso=True)
        sonido.assert_called_once_with("error")
        anunciar.assert_called_once_with("No se pudo reproducir el vídeo")

    def test_error_de_vlc_sin_relevo_para_y_avisa(self):
        panel = self._panel()
        with mock.patch.object(reproductor, "anunciar") as anunciar, \
                mock.patch("ytchat.voice.sound_player.reproducir"):
            panel._fallo_reproduccion()
        panel._detener.assert_called_once_with(silencioso=True)
        anunciar.assert_called_once_with("No se pudo reproducir el vídeo")

    def test_porcentaje_y_deslizador_con_relevo_remiten_a_los_botones(self):
        panel = self._panel()
        panel._relevo_ffmpeg = self._relevo()
        panel._busqueda_permitida_actual = mock.Mock(return_value=False)
        panel._player.get_length.return_value = 0  # lo que da VLC con el relevo
        panel.sld_pos = mock.Mock()
        with mock.patch.object(reproductor, "anunciar") as anunciar, \
                mock.patch.object(reproductor.logger, "debug") as debug:
            panel._buscar_porcentaje(50)
            panel._on_sld_pos(None)
        self.assertEqual(
            [c.args[0] for c in anunciar.call_args_list],
            ["En este directo solo se puede retroceder o adelantar con los "
             "botones o las flechas"] * 2)
        panel._player.set_time.assert_not_called()
        trazas = [str(c.args[1]) for c in debug.call_args_list]
        self.assertTrue(any(t.startswith("SALTO_RECHAZADO") and "porcentaje" in t
                            for t in trazas))
        self.assertTrue(any("deslizador" in t for t in trazas if t.startswith("SALTO_RECHAZADO")))


class TestSaltoEnRelevo(unittest.TestCase):
    """Retroceder/adelantar en un directo por relevo reinicia ffmpeg con
    desfase respecto al borde del directo (VLC no puede moverse solo)."""

    def _panel(self, desfase=0, ventana=(5.0, 720)):
        panel = TestRelevoRobustez._panel(TestRelevoRobustez())
        panel._relevo_ffmpeg = self._relevo()
        panel._relevo_fuentes = ("video-hls", "audio-hls")
        panel._relevo_desfase = desfase
        panel._relevo_ventana = ventana
        panel._cancelar_busqueda = mock.Mock()
        panel._cancelar_transporte = mock.Mock()
        panel.lbl_tiempo = mock.Mock()
        panel.sld_pos = mock.Mock()
        panel._estado_inicio = mock.Mock()
        return panel

    def _relevo(self):
        relevo = mock.Mock()
        relevo.iniciar.return_value = "tcp://127.0.0.1:6000"
        relevo.esperar_listo.return_value = True
        relevo.activo.return_value = True
        return relevo

    def _sincrono(self):
        return (
            mock.patch.object(reproductor.diagnostico, "crear_hilo",
                              side_effect=lambda target, _n: mock.Mock(start=target)),
            mock.patch.object(reproductor.wx, "CallAfter",
                              side_effect=lambda fn, *a: fn(*a)),
            mock.patch.object(reproductor.relevo_ffmpeg, "leer_ventana_hls",
                              return_value=(5.0, 720)),
            # El debounce del directo vence al instante: cada pulsación
            # reinicia ffmpeg una vez, como antes del debounce.
            mock.patch.object(reproductor.wx, "CallLater",
                              side_effect=lambda _ms, fn, *a: fn(*a)),
        )

    def test_retroceder_un_minuto_reinicia_ffmpeg_doce_segmentos_atras(self):
        panel = self._panel()
        viejo = panel._relevo_ffmpeg
        nuevo = self._relevo()
        hilo, callafter, ventana, debounce = self._sincrono()
        with hilo, callafter, ventana, debounce, \
                mock.patch.object(reproductor.relevo_ffmpeg, "RelevoFfmpeg",
                                  return_value=nuevo) as clase, \
                mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._buscar_rel(-60_000)
        clase.assert_called_once_with("video-hls", "audio-hls", 12)
        viejo.detener.assert_called_once()
        self.assertIs(panel._relevo_ffmpeg, nuevo)
        self.assertEqual(panel._relevo_desfase, 12)
        panel._inst.media_new.assert_called_once_with("tcp://127.0.0.1:6000")
        panel._player.play.assert_called_once()
        panel._player.set_time.assert_not_called()
        # La frase se dice al pulsar, una sola vez; al reconectar no se
        # repite ni se anuncia «Reproduciendo».
        self.assertEqual([c.args[0] for c in anunciar.call_args_list],
                         ["1 minuto por detrás del directo"])
        panel._estado_inicio.cancelar.assert_called()
        panel.lbl_tiempo.SetLabel.assert_called_with("Directo, 1:00 atrás")
        self.assertFalse(panel._cargando)

    def test_los_saltos_se_encadenan_desde_el_desfase_actual(self):
        panel = self._panel(desfase=12)
        nuevo = self._relevo()
        hilo, callafter, ventana, debounce = self._sincrono()
        with hilo, callafter, ventana, debounce, \
                mock.patch.object(reproductor.relevo_ffmpeg, "RelevoFfmpeg",
                                  return_value=nuevo) as clase, \
                mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._buscar_rel(-10_000)
        clase.assert_called_once_with("video-hls", "audio-hls", 14)
        self.assertEqual(anunciar.call_args.args[0],
                         "1 minuto y 10 segundos por detrás del directo")

    def test_adelantar_vuelve_al_directo(self):
        panel = self._panel(desfase=12)
        nuevo = self._relevo()
        hilo, callafter, ventana, debounce = self._sincrono()
        with hilo, callafter, ventana, debounce, \
                mock.patch.object(reproductor.relevo_ffmpeg, "RelevoFfmpeg",
                                  return_value=nuevo) as clase, \
                mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._buscar_rel(+60_000)
        clase.assert_called_once_with("video-hls", "audio-hls", 0)
        self.assertEqual(anunciar.call_args.args[0], "En el directo")
        panel.lbl_tiempo.SetLabel.assert_called_with("En directo")

    def test_adelantar_en_el_borde_avisa_y_no_reinicia(self):
        panel = self._panel(desfase=0)
        with mock.patch.object(reproductor.relevo_ffmpeg, "RelevoFfmpeg") as clase, \
                mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._buscar_rel(+60_000)
        clase.assert_not_called()
        panel._relevo_ffmpeg.detener.assert_not_called()
        anunciar.assert_called_once_with("Ya estás en el directo")

    def test_retroceder_al_final_de_la_ventana_avisa(self):
        from ytchat.player.busqueda_video import MARGEN_VENTANA_SEGMENTOS
        panel = self._panel(desfase=720 - MARGEN_VENTANA_SEGMENTOS)
        with mock.patch.object(reproductor.relevo_ffmpeg, "RelevoFfmpeg") as clase, \
                mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._buscar_rel(-60_000)
        clase.assert_not_called()
        anunciar.assert_called_once_with("No se puede retroceder más en este directo")

    def test_sin_ventana_leida_se_supone_una_corta(self):
        panel = self._panel(ventana=None)
        nuevo = self._relevo()
        hilo, callafter, ventana, debounce = self._sincrono()
        with hilo, callafter, ventana, debounce, \
                mock.patch.object(reproductor.relevo_ffmpeg, "RelevoFfmpeg",
                                  return_value=nuevo) as clase, \
                mock.patch.object(reproductor, "anunciar"):
            panel._buscar_rel(-60_000)
        clase.assert_called_once_with("video-hls", "audio-hls", 12)

    def test_sin_fuentes_en_carga_inicial_anuncia_cargando(self):
        # Sin fuentes todavía no hay con qué reiniciar: es la carga
        # inicial. Con fuentes la pulsación se procesa aunque cargue.
        panel = self._panel()
        panel._cargando = True
        panel._relevo_fuentes = None
        with mock.patch.object(reproductor.relevo_ffmpeg, "RelevoFfmpeg") as clase, \
                mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._saltar_en_relevo(-60_000)
        clase.assert_not_called()
        anunciar.assert_called_once_with("Cargando vídeo")

    def test_si_el_nuevo_relevo_no_arranca_se_avisa_y_se_cae_a_input_slave(self):
        panel = self._panel()
        nuevo = self._relevo()
        nuevo.iniciar.return_value = None
        hilo, callafter, ventana, debounce = self._sincrono()
        with hilo, callafter, ventana, debounce, \
                mock.patch.object(reproductor.relevo_ffmpeg, "RelevoFfmpeg",
                                  return_value=nuevo), \
                mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._buscar_rel(-60_000)
        self.assertEqual([c.args[0] for c in anunciar.call_args_list],
                         ["1 minuto por detrás del directo", "No se pudo mover el directo"])
        self.assertIsNone(panel._relevo_ffmpeg)
        self.assertEqual(panel._relevo_desfase, 0)
        panel._inst.media_new.assert_called_once_with("video-hls")

    def test_la_ventana_se_lee_solo_en_el_primer_arranque(self):
        panel = self._panel()
        nuevo = self._relevo()
        hilo, callafter, ventana, debounce = self._sincrono()
        with hilo, callafter, ventana as leer, debounce, \
                mock.patch.object(reproductor.relevo_ffmpeg, "RelevoFfmpeg",
                                  return_value=nuevo), \
                mock.patch.object(reproductor, "anunciar"):
            panel._buscar_rel(-60_000)
        leer.assert_not_called()   # ya había ventana: no se vuelve a bajar la lista

    def test_detener_olvida_el_desfase_y_las_fuentes(self):
        panel = self._panel(desfase=12)
        panel._timer_progreso = mock.Mock()
        panel._timer = mock.Mock()
        panel._estado_busqueda = mock.Mock(pendiente=False)
        panel._ciclo = None
        panel._detener = reproductor.ReproductorPanel._detener.__get__(panel)
        with mock.patch.object(reproductor, "anunciar"):
            try:
                panel._detener(silencioso=True)
            except Exception:
                pass   # el resto del método toca controles que aquí no existen
        self.assertEqual(panel._relevo_desfase, 0)
        self.assertIsNone(panel._relevo_fuentes)
        self.assertIsNone(panel._relevo_ventana)


class TestDirectoInterrumpido(unittest.TestCase):
    """Cuando ffmpeg termina (fin del directo, URL caducada, corte de red)
    VLC ve un fin de archivo: no es «Fin del vídeo», es una interrupción
    que se intenta recuperar recargando."""

    def _panel(self, relevo=None, is_live=True, recargas=0):
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._player = mock.Mock()
        panel._muted = False
        panel._url_flujo = ""
        panel._video_id = "vid"
        panel._info = {"is_live": is_live}
        panel._relevo_ffmpeg = relevo
        panel._recargas_directo = recargas
        panel._estado_inicio = mock.Mock(requiere=False)
        panel._estado_busqueda = mock.Mock(pendiente=False)
        panel._orden_transporte = None
        panel._timer = mock.Mock()
        panel._estado_vlc_actual = mock.Mock(return_value="ended")
        panel._evaluar_transporte = mock.Mock()
        panel._evaluar_busqueda = mock.Mock()
        panel._detener = mock.Mock()
        panel._fijar_estado = mock.Mock()
        panel.cargar = mock.Mock()
        return panel

    def test_fin_con_relevo_en_directo_avisa_y_recarga_una_vez(self):
        panel = self._panel(relevo=mock.Mock())
        with mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._on_timer(None)
        panel._detener.assert_called_once_with(silencioso=True)
        anunciar.assert_called_once_with("El directo se interrumpió")
        panel.cargar.assert_called_once_with(reproducir=True)
        self.assertEqual(panel._recargas_directo, 1)

    def test_agotadas_las_recargas_no_vuelve_a_intentar(self):
        panel = self._panel(relevo=mock.Mock(),
                            recargas=reproductor.TOPE_RECARGAS_DIRECTO)
        with mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._on_timer(None)
        panel._detener.assert_called_once_with(silencioso=True)
        anunciar.assert_called_once_with("El directo se interrumpió")
        panel.cargar.assert_not_called()
        panel._fijar_estado.assert_called_once_with("El directo se interrumpió.")
        self.assertEqual(panel._recargas_directo, reproductor.TOPE_RECARGAS_DIRECTO)

    def test_fin_sin_relevo_sigue_siendo_fin_del_video(self):
        panel = self._panel(relevo=None, is_live=False)
        with mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._on_timer(None)
        panel._detener.assert_called_once_with(silencioso=True)
        anunciar.assert_called_once_with("Fin del vídeo")
        panel.cargar.assert_not_called()

    def test_cambiar_de_video_reinicia_el_contador(self):
        panel = self._panel(relevo=None, recargas=2)
        panel._listo = True
        panel._ciclo = None
        panel._calidad_sel = None
        panel._alturas = []
        panel.set_video("otro", autoplay=True)
        self.assertEqual(panel._recargas_directo, 0)
        panel.cargar.assert_called_once_with(reproducir=True)


class TestAnchoEstado(unittest.TestCase):
    """Wrap() solo estrecha: hay que partir siempre del texto original."""

    def _panel(self, ancho=500):
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel.lbl_estado = mock.Mock()
        panel.GetClientSize = mock.Mock(return_value=mock.Mock(Width=ancho))
        return panel

    def test_reajustar_parte_del_texto_original(self):
        panel = self._panel()
        panel._fijar_estado("Aviso largo de espera")
        panel.lbl_estado.reset_mock()
        panel._ajustar_ancho_estado()
        self.assertEqual(panel.lbl_estado.method_calls, [
            mock.call.SetLabel("Aviso largo de espera"),
            mock.call.Wrap(460),
        ])

    def test_dos_reajustes_seguidos_no_acumulan_saltos(self):
        panel = self._panel()
        panel._fijar_estado("Aviso largo de espera")
        panel._ajustar_ancho_estado()
        panel._ajustar_ancho_estado()
        # _fijar_estado fija la etiqueta y reajusta (2 SetLabel); cada reajuste
        # posterior vuelve a partir del texto original, nunca del ya partido.
        etiquetas = [c.args[0] for c in panel.lbl_estado.SetLabel.call_args_list]
        self.assertEqual(etiquetas, ["Aviso largo de espera"] * 4)
        panel.lbl_estado.GetLabel.assert_not_called()

    def test_sin_texto_guardado_usa_la_etiqueta_actual(self):
        panel = self._panel()
        panel.lbl_estado.GetLabel.return_value = "Sin reproducir."
        panel._ajustar_ancho_estado()
        panel.lbl_estado.SetLabel.assert_called_once_with("Sin reproducir.")


class TestFmtHablado(unittest.TestCase):
    """La posición hablada conserva el español exacto, también en singular."""

    def test_cero_segundos(self):
        self.assertEqual(reproductor._fmt_hablado(0), "0 segundos")

    def test_un_segundo_en_singular(self):
        self.assertEqual(reproductor._fmt_hablado(1000), "1 segundo")

    def test_varios_segundos_en_plural(self):
        self.assertEqual(reproductor._fmt_hablado(2000), "2 segundos")

    def test_minuto_y_segundo_en_singular(self):
        self.assertEqual(reproductor._fmt_hablado(61_000),
                         "1 minuto 1 segundo")

    def test_hora_con_minutos_en_cero(self):
        self.assertEqual(reproductor._fmt_hablado(3_600_000),
                         "1 hora 0 minutos 0 segundos")

    def test_horas_minutos_y_segundos(self):
        self.assertEqual(reproductor._fmt_hablado(7_322_000),
                         "2 horas 2 minutos 2 segundos")


class TestPosAccesibleTextos(unittest.TestCase):
    """Los tres textos de _PosAccesible pasan por gettext.

    Sin ventana: se arma con __new__ como en test_desfase_accesible.
    """

    def _accesible(self, pos_ms=0, dur_ms=0, frase=None):
        panel = types.SimpleNamespace(
            _pos_ms=pos_ms,
            _dur_ms=dur_ms,
            frase_posicion_directo=frase if frase is not None else lambda: "En directo",
        )
        acc = reproductor._PosAccesible.__new__(reproductor._PosAccesible)
        acc._panel = panel
        return acc

    def test_nombre_sale_marcado(self):
        acc = self._accesible()
        with con_pseudo():
            codigo, texto = acc.GetName(0)
        self.assertEqual(codigo, wx.ACC_OK)
        self.assertTrue(texto.startswith("[¡"), texto)

    def test_valor_con_duracion_sale_marcado(self):
        acc = self._accesible(pos_ms=10_000, dur_ms=60_000)
        with con_pseudo():
            codigo, texto = acc.GetValue(0)
        self.assertEqual(codigo, wx.ACC_OK)
        self.assertTrue(texto.startswith("[¡"), texto)

    def test_valor_en_directo_sale_marcado(self):
        def falla():
            raise RuntimeError("sin frase")
        acc = self._accesible(frase=falla)
        with con_pseudo():
            codigo, texto = acc.GetValue(0)
        self.assertEqual(codigo, wx.ACC_OK)
        self.assertTrue(texto.startswith("[¡"), texto)

    def test_en_espanol_son_identicos(self):
        acc = self._accesible()
        self.assertEqual(acc.GetName(0), (wx.ACC_OK, "Posición de reproducción"))
        acc = self._accesible(pos_ms=10_000, dur_ms=60_000)
        self.assertEqual(
            acc.GetValue(0), (wx.ACC_OK, "10 segundos de 1 minuto 0 segundos"))
        def falla():
            raise RuntimeError("sin frase")
        acc = self._accesible(frase=falla)
        self.assertEqual(acc.GetValue(0), (wx.ACC_OK, "En directo"))


class TestPseudoTextosReproductor(unittest.TestCase):
    """Bajo pseudotraducción, cada frase al usuario sale marcada."""

    def test_avisos_puros_salen_marcados(self):
        with con_pseudo():
            marcados = [
                reproductor.aviso_reproductor(False, False),
                reproductor.aviso_reproductor(True, False),
                reproductor._fmt_hablado(0),
                reproductor._fmt_hablado(1000),
                reproductor._fmt_hablado(61_000),
            ]
        for texto in marcados:
            with self.subTest(texto=texto):
                self.assertTrue(texto.startswith("[¡"), texto)


# El panel lo arma `ytchat/player/reproductor.py`: sus textos quedan
# pendientes en otras ventanas y aquí se exige que no quede ninguno sin
# envolver. La comparación es exacta en los dos sentidos: falla si aparece
# un texto nuevo sin envolver y si un pendiente ya no está en el recorrido.
PENDIENTES_REPRODUCTOR = ()


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoReproductorVentana(unittest.TestCase):
    # Con ventana: la corre el advisor. No correr aquí.

    def setUp(self):
        self.app = wx.App(False) if not wx.App.Get() else wx.App.Get()

    def _panel(self):
        marco = wx.Frame(None)
        self.addCleanup(destruir, marco)
        config = {"mostrar_botones_reproductor": True,
                  "reproductor_solo_audio": False}
        with mock.patch.object(reproductor, "disponible",
                               return_value=True):
            return reproductor.ReproductorPanel(marco, config)

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            panel = self._panel()
            sin_marcar = textos_sin_marcar(panel, propios=("0:00 / 0:00",))
        self.assertEqual(sorted(sin_marcar), sorted(PENDIENTES_REPRODUCTOR))


class TestPseudoAnunciosReproductor(unittest.TestCase):
    """Bajo pseudotraducción, cada anuncio del reproductor sale marcado.

    Sin ventana: paneles con dobles, así se corre acá. Los textos que
    arma otro módulo (`frase_desfase_directo`, `aviso_sin_pausa` y los
    avisos de espera de `progreso`) ya salen marcados de su origen.
    """

    def setUp(self):
        self.captados = []
        parches = [
            mock.patch.object(reproductor, "anunciar", self._guardar),
            mock.patch("ytchat.voice.sound_player.reproducir"),
        ]
        for parche in parches:
            parche.start()
            self.addCleanup(parche.stop)
        pseudo = con_pseudo()
        pseudo.__enter__()
        self.addCleanup(pseudo.__exit__, None, None, None)

    def _guardar(self, frase, *args, **kwargs):
        self.captados.append(frase)

    def _exigir_marcados(self, cantidad):
        self.assertEqual(len(self.captados), cantidad)
        for frase in self.captados:
            self.assertTrue(frase.startswith("[¡"), frase)
        del self.captados[:]

    def _panel(self, **attrs):
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._listo = True
        panel._gen = 0
        panel._video_id = "video-cargado"
        panel._url_flujo = ""
        panel._player = None
        panel._ic_mute = mock.Mock()
        panel._ic_sound = mock.Mock()
        panel._timer_progreso = mock.Mock()
        for clave, valor in attrs.items():
            setattr(panel, clave, valor)
        return panel

    def test_sin_medio_anuncia_marcado(self):
        panel = self._panel(_video_id="", _url_flujo="")
        panel._toggle_play()
        self._exigir_marcados(1)

    def test_sin_reproductor_anuncia_marcado(self):
        panel = self._panel(_listo=False)
        panel._asegurar_player = lambda: False
        panel._toggle_play()
        self._exigir_marcados(1)

    def test_pausar_y_reanudar_anuncian_marcado(self):
        panel = self._panel()
        panel._asegurar_player = lambda: True
        panel._player = mock.Mock()
        panel._orden_transporte = None
        panel._intencion_reproducir = False
        panel._estado_vlc_actual = lambda: "playing"
        panel._mostrar_pausa = mock.Mock()
        panel._timer = mock.Mock()
        panel._toggle_play()
        self._exigir_marcados(1)
        panel._intencion_reproducir = True
        panel._orden_transporte = None
        panel._estado_vlc_actual = lambda: "paused"
        panel._toggle_play()
        self._exigir_marcados(1)

    def test_directo_tiktok_sin_pausa_avisa_marcado(self):
        panel = self._panel(_url_flujo="https://flujo.example/stream.flv")
        panel._asegurar_player = lambda: True
        panel._player = mock.Mock()
        panel._orden_transporte = None
        panel._intencion_reproducir = False
        panel._estado_vlc_actual = lambda: "playing"
        panel._config = {"atajos_raw": {}}
        panel._toggle_play()
        self._exigir_marcados(1)

    def test_pantalla_completa_sin_medio_anuncia_marcado(self):
        panel = self._panel(_video_id="", _url_flujo="", _fs=None)
        panel.alternar_pantalla_completa()
        self._exigir_marcados(1)

    def test_pantalla_completa_ida_y_vuelta_anuncian_marcado(self):
        from ytchat.player.pantalla_completa import AccionesPantalla
        panel = self._panel(_fs=None, _botones_visibles=True)
        panel._asegurar_player = lambda: True
        panel._mapa_atajos_fs = lambda: {}
        panel._fijar_salida = mock.Mock()
        panel._video = mock.Mock()
        panel.btn_play = mock.Mock()
        with mock.patch.object(reproductor, "PantallaCompleta") as clase:
            panel.alternar_pantalla_completa()
            self._exigir_marcados(1)
            panel._fs = clase.return_value
            panel.alternar_pantalla_completa()
            self._exigir_marcados(1)

    def test_silenciar_y_activar_anuncian_marcado(self):
        panel = self._panel(_muted=False)
        panel._player = mock.Mock()
        panel.btn_mute = mock.Mock()
        panel._toggle_mute()
        self._exigir_marcados(1)
        panel._toggle_mute()
        self._exigir_marcados(1)

    def test_detener_anuncia_marcado(self):
        panel = self._panel()
        panel._timer_progreso = mock.Mock()
        panel._detener()
        self._exigir_marcados(1)

    def test_volumen_anuncia_nombre_y_valor_marcados(self):
        from ytchat.core import anuncio_ajuste
        compartido = anuncio_ajuste.COMPARTIDO
        ultimo, hora = compartido._ultimo, compartido._hora
        self.addCleanup(setattr, compartido, "_ultimo", ultimo)
        self.addCleanup(setattr, compartido, "_hora", hora)
        compartido._ultimo, compartido._hora = "otro_control", 0.0
        panel = self._panel(_vol=50)
        panel.sld_vol = mock.Mock()
        panel._player = None
        panel.ajustar_volumen(+20)
        self._exigir_marcados(1)
        panel.ajustar_volumen(+1)
        self._exigir_marcados(1)

    def test_calidades_anuncian_marcado(self):
        panel = self._panel(_calidad_sel=None, _info=None)
        panel.set_calidad(None)
        self._exigir_marcados(1)
        panel.set_calidad(720)
        self._exigir_marcados(1)

    def test_cargar_sin_reproductor_anuncia_marcado(self):
        panel = self._panel(_listo=False)
        panel._asegurar_player = lambda: False
        panel.cargar()
        self._exigir_marcados(1)

    def test_cargar_en_curso_anuncia_marcado(self):
        panel = self._panel(_cargando=True)
        panel._asegurar_player = lambda: True
        panel.cargar()
        self._exigir_marcados(1)

    def test_cargar_anuncia_marcado(self):
        from ytchat.player.busqueda_video import EstadoBusqueda
        panel = self._panel(_cargando=False)
        panel._asegurar_player = lambda: True
        panel._estado_busqueda = EstadoBusqueda(confirmada=0)
        panel._estado_inicio = mock.Mock()
        panel._timer_progreso = mock.Mock()
        panel._fijar_estado = mock.Mock()
        with mock.patch.object(reproductor.diagnostico, "crear_hilo"):
            panel.cargar()
        self._exigir_marcados(1)

    def test_error_de_carga_anuncia_marcado(self):
        panel = self._panel()
        panel._estado_inicio = mock.Mock()
        panel._timer_progreso = mock.Mock()
        panel._fijar_estado = mock.Mock()
        panel._error_carga()
        self._exigir_marcados(1)

    def test_progreso_de_carga_anuncia_marcado(self):
        panel = self._panel(_cargando=True,
                            _inicio_progreso=time.monotonic() - 5.0,
                            _ultimo_aviso_progreso=None)
        panel._fijar_estado = mock.Mock()
        panel._on_timer_progreso(None)
        self._exigir_marcados(1)

    def test_transporte_confirmado_anuncia_marcado(self):
        from ytchat.player.busqueda_video import OrdenTransporte
        panel = self._panel()
        panel._mostrar_pausa = mock.Mock()
        panel._timer = mock.Mock()
        panel._orden_transporte = OrdenTransporte(intencion_reproducir=False,
                                                 instante=time.monotonic())
        panel._evaluar_transporte(estado_forzado="paused")
        self._exigir_marcados(1)
        panel._orden_transporte = OrdenTransporte(intencion_reproducir=True,
                                                 instante=time.monotonic())
        panel._evaluar_transporte(estado_forzado="playing")
        self._exigir_marcados(1)

    def test_transporte_fallido_anuncia_marcado(self):
        from ytchat.player.busqueda_video import OrdenTransporte
        panel = self._panel()
        panel._mostrar_pausa = mock.Mock()
        panel._timer = mock.Mock()
        panel._orden_transporte = OrdenTransporte(intencion_reproducir=False,
                                                 instante=time.monotonic() - 10.0)
        panel._estado_vlc_actual = lambda: "playing"
        panel._evaluar_transporte(estado_forzado="opening")
        self._exigir_marcados(1)
        panel._orden_transporte = OrdenTransporte(intencion_reproducir=True,
                                                 instante=time.monotonic() - 10.0)
        panel._estado_vlc_actual = lambda: "paused"
        panel._evaluar_transporte(estado_forzado="opening")
        self._exigir_marcados(1)

    def test_transitorio_y_sin_barra_anuncian_marcado(self):
        panel = self._panel(_cargando=True)
        panel._estado_vlc_actual = lambda: "playing"
        panel._aviso_transitorio()
        self._exigir_marcados(1)
        panel = self._panel(_cargando=False)
        panel._estado_vlc_actual = lambda: "stopped"
        panel._aviso_transitorio()
        self._exigir_marcados(1)
        panel = self._panel(_cargando=False,
                            _url_flujo="https://flujo.example/stream.flv")
        panel._estado_vlc_actual = lambda: "playing"
        panel._aviso_sin_barra()
        self._exigir_marcados(1)
        panel = self._panel(_cargando=False)
        panel._estado_vlc_actual = lambda: "playing"
        panel._aviso_sin_barra()
        self._exigir_marcados(1)

    def test_busqueda_no_permitida_anuncia_marcado(self):
        panel = self._panel(_cargando=False, _relevo_ffmpeg=mock.Mock())
        panel._es_directo_actual = lambda: True
        panel._estado_vlc_actual = lambda: "playing"
        panel._aviso_busqueda_no_permitida()
        self._exigir_marcados(1)
        panel = self._panel(_cargando=False, _relevo_ffmpeg=None,
                            _url_flujo="https://flujo.example/stream.flv")
        panel._es_directo_actual = lambda: True
        panel._estado_vlc_actual = lambda: "playing"
        panel._aviso_busqueda_no_permitida()
        self._exigir_marcados(1)
        panel = self._panel(_cargando=False, _relevo_ffmpeg=None)
        panel._es_directo_actual = lambda: True
        panel._estado_vlc_actual = lambda: "playing"
        panel._aviso_busqueda_no_permitida()
        self._exigir_marcados(1)
        panel = self._panel(_cargando=False, _relevo_ffmpeg=None)
        panel._es_directo_actual = lambda: False
        panel._estado_vlc_actual = lambda: "playing"
        panel._aviso_busqueda_no_permitida()
        self._exigir_marcados(1)

    def test_salto_en_relevo_anuncia_marcado(self):
        from ytchat.player.busqueda_video import (
            MARGEN_VENTANA_SEGMENTOS, EstadoBusqueda)
        tope = 720 - MARGEN_VENTANA_SEGMENTOS
        panel = self._panel(_relevo_fuentes=None)
        panel._saltar_en_relevo(-60_000)
        self._exigir_marcados(1)
        panel = self._panel(_relevo_fuentes=("video", "audio"),
                            _relevo_ventana=(5.0, 720), _relevo_desfase=0)
        panel._saltar_en_relevo(+60_000)
        self._exigir_marcados(1)
        panel = self._panel(_relevo_fuentes=("video", "audio"),
                            _relevo_ventana=(5.0, 720), _relevo_desfase=tope)
        panel._saltar_en_relevo(-60_000)
        self._exigir_marcados(1)
        panel = self._panel(_relevo_fuentes=("video", "audio"),
                            _relevo_ventana=(5.0, 720), _relevo_desfase=0)
        panel._estado_busqueda = EstadoBusqueda(confirmada=0)
        with mock.patch.object(reproductor.wx, "CallLater"):
            panel._saltar_en_relevo(+60_000)
        self._exigir_marcados(1)

    def test_ir_al_directo_anuncia_marcado(self):
        panel = self._panel()
        panel._es_directo_actual = lambda: False
        panel.ir_al_directo()
        self._exigir_marcados(1)
        panel = self._panel(_relevo_fuentes=("video", "audio"),
                            _relevo_desfase=0)
        panel._es_directo_actual = lambda: True
        panel.ir_al_directo()
        self._exigir_marcados(1)
        panel = self._panel(_relevo_fuentes=None)
        panel._es_directo_actual = lambda: True
        panel.ir_al_directo()
        self._exigir_marcados(1)
        panel = self._panel(_relevo_fuentes=("video", "audio"),
                            _relevo_ventana=(5.0, 720), _relevo_desfase=12)
        panel._es_directo_actual = lambda: True
        with mock.patch.object(reproductor.wx, "CallLater"):
            panel.ir_al_directo()
        self._exigir_marcados(1)

    def test_mover_y_posicion_anuncian_marcado(self):
        from ytchat.player.busqueda_video import EstadoBusqueda
        panel = self._panel(_vod_por_relevo=True,
                            _relevo_vod_base_ms=None)
        panel._estado_busqueda = EstadoBusqueda(confirmada=0)
        panel._estado_vlc_actual = lambda: "playing"
        panel._duracion_actual = lambda: 600_000
        panel._fijar_tiempo = mock.Mock()
        panel._timer = mock.Mock()
        panel._marcar_destino(300_000)
        self._exigir_marcados(1)
        bus = mock.Mock()
        bus.pendiente = True
        bus.destino = 300_000
        bus.confirmada = 0
        bus.candidato = None
        bus.edad_ms = mock.Mock(return_value=10)
        bus.observar = mock.Mock(return_value=("confirmado", 5_000))
        panel._estado_busqueda = bus
        panel.sld_pos = mock.Mock()
        with mock.patch.object(reproductor.wx.Window, "FindFocus",
                               return_value=None):
            panel._evaluar_busqueda()
        self._exigir_marcados(1)
        bus.observar = mock.Mock(return_value=("fallo", None))
        with mock.patch.object(reproductor.wx.Window, "FindFocus",
                               return_value=None):
            panel._evaluar_busqueda()
        self._exigir_marcados(1)

    def test_deslizador_y_porcentaje_mueven_y_anuncian_marcado(self):
        from ytchat.player.busqueda_video import EstadoBusqueda
        panel = self._panel(_vod_por_relevo=False)
        panel._player = mock.Mock()
        panel._estado_busqueda = EstadoBusqueda(confirmada=0)
        panel._busqueda_permitida_actual = lambda: True
        panel._duracion_actual = lambda: 600_000
        panel._fijar_tiempo = mock.Mock()
        panel._timer = mock.Mock()
        panel.sld_pos = mock.Mock()
        panel.sld_pos.GetValue.return_value = 500
        panel._on_sld_pos(None)
        self._exigir_marcados(1)
        panel._estado_busqueda = EstadoBusqueda(confirmada=0)
        panel._buscar_porcentaje(50)
        self._exigir_marcados(1)

    def test_fin_de_flujo_anuncia_marcado(self):
        from ytchat.player.busqueda_video import EstadoBusqueda
        panel = self._panel()
        panel._timer_progreso = mock.Mock()
        panel._duracion_actual = lambda: 600_000
        panel._estado_busqueda = EstadoBusqueda(confirmada=599_000)
        panel._relevo_vod_ultima = None
        panel._relevo_vod_base_ms = None
        panel._pos_ms = 0
        panel._relevo_vod_recuperaciones = 0
        panel._fin_flujo_vod()
        self._exigir_marcados(1)
        panel = self._panel()
        panel._timer_progreso = mock.Mock()
        panel._duracion_actual = lambda: 600_000
        panel._estado_busqueda = EstadoBusqueda(confirmada=100_000)
        panel._relevo_vod_ultima = 100_000
        panel._relevo_vod_base_ms = 0
        panel._relevo_fuentes = ("video", "audio")
        panel._pos_ms = 0
        panel._relevo_vod_recuperaciones = 2
        panel._fin_flujo_vod()
        self._exigir_marcados(1)

    def test_fallo_de_reproduccion_y_reintento_anuncian_marcado(self):
        panel = self._panel(_vod_por_relevo=False, _relevo_ffmpeg=None,
                            _relevo_reintentos=0)
        panel._timer_progreso = mock.Mock()
        panel._fijar_estado = mock.Mock()
        panel._fallo_reproduccion()
        self._exigir_marcados(1)
        panel = self._panel(_recargas_apertura=1)
        panel._timer_progreso = mock.Mock()
        panel._fijar_estado = mock.Mock()
        panel._recargar_apertura_vod()
        self._exigir_marcados(1)
        panel = self._panel()
        panel._timer_progreso = mock.Mock()
        panel._fijar_estado = mock.Mock()
        panel._avisar_fallo(reproductor._("falla de mentira"))
        self.assertTrue(panel._fijar_estado.call_args.args[0].startswith("[¡"))
        self._exigir_marcados(1)

    def test_directo_interrumpido_anuncia_marcado(self):
        panel = self._panel(_recargas_directo=0)
        panel._timer_progreso = mock.Mock()
        panel.cargar = mock.Mock()
        panel._directo_interrumpido()
        self._exigir_marcados(1)
        panel = self._panel(_recargas_directo=2)
        panel._timer_progreso = mock.Mock()
        panel._fijar_estado = mock.Mock()
        panel._directo_interrumpido()
        self.assertTrue(panel._fijar_estado.call_args.args[0].startswith("[¡"))
        self._exigir_marcados(1)

    def test_tiktok_terminado_y_fallo_de_apertura_anuncian_marcado(self):
        from ytchat.player.busqueda_video import EstadoInicioReproduccion
        panel = self._panel()
        panel._timer_progreso = mock.Mock()
        inicio = EstadoInicioReproduccion()
        inicio.iniciar()
        inicio._anunciado = True
        panel._estado_inicio = inicio
        panel._terminar_flujo_tiktok()
        self._exigir_marcados(1)
        panel = self._panel(_aviso_fallo_flujo=False)
        panel._timer_progreso = mock.Mock()
        panel._fijar_estado = mock.Mock()
        panel._estado_inicio = mock.Mock(anunciado=False, primera=None)
        with mock.patch.object(reproductor.flujo_tiktok, "sondear_en_hilo"):
            panel._terminar_flujo_tiktok()
        self._exigir_marcados(1)

    def test_cierre_anuncia_marcado(self):
        panel = self._panel()
        panel.lbl_estado = mock.Mock()
        panel._fijar_estado = mock.Mock()
        panel._mostrar_estado_cerrando(True)
        self.assertTrue(panel._fijar_estado.call_args.args[0].startswith("[¡"))
        self._exigir_marcados(1)
        panel._mostrar_estado_cerrando(False)
        self.assertEqual(self.captados, [])

    def test_etiquetas_y_frases_salen_marcadas(self):
        panel = self._panel(_botones_visibles=True)
        with self.subTest(etiqueta="ocultar"):
            self.assertTrue(panel._etiqueta_toggle().startswith("[¡"))
        panel._botones_visibles = False
        with self.subTest(etiqueta="mostrar"):
            self.assertTrue(panel._etiqueta_toggle().startswith("[¡"))
        panel = self._panel(_relevo_ffmpeg=mock.Mock(),
                            _relevo_desfase=5, _relevo_ventana=(5.0, 720))
        panel._es_directo_actual = lambda: True
        with self.subTest(etiqueta="directo"):
            self.assertTrue(panel._etiqueta_directo().startswith("[¡"))
        panel._relevo_ffmpeg = None
        with self.subTest(etiqueta="en directo"):
            self.assertTrue(panel._etiqueta_directo().startswith("[¡"))
        panel._relevo_fuentes = ("video", "audio")
        panel._relevo_desfase = 5
        with self.subTest(frase="desfase"):
            self.assertTrue(panel.frase_posicion_directo().startswith("[¡"))
        panel._relevo_fuentes = None
        with self.subTest(frase="en directo"):
            self.assertTrue(panel.frase_posicion_directo().startswith("[¡"))

    def test_relevo_listo_refleja_el_anuncio_marcado(self):
        from ytchat.player.busqueda_video import frase_desfase_directo
        panel = self._panel(_gen=3, _relevo_gen=5, _video_id="vid")
        panel._continuar_reproducir_calidad = mock.Mock()
        panel._fijar_estado = mock.Mock()
        panel._fijar_tiempo = mock.Mock()
        panel._estado_inicio = mock.Mock()
        frase = frase_desfase_directo(60.0)
        panel._relevo_listo(mock.Mock(), "http://relevo.example/x", 5, 3,
                            "vid", "video", "", True, anuncio=frase)
        self.assertTrue(panel._fijar_estado.call_args.args[0].startswith("[¡"))
        self.assertEqual(self.captados, [])
        panel._relevo_listo(mock.Mock(), None, 5, 3, "vid", "video", "",
                            True, anuncio=frase)
        self._exigir_marcados(1)

    def test_inicio_de_reproduccion_anuncia_marcado(self):
        from types import SimpleNamespace
        from ytchat.player.busqueda_video import (
            EstadoBusqueda, EstadoInicioReproduccion)
        panel = self._panel(_muted=False, _vol=80, _vod_por_relevo=False,
                            _relevo_vod_base_ms=None)
        panel._player = mock.Mock()
        panel._player.get_state.return_value = SimpleNamespace(name="Playing")
        panel._player.audio_get_volume.return_value = 80
        panel._player.get_time.return_value = 500
        panel._player.get_length.return_value = 600_000
        inicio = EstadoInicioReproduccion()
        inicio.iniciar()
        inicio._primera = 0
        panel._estado_inicio = inicio
        panel._marca_reproduccion = time.monotonic() - 2.0
        panel._marca_extraccion = time.monotonic() - 1.0
        panel._marca_url = time.monotonic() - 1.0
        panel._estado_busqueda = EstadoBusqueda(confirmada=0)
        panel._orden_transporte = None
        panel._fijar_estado = mock.Mock()
        panel._fijar_tiempo = mock.Mock()
        panel.sld_pos = mock.Mock()
        with mock.patch.object(reproductor.wx.Window, "FindFocus",
                               return_value=None):
            panel._on_timer(mock.Mock())
        self._exigir_marcados(1)


if __name__ == "__main__":
    unittest.main()
