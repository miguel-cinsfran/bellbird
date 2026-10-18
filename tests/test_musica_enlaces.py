"""Pruebas de los enlaces de YouTube para la música (`enlaces.py`).

Todo lo que toca yt-dlp va con el programa o el módulo parcheados: sin red.
Las pruebas reales contra YouTube solo corren con `YTCHAT_PRUEBAS_RED=1`.
"""

import json
import os
import threading
import time
import unittest
from unittest import mock

from ytchat.music import enlaces
from ytchat.music.enlaces import ErrorEnlace
from ytchat.music.modelo import Tema
from ytchat.player import motor_vlc

_HABIL_RED = os.environ.get("YTCHAT_PRUEBAS_RED") == "1"

VIDEO = "jNQXAC9IVRw"
LISTA = "PLbpi6ZahtOH71mwANLzAlPX9cZafnzIqt"


class TestReconocerDirecciones(unittest.TestCase):

    def test_acepta_las_formas_de_youtube(self):
        for texto in (
            "https://www.youtube.com/watch?v=abc123",
            "youtube.com/watch?v=abc123",
            "https://youtu.be/abc123",
            "www.youtube.com/shorts/abc123",
            "https://music.youtube.com/watch?v=abc123",
            "https://www.youtube.com/playlist?list=PLabc123",
            "https://youtu.be/abc123?list=PLabc123",
            "HTTPS://WWW.YOUTUBE.COM/WATCH?V=abc123",
        ):
            with self.subTest(texto=texto):
                self.assertTrue(enlaces.es_enlace_youtube(texto))

    def test_rechaza_lo_que_no_es_youtube(self):
        for texto in (
            "", "   ", None, 123, "no es una url",
            "https://vimeo.com/12345",
            "https://youtube.com/",
            "https://youtube.com/@un-canal",
            "https://example.com/youtube.com/watch?v=abc123",
        ):
            with self.subTest(texto=texto):
                self.assertFalse(enlaces.es_enlace_youtube(texto))

    def test_id_de_url(self):
        self.assertEqual(
            enlaces.id_de_url("https://www.youtube.com/watch?v=abc123"), "abc123")
        self.assertEqual(enlaces.id_de_url("https://youtu.be/abc123"), "abc123")
        self.assertEqual(
            enlaces.id_de_url("https://www.youtube.com/shorts/abc123"), "abc123")
        self.assertEqual(
            enlaces.id_de_url("https://music.youtube.com/watch?v=abc123"), "abc123")
        self.assertEqual(
            enlaces.id_de_url("https://www.youtube.com/playlist?list=PL1"), "")
        self.assertEqual(enlaces.id_de_url(""), "")
        self.assertEqual(enlaces.id_de_url(None), "")


class TestTemasDeInfo(unittest.TestCase):

    def test_video_suelto(self):
        datos = {"id": "abc123", "title": "Una canción"}
        self.assertEqual(
            enlaces.temas_de_info(datos),
            (Tema("https://www.youtube.com/watch?v=abc123", "Una canción"),))

    def test_video_sin_titulo_usa_el_id(self):
        self.assertEqual(
            enlaces.temas_de_info({"id": "abc123"}),
            (Tema("https://www.youtube.com/watch?v=abc123", "abc123"),))

    def test_lista_en_orden(self):
        datos = {"entries": [
            {"id": "uno", "title": "Primera"},
            {"id": "dos", "title": "Segunda"},
        ]}
        self.assertEqual(
            enlaces.temas_de_info(datos),
            (Tema("https://www.youtube.com/watch?v=uno", "Primera"),
             Tema("https://www.youtube.com/watch?v=dos", "Segunda")))

    def test_salta_entradas_sin_id(self):
        datos = {"entries": [
            {"id": "uno", "title": "Primera"},
            {"title": "Privada"},
            None,
            {"id": "", "title": "Borrada"},
            {"id": "dos", "title": "Segunda"},
        ]}
        self.assertEqual([t.titulo for t in enlaces.temas_de_info(datos)],
                         ["Primera", "Segunda"])

    def test_vacio_o_no_dict(self):
        self.assertEqual(enlaces.temas_de_info(None), ())
        self.assertEqual(enlaces.temas_de_info([]), ())
        self.assertEqual(enlaces.temas_de_info({"entries": []}), ())
        self.assertEqual(enlaces.temas_de_info({"title": "sin id"}), ())


def _json_lista():
    return json.dumps({"entries": [
        {"id": "uno", "title": "Primera"},
        {"id": "dos", "title": "Segunda"},
    ]})


class TestExpandir(unittest.TestCase):

    def test_con_programa_usa_flat_playlist_y_tope(self):
        salida = mock.Mock(returncode=0, stdout=_json_lista())
        with mock.patch.object(enlaces.ytdlp_bin, "ruta_ytdlp",
                               return_value=r"C:\yt-dlp.exe"), \
                mock.patch.object(enlaces.subprocess, "run",
                                  return_value=salida) as correr:
            temas = enlaces.expandir("https://www.youtube.com/playlist?list=PL1")
        self.assertEqual([t.titulo for t in temas], ["Primera", "Segunda"])
        argumentos = correr.call_args.args[0]
        self.assertEqual(argumentos[0], r"C:\yt-dlp.exe")
        self.assertIn("--flat-playlist", argumentos)
        self.assertIn("-J", argumentos)
        self.assertIn("--no-warnings", argumentos)
        self.assertEqual(argumentos[-1],
                         "https://www.youtube.com/playlist?list=PL1")
        self.assertEqual(correr.call_args.kwargs.get("timeout"),
                         enlaces.TOPE_PROGRAMA)

    def test_con_programa_y_codigo_de_error(self):
        salida = mock.Mock(returncode=1, stdout="")
        with mock.patch.object(enlaces.ytdlp_bin, "ruta_ytdlp",
                               return_value=r"C:\yt-dlp.exe"), \
                mock.patch.object(enlaces.subprocess, "run", return_value=salida):
            with self.assertRaises(ErrorEnlace) as caso:
                enlaces.expandir("https://youtu.be/abc123")
        self.assertIn("No se pudo leer el enlace", str(caso.exception))

    def test_con_programa_que_se_pasa_del_tope(self):
        import subprocess
        with mock.patch.object(enlaces.ytdlp_bin, "ruta_ytdlp",
                               return_value=r"C:\yt-dlp.exe"), \
                mock.patch.object(enlaces.subprocess, "run",
                                  side_effect=subprocess.TimeoutExpired("x", 60)):
            with self.assertRaises(ErrorEnlace):
                enlaces.expandir("https://youtu.be/abc123")

    def test_con_modulo(self):
        datos = {"id": "abc123", "title": "Una canción"}
        with mock.patch.object(enlaces.ytdlp_bin, "ruta_ytdlp",
                               return_value=None), \
                mock.patch.object(enlaces, "_extraer_plano_con_modulo",
                                  return_value=datos):
            temas = enlaces.expandir("https://youtu.be/abc123")
        self.assertEqual(temas,
                         (Tema("https://www.youtube.com/watch?v=abc123",
                               "Una canción"),))

    def test_sin_videos_lanza(self):
        datos = {"entries": []}
        with mock.patch.object(enlaces.ytdlp_bin, "ruta_ytdlp",
                               return_value=None), \
                mock.patch.object(enlaces, "_extraer_plano_con_modulo",
                                  return_value=datos):
            with self.assertRaises(ErrorEnlace) as caso:
                enlaces.expandir("https://youtu.be/abc123")
        self.assertIn("El enlace no tiene vídeos", str(caso.exception))


class TestUrlAudio(unittest.TestCase):

    def test_con_programa(self):
        info = {"formats": [
            {"vcodec": "none", "acodec": "mp4a", "url": "audio-https",
             "language_preference": 10},
        ]}
        with mock.patch.object(enlaces.ytdlp_bin, "ruta_ytdlp",
                               return_value=r"C:\yt-dlp.exe"), \
                mock.patch.object(enlaces.ytdlp_bin, "info_video",
                                  return_value=info) as pedir:
            url = enlaces.url_audio("https://www.youtube.com/watch?v=abc123")
        self.assertEqual(url, "audio-https")
        pedir.assert_called_once_with("abc123")

    def test_con_modulo(self):
        info = {"formats": [
            {"vcodec": "none", "acodec": "mp4a", "url": "audio-https"},
        ]}
        with mock.patch.object(enlaces.ytdlp_bin, "ruta_ytdlp",
                               return_value=None), \
                mock.patch.object(enlaces, "_extraer_video_con_modulo",
                                  return_value=info):
            url = enlaces.url_audio("https://youtu.be/abc123")
        self.assertEqual(url, "audio-https")

    def test_sin_audio_lanza(self):
        with mock.patch.object(enlaces.ytdlp_bin, "ruta_ytdlp",
                               return_value=None), \
                mock.patch.object(enlaces, "_extraer_video_con_modulo",
                                  return_value={"formats": []}):
            with self.assertRaises(ErrorEnlace):
                enlaces.url_audio("https://youtu.be/abc123")

    def test_origen_sin_id_lanza(self):
        with self.assertRaises(ErrorEnlace):
            enlaces.url_audio("https://www.youtube.com/playlist?list=PL1")

    def test_el_programa_no_devuelve_datos_lanza(self):
        with mock.patch.object(enlaces.ytdlp_bin, "ruta_ytdlp",
                               return_value=r"C:\yt-dlp.exe"), \
                mock.patch.object(enlaces.ytdlp_bin, "info_video",
                                  return_value=None):
            with self.assertRaises(ErrorEnlace):
                enlaces.url_audio("https://youtu.be/abc123")


@unittest.skipUnless(_HABIL_RED,
                     "pruebas de red desactivadas (YTCHAT_PRUEBAS_RED=1)")
class TestEnlacesRed(unittest.TestCase):
    """Reales contra YouTube. Solo las corre el advisor con la variable."""

    def test_expandir_un_video(self):
        temas = enlaces.expandir(f"https://www.youtube.com/watch?v={VIDEO}")
        self.assertEqual(len(temas), 1)
        self.assertEqual(temas[0].origen,
                         f"https://www.youtube.com/watch?v={VIDEO}")
        self.assertTrue(temas[0].titulo)

    def test_expandir_una_lista(self):
        temas = enlaces.expandir(
            f"https://www.youtube.com/playlist?list={LISTA}")
        self.assertGreaterEqual(len(temas), 1)
        for tema in temas:
            self.assertTrue(tema.origen.startswith(
                "https://www.youtube.com/watch?v="))
            self.assertTrue(tema.titulo)

    def test_url_audio_de_un_video(self):
        url = enlaces.url_audio(f"https://www.youtube.com/watch?v={VIDEO}")
        self.assertTrue(url.startswith("http"))


def esperar(condicion, plazo=30.0):
    fin = time.monotonic() + plazo
    while time.monotonic() < fin:
        if condicion():
            return True
        time.sleep(0.05)
    return condicion()


@unittest.skipUnless(_HABIL_RED,
                     "pruebas de red desactivadas (YTCHAT_PRUEBAS_RED=1)")
@unittest.skipUnless(motor_vlc.disponible(), "libVLC no está disponible")
class TestAdaptadorPorEnlaceReal(unittest.TestCase):
    """Reproduce un vídeo de YouTube por enlace con libVLC y «adummy»."""

    def test_reproduce_y_avisa_sonando(self):
        from ytchat.music.adaptador_vlc import AdaptadorVlc
        adaptador = AdaptadorVlc(salida_audio="adummy")
        self.addCleanup(adaptador.cerrar)
        terminado = threading.Event()

        def aviso(ficha, fallo):
            terminado.set()

        adaptador.asignar_aviso(aviso)
        adaptador.cargar(
            Tema(f"https://www.youtube.com/watch?v={VIDEO}", "Me at the zoo"), 1)
        sonando = esperar(
            lambda: adaptador._actual is not None
            and adaptador._actual.is_playing())
        self.assertTrue(sonando, "no llegó a sonar en 30 s")
        self.assertFalse(terminado.is_set(), "terminó en vez de sonar")


if __name__ == "__main__":
    unittest.main()
