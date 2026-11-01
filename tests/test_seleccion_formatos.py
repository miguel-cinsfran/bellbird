"""Selección de formatos para el VOD por relevo.

El relevo de ffmpeg no tolera audio HLS por TCP, así que el VOD evita las
pistas m3u8 cuando hay alternativas normales. El directo no cambia.
"""

import unittest
from unittest import mock

from bellbird.player import formatos_youtube
from bellbird.player import reproductor
from bellbird.player.formatos import mejor_audio_estereo
from bellbird.player.formatos_youtube import _video_para_altura
from bellbird.player.formatos_youtube import espera_para_abrir


def _audio(fid, protocolo, abr, lang, url=None, acodec="mp4a", ext=None):
    pista = {"format_id": fid, "protocol": protocolo, "acodec": acodec,
             "vcodec": "none", "abr": abr, "language_preference": lang,
             "url": url or f"https://{fid}"}
    if ext is not None:
        pista["ext"] = ext
    return pista


class PruebasMejorAudioSinHls(unittest.TestCase):
    def _info_j906(self):
        return {"formats": [
            _audio("233", "m3u8_native", 48, None),
            _audio("234", "m3u8_native", 120, None),
            _audio("140", "https", 128, -1, ext="m4a"),
            _audio("251", "https", 160, -1, acodec="opus", ext="webm"),
        ]}

    def test_evitando_hls_elige_140_m4a_aunque_251_tenga_mas_bitrate(self):
        url = reproductor._mejor_audio(self._info_j906(), evitar_hls=True)
        self.assertEqual(url, "https://140")

    def test_sin_evitando_hls_elige_una_hls_como_hoy(self):
        url = reproductor._mejor_audio(self._info_j906())
        self.assertIn(url, ("https://233", "https://234"))

    def test_doblaje_gana_la_original_aunque_tenga_menos_bitrate(self):
        info = {"formats": [
            _audio("dub", "https", 200, -1, ext="m4a"),
            _audio("orig", "https", 128, 10, acodec="opus", ext="webm"),
        ]}
        url = reproductor._mejor_audio(info, evitar_hls=True)
        self.assertEqual(url, "https://orig")

    def test_webm_original_gana_a_m4a_doblado(self):
        info = {"formats": [
            _audio("dub-m4a", "https", 200, -1, ext="m4a"),
            _audio("orig-webm", "https", 128, 10, acodec="opus",
                   ext="webm"),
        ]}
        url = reproductor._mejor_audio(info, evitar_hls=True)
        self.assertEqual(url, "https://orig-webm")

    def test_m4a_original_gana_a_webm_original_con_mas_bitrate(self):
        info = {"formats": [
            _audio("orig-webm", "https", 160, 10, acodec="opus",
                   ext="webm"),
            _audio("orig-m4a", "https", 128, 10, ext="m4a"),
        ]}
        url = reproductor._mejor_audio(info, evitar_hls=True)
        self.assertEqual(url, "https://orig-m4a")

    def test_sin_evitando_hls_el_orden_es_el_de_antes(self):
        info = {"formats": [
            _audio("m4a", "https", 128, 10, ext="m4a"),
            _audio("webm", "https", 160, 10, acodec="opus", ext="webm"),
        ]}
        url = reproductor._mejor_audio(info)
        self.assertEqual(url, "https://webm")

    def test_solo_hls_devuelve_una_hls(self):
        info = {"formats": [
            _audio("233", "m3u8_native", 48, None),
            _audio("234", "m3u8_native", 120, None),
        ]}
        url = reproductor._mejor_audio(info, evitar_hls=True)
        self.assertIn(url, ("https://233", "https://234"))


class PruebasMejorAudioEstereo(unittest.TestCase):
    """El solo audio evita las pistas multicanal y las HLS."""

    def test_descarta_la_multicanal_si_hay_estereo(self):
        info = {"formats": [
            _pista_audio("https://258", 0, "m4a", "mp4a", 384, canales=6),
            _pista_audio("https://140", 0, "m4a", "mp4a", 128, canales=2),
        ]}
        self.assertEqual(mejor_audio_estereo(info), "https://140")

    def test_doblaje_estereo_no_gana_a_la_original(self):
        info = {"formats": [
            _pista_audio("https://doblaje", 0, "m4a", "mp4a", 200,
                         canales=2, lang=-1),
            _pista_audio("https://original", 0, "webm", "opus", 128,
                         canales=2, lang=10),
        ]}
        self.assertEqual(mejor_audio_estereo(info), "https://original")

    def test_sin_estereo_usa_las_demas_que_no_son_hls(self):
        info = {"formats": [
            _pista_audio("https://258", 0, "webm", "opus", 384, canales=6),
            _pista_audio("https://hls", 0, "m4a", "mp4a", 128, canales=2,
                         protocolo="m3u8_native"),
        ]}
        self.assertEqual(mejor_audio_estereo(info), "https://258")

    def test_solo_hls_devuelve_vacio(self):
        info = {"formats": [
            _pista_audio("https://hls", 0, "m4a", "mp4a", 128, canales=2,
                         protocolo="m3u8_native"),
        ]}
        self.assertEqual(mejor_audio_estereo(info), "")


class PruebasVideoParaAlturaSinHls(unittest.TestCase):
    def test_a_720_prefiere_136_https_antes_que_232_hls(self):
        info = {"formats": [
            {"format_id": "232", "protocol": "m3u8_native", "vcodec": "avc",
             "acodec": "none", "height": 720, "tbr": 3000,
             "url": "https://232"},
            {"format_id": "136", "protocol": "https", "vcodec": "avc",
             "acodec": "none", "height": 720, "tbr": 1500,
             "url": "https://136"},
        ]}
        url, prog = reproductor._video_para_altura(info, 720)
        self.assertEqual(url, "https://136")
        self.assertFalse(prog)


class TestVideoParaAlturaFijado(unittest.TestCase):
    def test_progresivo_exacto(self):
        info = {"formats": [
            {"format_id": "p720", "vcodec": "avc1", "acodec": "mp4a",
             "height": 720, "protocol": "https", "url": "https://p720"},
        ]}
        self.assertEqual(_video_para_altura(info, 720),
                         ("https://p720", True))

    def test_progresivo_mas_bajo_y_solo_exacto_gana_solo(self):
        info = {"formats": [
            {"format_id": "p480", "vcodec": "avc1", "acodec": "mp4a",
             "height": 480, "protocol": "https", "url": "https://p480"},
            {"format_id": "s720", "vcodec": "avc1", "acodec": "none",
             "height": 720, "protocol": "https", "tbr": 1500,
             "url": "https://s720"},
        ]}
        self.assertEqual(_video_para_altura(info, 720),
                         ("https://s720", False))

    def test_dos_solos_a_la_altura_gana_https_aunque_tenga_menos_tbr(self):
        info = {"formats": [
            {"format_id": "s720hls", "vcodec": "avc1", "acodec": "none",
             "height": 720, "protocol": "m3u8_native", "tbr": 3000,
             "url": "https://s720hls"},
            {"format_id": "s720https", "vcodec": "avc1", "acodec": "none",
             "height": 720, "protocol": "https", "tbr": 1500,
             "url": "https://s720https"},
        ]}
        self.assertEqual(_video_para_altura(info, 720),
                         ("https://s720https", False))

    def test_dos_https_a_la_altura_gana_mas_tbr(self):
        info = {"formats": [
            {"format_id": "s720lento", "vcodec": "avc1", "acodec": "none",
             "height": 720, "protocol": "https", "tbr": 2000,
             "url": "https://s720lento"},
            {"format_id": "s720rapido", "vcodec": "avc1", "acodec": "none",
             "height": 720, "protocol": "https", "tbr": 3000,
             "url": "https://s720rapido"},
        ]}
        self.assertEqual(_video_para_altura(info, 720),
                         ("https://s720rapido", False))

    def test_sin_solo_exacto_devuelve_mejor_progresivo_aunque_supere(self):
        info = {"formats": [
            {"format_id": "p360", "vcodec": "avc1", "acodec": "mp4a",
             "height": 360, "protocol": "https", "url": "https://p360"},
            {"format_id": "p1080", "vcodec": "avc1", "acodec": "mp4a",
             "height": 1080, "protocol": "https", "url": "https://p1080"},
        ]}
        self.assertEqual(_video_para_altura(info, 720),
                         ("https://p1080", True))

    def test_sin_progresivos_solos_por_debajo_elige_mas_alto(self):
        info = {"formats": [
            {"format_id": "s360", "vcodec": "avc1", "acodec": "none",
             "height": 360, "protocol": "https", "tbr": 1000,
             "url": "https://s360"},
            {"format_id": "s480", "vcodec": "avc1", "acodec": "none",
             "height": 480, "protocol": "https", "tbr": 1500,
             "url": "https://s480"},
        ]}
        self.assertEqual(_video_para_altura(info, 720),
                         ("https://s480", False))

    def test_sin_progresivos_todos_por_encima_elige_mas_bajo(self):
        info = {"formats": [
            {"format_id": "s720", "vcodec": "avc1", "acodec": "none",
             "height": 720, "protocol": "https", "tbr": 2500,
             "url": "https://s720"},
            {"format_id": "s1080", "vcodec": "avc1", "acodec": "none",
             "height": 1080, "protocol": "https", "tbr": 4500,
             "url": "https://s1080"},
        ]}
        self.assertEqual(_video_para_altura(info, 480),
                         ("https://s720", False))

    def test_sin_video_devuelve_vacio(self):
        info = {"formats": [
            {"format_id": "a140", "vcodec": "none", "acodec": "mp4a",
             "height": None, "protocol": "https",
             "url": "https://a140"},
        ]}
        self.assertEqual(_video_para_altura(info, 720), ("", False))


def _video(url, altura, cuando, protocolo="https"):
    return {"vcodec": "avc", "acodec": "none", "height": altura,
            "protocol": protocolo, "url": url, "available_at": cuando}


def _pista_audio(url, cuando, ext, acodec, abr, canales=None, lang=10,
                 protocolo="https"):
    pista = {"vcodec": "none", "acodec": acodec, "abr": abr,
             "language_preference": lang, "ext": ext, "protocol": protocolo,
             "url": url, "available_at": cuando}
    if canales is not None:
        pista["audio_channels"] = canales
    return pista


class PruebasEsperaParaAbrir(unittest.TestCase):

    def test_con_altura_cuenta_el_video_y_el_audio_elegidos(self):
        info = {"is_live": False, "formats": [
            _video("https://video", 720, 1010),
            _pista_audio("https://audio", 1005, "m4a", "mp4a", 128),
            _pista_audio("https://otro-audio", 1015, "webm", "opus", 160),
        ]}
        self.assertEqual(espera_para_abrir(info, 720, 1000.0), 10.0)

    def test_con_altura_none_usa_la_altura_automatica(self):
        info = {"is_live": False, "formats": [
            _video("https://1080", 1080, 1013),
            _video("https://720", 720, 1002),
            _pista_audio("https://audio", 1001, "m4a", "mp4a", 128),
        ]}
        self.assertEqual(espera_para_abrir(info, None, 1000.0), 13.0)

    def test_solo_audio_espera_solo_la_direccion_de_audio(self):
        info = {"is_live": False, "formats": [
            _video("https://video", 720, 1019),
            _pista_audio("https://audio", 1004, "m4a", "mp4a", 128),
            _pista_audio("https://258", 1015, "m4a", "mp4a", 384,
                         canales=6),
        ]}
        self.assertEqual(
            espera_para_abrir(info, 720, 1000.0, solo_audio=True), 4.0)

    def test_directo_usa_fuentes_para_directo(self):
        info = {"is_live": True, "formats": [
            _video("https://video", 720, 1004),
            _pista_audio("https://audio", 1009, "m4a", "mp4a", 128),
        ]}
        with mock.patch.object(formatos_youtube, "fuentes_para_directo",
                               return_value=("https://video",
                                             "https://audio")) as fuentes:
            espera = espera_para_abrir(info, 720, 1000.0)
        fuentes.assert_called_once_with(info)
        self.assertEqual(espera, 9.0)


if __name__ == "__main__":
    unittest.main()
