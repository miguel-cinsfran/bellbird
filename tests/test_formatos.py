"""Pruebas puras de la selección de formatos (`formatos.py`)."""

import unittest

from bellbird.player.formatos import mejor_audio, segundos_hasta_disponible


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


def _formato(url, disponible=None):
    formato = {"url": url}
    if disponible is not None:
        formato["available_at"] = disponible
    return formato


class TestSegundosHastaDisponible(unittest.TestCase):

    def test_elige_el_mayor_de_los_pedidos(self):
        info = {"formats": [
            _formato("video", 1010),
            _formato("audio", 1006),
            _formato("otro", 1100),
        ]}
        self.assertEqual(
            segundos_hasta_disponible(info, ("video", "audio"), 1000.0), 10.0)

    def test_ignora_el_formato_no_pedido_con_hora_mas_lejana(self):
        info = {"formats": [
            _formato("video", 1008),
            _formato("no-pedido", 1140),
        ]}
        self.assertEqual(
            segundos_hasta_disponible(info, ("video",), 1000.0), 8.0)

    def test_hora_pasada_da_cero(self):
        info = {"formats": [_formato("video", 990)]}
        self.assertEqual(
            segundos_hasta_disponible(info, ("video",), 1000.0), 0.0)

    def test_sin_campo_da_cero(self):
        info = {"formats": [_formato("video")]}
        self.assertEqual(
            segundos_hasta_disponible(info, ("video",), 1000.0), 0.0)

    def test_no_numerico_da_cero(self):
        info = {"formats": [_formato("video", "pronto")]}
        self.assertEqual(
            segundos_hasta_disponible(info, ("video",), 1000.0), 0.0)

    def test_mas_alla_del_tope_da_el_tope(self):
        info = {"formats": [_formato("video", 1100)]}
        self.assertEqual(
            segundos_hasta_disponible(info, ("video",), 1000.0, tope=15.0),
            15.0)

    def test_direcciones_vacias_se_ignoran(self):
        info = {"formats": [_formato("", 1100), _formato("video", 1003)]}
        self.assertEqual(
            segundos_hasta_disponible(info, ("", "video"), 1000.0), 3.0)

    def test_barrido_nunca_negativo_ni_pasa_del_tope(self):
        info = {"formats": [_formato("video", 1006), _formato("audio", 1011)]}
        for ahora in range(990, 1030):
            with self.subTest(ahora=ahora):
                espera = segundos_hasta_disponible(
                    info, ("video", "audio"), float(ahora), tope=15.0)
                self.assertGreaterEqual(espera, 0.0)
                self.assertLessEqual(espera, 15.0)


if __name__ == "__main__":
    unittest.main()
