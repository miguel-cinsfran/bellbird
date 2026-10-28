import unittest
from unittest import mock

from ytchat.player import recuperacion
from ytchat.player import reproductor


def _funciones(**valores):
    base = {
        "es_directo": lambda: False,
        "fallo_apertura": lambda: False,
        "flujo_sono": lambda: False,
        "relevo_con_reintento": lambda: False,
    }
    base.update(valores)
    return base


class TestDecidirAlTerminarEnded(unittest.TestCase):

    def test_nada_si_vod_cargando(self):
        decision = recuperacion.decidir_al_terminar(
            "ended", vod_cargando=True, hay_relevo=True,
            relevo_vod=True, es_flujo=False,
            **_funciones(es_directo=lambda: True,
                         fallo_apertura=lambda: True))
        self.assertEqual(decision, recuperacion.NADA)

    def test_directo_interrumpido(self):
        decision = recuperacion.decidir_al_terminar(
            "ended", vod_cargando=False, hay_relevo=True,
            relevo_vod=False, es_flujo=False,
            **_funciones(es_directo=lambda: True))
        self.assertEqual(decision, recuperacion.DIRECTO_INTERRUMPIDO)

    def test_fin_flujo_vod(self):
        decision = recuperacion.decidir_al_terminar(
            "ended", vod_cargando=False, hay_relevo=True,
            relevo_vod=True, es_flujo=False,
            **_funciones(es_directo=lambda: False))
        self.assertEqual(decision, recuperacion.FIN_FLUJO_VOD)

    def test_recargar_apertura(self):
        decision = recuperacion.decidir_al_terminar(
            "ended", vod_cargando=False, hay_relevo=False,
            relevo_vod=False, es_flujo=False,
            **_funciones(fallo_apertura=lambda: True))
        self.assertEqual(decision, recuperacion.RECARGAR_APERTURA)

    def test_terminar_flujo(self):
        decision = recuperacion.decidir_al_terminar(
            "ended", vod_cargando=False, hay_relevo=False,
            relevo_vod=False, es_flujo=True,
            **_funciones())
        self.assertEqual(decision, recuperacion.TERMINAR_FLUJO)

    def test_fin_video(self):
        decision = recuperacion.decidir_al_terminar(
            "ended", vod_cargando=False, hay_relevo=False,
            relevo_vod=False, es_flujo=False,
            **_funciones())
        self.assertEqual(decision, recuperacion.FIN_VIDEO)

    def test_nada_con_otro_estado(self):
        decision = recuperacion.decidir_al_terminar(
            "playing", vod_cargando=False, hay_relevo=True,
            relevo_vod=True, es_flujo=True,
            **_funciones(es_directo=lambda: True,
                         fallo_apertura=lambda: True,
                         flujo_sono=lambda: True,
                         relevo_con_reintento=lambda: True))
        self.assertEqual(decision, recuperacion.NADA)


class TestDecidirAlTerminarError(unittest.TestCase):

    def test_nada_si_vod_cargando(self):
        decision = recuperacion.decidir_al_terminar(
            "error", vod_cargando=True, hay_relevo=False,
            relevo_vod=False, es_flujo=True,
            **_funciones(fallo_apertura=lambda: True))
        self.assertEqual(decision, recuperacion.NADA)

    def test_terminar_flujo_si_no_sono(self):
        decision = recuperacion.decidir_al_terminar(
            "error", vod_cargando=False, hay_relevo=False,
            relevo_vod=False, es_flujo=True,
            **_funciones(flujo_sono=lambda: False))
        self.assertEqual(decision, recuperacion.TERMINAR_FLUJO)

    def test_recargar_apertura_sin_reintento(self):
        decision = recuperacion.decidir_al_terminar(
            "error", vod_cargando=False, hay_relevo=True,
            relevo_vod=False, es_flujo=False,
            **_funciones(fallo_apertura=lambda: True,
                         relevo_con_reintento=lambda: False))
        self.assertEqual(decision, recuperacion.RECARGAR_APERTURA)

    def test_fallo_si_hay_reintento(self):
        decision = recuperacion.decidir_al_terminar(
            "error", vod_cargando=False, hay_relevo=True,
            relevo_vod=False, es_flujo=False,
            **_funciones(fallo_apertura=lambda: True,
                         relevo_con_reintento=lambda: True))
        self.assertEqual(decision, recuperacion.FALLO)

    def test_fallo_sin_apertura(self):
        decision = recuperacion.decidir_al_terminar(
            "error", vod_cargando=False, hay_relevo=False,
            relevo_vod=False, es_flujo=False,
            **_funciones())
        self.assertEqual(decision, recuperacion.FALLO)


class TestOrdenPerezoso(unittest.TestCase):

    def test_no_llama_es_directo_si_vod_cargando(self):
        es_directo = mock.Mock(side_effect=AssertionError)
        decision = recuperacion.decidir_al_terminar(
            "ended", vod_cargando=True, hay_relevo=True,
            relevo_vod=True, es_flujo=False, es_directo=es_directo,
            fallo_apertura=lambda: False,
            flujo_sono=lambda: False,
            relevo_con_reintento=lambda: False)
        self.assertEqual(decision, recuperacion.NADA)
        es_directo.assert_not_called()

    def test_no_llama_fallo_apertura_si_directo(self):
        fallo_apertura = mock.Mock(side_effect=AssertionError)
        decision = recuperacion.decidir_al_terminar(
            "ended", vod_cargando=False, hay_relevo=True,
            relevo_vod=False, es_flujo=False,
            es_directo=lambda: True,
            fallo_apertura=fallo_apertura,
            flujo_sono=lambda: False,
            relevo_con_reintento=lambda: False)
        self.assertEqual(decision, recuperacion.DIRECTO_INTERRUMPIDO)
        fallo_apertura.assert_not_called()


class TestUltimaPosicion(unittest.TestCase):

    def test_usa_relevo(self):
        self.assertEqual(
            recuperacion.ultima_posicion(9000, 8000, 1000), 9000)

    def test_usa_confirmada_si_no_hay_relevo(self):
        self.assertEqual(
            recuperacion.ultima_posicion(None, 8000, 1000), 8000)

    def test_usa_pos_si_no_hay_otra(self):
        self.assertEqual(
            recuperacion.ultima_posicion(None, None, 1000), 1000)

    def test_valor_no_numerico_da_cero(self):
        self.assertEqual(
            recuperacion.ultima_posicion("rota", None, 1000), 0)


class TestDecidirFinVod(unittest.TestCase):

    def test_fin_video_con_dur_cero(self):
        self.assertEqual(
            recuperacion.decidir_fin_vod(0, 9000, 0, 1000, True),
            recuperacion.FIN_VIDEO)

    def test_fin_video_en_el_borde_de_5000(self):
        self.assertEqual(
            recuperacion.decidir_fin_vod(15000, 10000, 0, 1000, True),
            recuperacion.FIN_VIDEO)

    def test_esclavo_si_nunca_sono(self):
        self.assertEqual(
            recuperacion.decidir_fin_vod(60000, 9000, 2, 9000, True),
            recuperacion.ESCLAVO)

    def test_corte_sonado_si_agoto_recuperaciones(self):
        self.assertEqual(
            recuperacion.decidir_fin_vod(60000, 20000, 2, 1000, True),
            recuperacion.CORTE_SONADO)

    def test_corte_sonado_sin_fuentes(self):
        self.assertEqual(
            recuperacion.decidir_fin_vod(60000, 20000, 2, 1000, False),
            recuperacion.CORTE_SONADO)

    def test_corte_sin_fuentes(self):
        self.assertEqual(
            recuperacion.decidir_fin_vod(60000, 20000, 0, 1000, False),
            recuperacion.CORTE)

    def test_reabrir(self):
        self.assertEqual(
            recuperacion.decidir_fin_vod(60000, 20000, 0, 1000, True),
            recuperacion.REABRIR)


class TestDespachoAlTerminar(unittest.TestCase):
    """Cada decisión de decidir_al_terminar ejecuta su acción y nada más."""

    def _panel(self):
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._player = mock.Mock()
        panel._muted = True
        panel._estado_vlc_actual = mock.Mock(return_value="ended")
        panel._evaluar_transporte = mock.Mock()
        panel._evaluar_busqueda = mock.Mock()
        panel._timer = mock.Mock()
        panel._directo_interrumpido = mock.Mock()
        panel._fin_flujo_vod = mock.Mock()
        panel._recargar_apertura_vod = mock.Mock()
        panel._terminar_flujo_tiktok = mock.Mock()
        panel._detener = mock.Mock()
        panel._fallo_reproduccion = mock.Mock()
        return panel

    def test_despacho(self):
        esperados = {
            recuperacion.DIRECTO_INTERRUMPIDO: "_directo_interrumpido",
            recuperacion.FIN_FLUJO_VOD: "_fin_flujo_vod",
            recuperacion.RECARGAR_APERTURA: "_recargar_apertura_vod",
            recuperacion.TERMINAR_FLUJO: "_terminar_flujo_tiktok",
            recuperacion.FIN_VIDEO: "_detener",
            recuperacion.FALLO: "_fallo_reproduccion",
            recuperacion.NADA: None,
        }
        for decision, destino in esperados.items():
            with self.subTest(decision=decision):
                panel = self._panel()
                destinos = {
                    "_directo_interrumpido": panel._directo_interrumpido,
                    "_fin_flujo_vod": panel._fin_flujo_vod,
                    "_recargar_apertura_vod": panel._recargar_apertura_vod,
                    "_terminar_flujo_tiktok": panel._terminar_flujo_tiktok,
                    "_detener": panel._detener,
                    "_fallo_reproduccion": panel._fallo_reproduccion,
                }
                with mock.patch.object(recuperacion, "decidir_al_terminar",
                                       return_value=decision), \
                        mock.patch.object(reproductor, "anunciar") as anunciar:
                    panel._on_timer(None)
                for nombre, metodo in destinos.items():
                    if nombre == destino:
                        metodo.assert_called_once()
                    else:
                        metodo.assert_not_called()
                if decision == recuperacion.FIN_VIDEO:
                    panel._detener.assert_called_once_with(silencioso=True)
                    anunciar.assert_called_once_with("Fin del vídeo")
                else:
                    anunciar.assert_not_called()


class TestDespachoFinVod(unittest.TestCase):
    """Cada decisión de decidir_fin_vod ejecuta sus llamadas y nada más."""

    def _panel(self):
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._duracion_actual = mock.Mock(return_value=60000)
        panel._pos_ms = 20000
        panel._relevo_fuentes = ("http://ejemplo/video", "esclavo")
        panel._intencion_reproducir = True
        panel._detener = mock.Mock()
        panel._detener_relevo_ffmpeg = mock.Mock()
        panel._cancelar_transporte = mock.Mock()
        panel._continuar_reproducir_calidad = mock.Mock()
        panel._arrancar_relevo = mock.Mock()
        return panel

    def test_despacho(self):
        decisiones = (recuperacion.FIN_VIDEO, recuperacion.CORTE,
                      recuperacion.CORTE_SONADO, recuperacion.ESCLAVO,
                      recuperacion.REABRIR)
        for decision in decisiones:
            with self.subTest(decision=decision):
                panel = self._panel()
                with mock.patch.object(recuperacion, "decidir_fin_vod",
                                       return_value=decision), \
                        mock.patch.object(reproductor, "anunciar") as anunciar, \
                        mock.patch.object(reproductor.logger, "warning") as aviso:
                    panel._fin_flujo_vod()
                if decision == recuperacion.FIN_VIDEO:
                    panel._detener.assert_called_once_with(silencioso=True)
                    anunciar.assert_called_once_with("Fin del vídeo")
                    aviso.assert_not_called()
                elif decision == recuperacion.CORTE:
                    panel._detener.assert_called_once_with(silencioso=True)
                    anunciar.assert_called_once_with("Se cortó el vídeo")
                    aviso.assert_not_called()
                elif decision == recuperacion.CORTE_SONADO:
                    aviso.assert_called_once_with(
                        "VOD_RELEVO corte sin recuperar ultima=%d dur=%d",
                        20000, 60000)
                    panel._detener.assert_called_once_with(silencioso=True)
                    anunciar.assert_called_once_with("Se cortó el vídeo")
                elif decision == recuperacion.ESCLAVO:
                    aviso.assert_called_once_with(
                        "VOD_RELEVO sin arrancar, sigue con esclavo")
                    self.assertFalse(panel._vod_por_relevo)
                    panel._detener_relevo_ffmpeg.assert_called_once_with()
                    self.assertTrue(panel._tiene_esclavo)
                    panel._continuar_reproducir_calidad.assert_called_once_with(
                        "http://ejemplo/video", "esclavo", False, True)
                    panel._detener.assert_not_called()
                    anunciar.assert_not_called()
                elif decision == recuperacion.REABRIR:
                    self.assertEqual(panel._relevo_vod_recuperaciones, 1)
                    aviso.assert_called_once_with(
                        "VOD_RELEVO recupera=%d ultima=%d dur=%d",
                        1, 20000, 60000)
                    panel._cancelar_transporte.assert_called_once_with()
                    panel._detener_relevo_ffmpeg.assert_called_once_with()
                    self.assertEqual(panel._relevo_fuentes,
                                     ("http://ejemplo/video", "esclavo"))
                    panel._arrancar_relevo.assert_called_once_with(
                        "http://ejemplo/video", "esclavo", True,
                        inicio_ms=20000)
                    panel._detener.assert_not_called()
                    anunciar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
