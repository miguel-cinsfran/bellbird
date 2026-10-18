"""Pruebas puras de la selección de formatos (`formatos.py`)."""

import unittest

from ytchat.player.formatos import mejor_audio


def _audio(url, abr=None, idioma=None, protocolo=None, ext=None,
           acodec="mp4a"):
    formato = {"vcodec": "none", "acodec": acodec, "url": url}
    if abr is not None:
        formato["abr"] = abr
    if idioma is not None:
        formato["language_preference"] = idioma
    if protocolo is not None:
        formato["protocol"] = protocolo
    if ext is not None:
        formato["ext"] = ext
    return formato


class TestMejorAudio(unittest.TestCase):

    def test_sin_audio_da_vacio(self):
        self.assertEqual(mejor_audio({"formats": []}), "")
        self.assertEqual(mejor_audio({}), "")
        self.assertEqual(mejor_audio({"formats": None}), "")

    def test_descarta_video_y_audio_sin_url(self):
        info = {"formats": [
            {"vcodec": "avc1", "acodec": "mp4a", "url": "progresivo"},
            _audio("sin-url") | {"url": None},
        ]}
        self.assertEqual(mejor_audio(info), "")

    def test_prefiere_la_pista_original_sobre_el_bitrate(self):
        info = {"formats": [
            _audio("doblaje", abr=320, idioma=1),
            _audio("original", abr=128, idioma=10),
        ]}
        self.assertEqual(mejor_audio(info), "original")

    def test_a_igualdad_de_idioma_gana_el_bitrate(self):
        info = {"formats": [
            _audio("flojo", abr=128, idioma=10),
            _audio("fuerte", abr=192, idioma=10),
        ]}
        self.assertEqual(mejor_audio(info), "fuerte")

    def test_evitar_hls_ignora_las_pistas_hls(self):
        info = {"formats": [
            _audio("hls", abr=256, idioma=10, protocolo="m3u8_native"),
            _audio("https", abr=128, idioma=10),
        ]}
        self.assertEqual(mejor_audio(info, evitar_hls=True), "https")

    def test_evitar_hls_sin_alternativa_elige_entre_las_hls(self):
        info = {"formats": [
            _audio("hls-a", abr=128, idioma=10, protocolo="m3u8_native"),
            _audio("hls-b", abr=256, idioma=10, protocolo="m3u8_native"),
        ]}
        self.assertEqual(mejor_audio(info, evitar_hls=True), "hls-b")

    def test_evitar_hls_prefiere_m4a_a_igualdad_de_idioma(self):
        info = {"formats": [
            _audio("opus", abr=160, idioma=10, ext="webm", acodec="opus"),
            _audio("m4a", abr=128, idioma=10, ext="m4a"),
        ]}
        self.assertEqual(mejor_audio(info, evitar_hls=True), "m4a")

    def test_evitar_hls_conserva_el_idioma_por_encima_del_formato(self):
        info = {"formats": [
            _audio("opus-original", abr=160, idioma=10, ext="webm",
                   acodec="opus"),
            _audio("m4a-doblado", abr=128, idioma=1, ext="m4a"),
        ]}
        self.assertEqual(mejor_audio(info, evitar_hls=True), "opus-original")


if __name__ == "__main__":
    unittest.main()
