"""Cableado del final del flujo de TikTok en el reproductor."""

import unittest
from unittest import mock

from ytchat.player import reproductor


def _panel_timer(estado, sono=False):
    panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
    panel._video_id = ""
    panel._url_flujo = ("https://example.com/flujo.flv"
                        "?expire=1700000000&sign=secreto")
    panel._info = {"is_live": True}
    panel._player = mock.Mock()
    panel._muted = True
    panel._vol = 80
    inicio = mock.Mock()
    inicio.requiere = False
    inicio.anunciado = sono
    inicio.primera = None
    inicio.observar.return_value = False
    panel._estado_inicio = inicio
    panel._estado_vlc_actual = mock.Mock(return_value=estado)
    panel._lectura_cruda = mock.Mock(return_value=1000)
    panel._topologia_actual = mock.Mock(return_value="flujo")
    panel._evaluar_transporte = mock.Mock()
    panel._evaluar_busqueda = mock.Mock()
    panel._vod_por_relevo = False
    panel._cargando = False
    panel._relevo_ffmpeg = None
    panel._relevo_vod_base_ms = None
    panel._orden_transporte = None
    panel._estado_busqueda = mock.Mock(pendiente=False)
    panel._timer = mock.Mock()
    panel._intencion_reproducir = True
    panel._recargas_apertura = 0
    panel._recargas_directo = 0
    panel._listo = True
    panel._calidad_sel = None
    panel._alturas = []
    panel._gen = 0
    panel._detener = mock.Mock()
    panel._fijar_estado = mock.Mock()
    panel.cargar = mock.Mock()
    return panel


class TestFinalDelFlujo(unittest.TestCase):

    def test_flujo_que_nunca_sono_y_termina_avisa_una_vez_y_lanza_la_sonda(self):
        panel = _panel_timer("ended", sono=False)
        with mock.patch.object(reproductor, "anunciar") as anunciar, \
                mock.patch.object(reproductor.flujo_tiktok,
                                  "sondear_en_hilo") as sonda, \
                mock.patch("ytchat.voice.sound_player.reproducir") as sonido:
            panel._on_timer(None)
            panel._on_timer(None)

        panel._detener.assert_called_once_with(silencioso=True)
        panel._fijar_estado.assert_called_once_with(
            "No se pudo abrir el directo de TikTok.")
        anunciar.assert_called_once_with(
            "No se pudo abrir el directo de TikTok")
        sonido.assert_called_once_with("error")
        sonda.assert_called_once_with(panel._url_flujo)

    def test_flujo_que_nunca_sono_y_da_error_avisa_y_lanza_la_sonda(self):
        panel = _panel_timer("error", sono=False)
        with mock.patch.object(reproductor, "anunciar") as anunciar, \
                mock.patch.object(reproductor.flujo_tiktok,
                                  "sondear_en_hilo") as sonda, \
                mock.patch("ytchat.voice.sound_player.reproducir") as sonido:
            panel._on_timer(None)

        panel._detener.assert_called_once_with(silencioso=True)
        panel._fijar_estado.assert_called_once_with(
            "No se pudo abrir el directo de TikTok.")
        anunciar.assert_called_once_with(
            "No se pudo abrir el directo de TikTok")
        sonido.assert_called_once_with("error")
        sonda.assert_called_once_with(panel._url_flujo)

    def test_error_y_ended_del_mismo_intento_avisan_una_vez(self):
        panel = _panel_timer("error", sono=False)
        with mock.patch.object(reproductor, "anunciar") as anunciar, \
                mock.patch.object(reproductor.flujo_tiktok,
                                  "sondear_en_hilo") as sonda, \
                mock.patch("ytchat.voice.sound_player.reproducir") as sonido:
            panel._on_timer(None)
            panel._estado_vlc_actual.return_value = "ended"
            panel._on_timer(None)

        anunciar.assert_called_once_with(
            "No se pudo abrir el directo de TikTok")
        sonido.assert_called_once_with("error")
        sonda.assert_called_once_with(panel._url_flujo)

    def test_flujo_que_sono_y_termina_anuncia_el_fin_sin_sonda_ni_error(self):
        panel = _panel_timer("ended", sono=True)
        with mock.patch.object(reproductor, "anunciar") as anunciar, \
                mock.patch.object(reproductor.flujo_tiktok,
                                  "sondear_en_hilo") as sonda, \
                mock.patch("ytchat.voice.sound_player.reproducir") as sonido:
            panel._on_timer(None)

        panel._detener.assert_called_once_with(silencioso=True)
        anunciar.assert_called_once_with("El directo de TikTok terminó")
        sonda.assert_not_called()
        sonido.assert_not_called()
        panel._fijar_estado.assert_not_called()

    def test_vod_de_youtube_que_termina_sigue_diciendo_fin_del_video(self):
        panel = _panel_timer("ended", sono=False)
        panel._url_flujo = ""
        panel._video_id = "A" * 11
        panel._info = {"is_live": False}
        with mock.patch.object(reproductor, "anunciar") as anunciar:
            panel._on_timer(None)

        panel._detener.assert_called_once_with(silencioso=True)
        anunciar.assert_called_once_with("Fin del vídeo")


class TestLogDelEnlace(unittest.TestCase):

    def _panel(self):
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._listo = True
        panel._ciclo = None
        panel._detener = mock.Mock()
        panel._fijar_estado = mock.Mock()
        return panel

    def test_set_flujo_anota_el_resumen_del_enlace(self):
        panel = self._panel()
        url = ("https://example.com/live/stream.flv"
               "?expire=1700000000&sign=secreto")
        resumen = "servidor=example.com ruta=/live/stream.flv"
        with mock.patch.object(reproductor.logger, "info") as info, \
                mock.patch.object(reproductor.flujo_tiktok, "resumen_url",
                                  return_value=resumen) as resumir:
            panel.set_flujo(url, autoplay=False)

        resumir.assert_called_once_with(url)
        info.assert_called_once_with("TIKTOK_FLUJO %s", resumen)

    def test_set_flujo_vacio_no_anota(self):
        panel = self._panel()
        with mock.patch.object(reproductor.logger, "info") as info:
            panel.set_flujo("", autoplay=False)
        info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
