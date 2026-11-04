"""Pruebas de la vigilancia que reconecta el relevo de un directo."""

import importlib
import unittest
from unittest import mock

from bellbird.core import idioma
from bellbird.player import vigilancia_relevo


class Reloj:
    def __init__(self, ahora=0.0):
        self.ahora = ahora

    def __call__(self):
        return self.ahora


class Banco:
    """Callbacks y estado que la vigilancia usa desde el reproductor."""

    def __init__(self, activo=True, dos_entradas=True):
        self.activo = activo
        self.dos_entradas = dos_entradas
        self.reinicios = []
        self.anuncios = []
        self.sonidos = []
        self.desfase = 7
        self.reloj = Reloj()

    def reabrir(self, desfase, anuncio):
        self.reinicios.append((desfase, anuncio))
        return self.desfase if desfase is None else desfase

    def anunciar(self, texto):
        self.anuncios.append(texto)

    def sonar(self, evento):
        self.sonidos.append(evento)

    def despachar(self, funcion, *args):
        funcion(*args)

    def crear(self):
        return vigilancia_relevo.Vigilancia(
            self.reabrir, self.anunciar, self.sonar, self.despachar,
            activo=lambda: self.activo,
            dos_entradas=lambda: self.dos_entradas,
            reloj=self.reloj)


class TestAvisoDeCorte(unittest.TestCase):

    def test_avisa_al_caer_el_buffer_por_primera_vez(self):
        self.assertTrue(vigilancia_relevo.aviso_de_corte(99, None))

    def test_avisa_al_recuperarse_el_buffer(self):
        self.assertTrue(vigilancia_relevo.aviso_de_corte(100, 99))

    def test_no_avisa_cada_evento_durante_un_corte(self):
        self.assertEqual(vigilancia_relevo.aviso_de_corte(80, 99), "")


class TestFrases(unittest.TestCase):

    def tearDown(self):
        idioma._reiniciar()

    def test_se_traducen_al_anunciar_y_no_al_importar(self):
        idioma.instalar(idioma.IDIOMA_PSEUDO)
        importlib.reload(vigilancia_relevo)
        self.assertEqual(vigilancia_relevo._FRASE_RECONEXION,
                         "Reconectando el directo")
        idioma.instalar("en")
        banco = Banco()
        vigilancia = banco.crear()
        for instante in (0.0, 30.0, 60.0):
            vigilancia.aviso(
                "Error during demuxing: I/O error", instante)
        vigilancia.aviso("Error during demuxing: I/O error", 90.0)
        self.assertEqual(banco.anuncios[0], "Reconnecting the live stream")
        self.assertEqual(
            banco.anuncios[-1],
            "The live stream keeps cutting out. Reload it if it doesn't improve.")


class TestEntradaDeError(unittest.TestCase):

    def test_con_dos_entradas_nombra_la_que_fallo(self):
        self.assertEqual(
            vigilancia_relevo.entrada_de_error(
                "[in#0/hls @ 1] Error during demuxing: I/O error", True),
            "video")
        self.assertEqual(
            vigilancia_relevo.entrada_de_error(
                "[in#1/hls @ 1] Error during demuxing: I/O error", True),
            "audio")

    def test_con_dos_entradas_y_sin_marca_es_mixta(self):
        self.assertEqual(
            vigilancia_relevo.entrada_de_error(
                "Error during demuxing: I/O error", True),
            "mixta")

    def test_con_una_entrada_no_culpa_a_ninguna(self):
        self.assertEqual(
            vigilancia_relevo.entrada_de_error(
                "[in#0/hls @ 1] Error during demuxing: I/O error", False),
            "")


class TestCortes(unittest.TestCase):

    def test_un_corte_no_reinicia(self):
        banco = Banco()
        vigilancia = banco.crear()
        vigilancia.corte(0.0)
        self.assertEqual(banco.reinicios, [])

    def test_tres_cortes_en_un_minuto_reinician(self):
        banco = Banco()
        vigilancia = banco.crear()
        for instante in (0.0, 10.0, 20.0):
            vigilancia.corte(instante)
        self.assertEqual(len(banco.reinicios), 1)
        self.assertEqual(banco.reinicios[0][0], None)
        self.assertEqual(banco.anuncios[-1], "Reconectando el directo")
        self.assertEqual(banco.sonidos, ["reconectando_directo"])

    def test_tres_cortes_repartidos_en_mas_de_un_minuto_no_reinician(self):
        banco = Banco()
        vigilancia = banco.crear()
        for instante in (0.0, 30.0, 61.0):
            vigilancia.corte(instante)
        self.assertEqual(banco.reinicios, [])

    def test_el_corte_que_reinicia_no_vuelve_a_contar(self):
        banco = Banco()
        vigilancia = banco.crear()
        for instante in (0.0, 10.0, 20.0):
            vigilancia.corte(instante)
        banco.reloj.ahora = 41.0
        for instante in (41.0, 42.0):
            vigilancia.corte(instante)
        self.assertEqual(len(banco.reinicios), 1)


class TestErrores(unittest.TestCase):

    def test_un_error_de_stderr_en_directo_reinicia(self):
        banco = Banco()
        vigilancia = banco.crear()
        vigilancia.aviso(
            "[in#1/hls @ 1] Error during demuxing: I/O error", 0.0)
        self.assertEqual(len(banco.reinicios), 1)
        self.assertEqual(banco.anuncios, ["Reconectando el directo"])
        self.assertEqual(banco.sonidos, ["reconectando_directo"])

    def test_en_grabado_no_reinicia(self):
        banco = Banco(activo=False)
        vigilancia = banco.crear()
        vigilancia.aviso(
            "[in#1/hls @ 1] Error during demuxing: I/O error", 0.0)
        self.assertEqual(banco.reinicios, [])
        self.assertEqual(banco.anuncios, [])

    def test_los_avisos_repetidos_de_ffmpeg_no_reinician(self):
        banco = Banco()
        vigilancia = banco.crear()
        for texto in (
                "[hls @ 1] keepalive request failed for 'https://x/seg.ts'",
                "Cannot reuse HTTP connection for different host: a vs b"):
            vigilancia.aviso(texto, 0.0)
        self.assertEqual(banco.reinicios, [])

    def test_un_reintento_pasajero_de_la_lista_no_reinicia(self):
        banco = Banco()
        vigilancia = banco.crear()
        vigilancia.aviso("Failed to reload playlist", 0.0)
        self.assertEqual(banco.reinicios, [])

    def test_espera_veinte_segundos_entre_motivos(self):
        banco = Banco()
        vigilancia = banco.crear()
        vigilancia.aviso("Error during demuxing: I/O error", 0.0)
        vigilancia.aviso("Error during demuxing: I/O error", 10.0)
        self.assertEqual(len(banco.reinicios), 1)
        vigilancia.aviso("Error during demuxing: I/O error", 21.0)
        self.assertEqual(len(banco.reinicios), 2)


class TestTopeDeReinicios(unittest.TestCase):

    def test_cuarto_motivo_avisa_una_sola_vez(self):
        banco = Banco()
        vigilancia = banco.crear()
        for instante in (0.0, 30.0, 60.0):
            vigilancia.aviso("Error during demuxing: I/O error", instante)
        self.assertEqual(len(banco.reinicios), 3)
        vigilancia.aviso("Error during demuxing: I/O error", 90.0)
        self.assertEqual(len(banco.reinicios), 3)
        self.assertEqual(
            banco.anuncios[-1],
            "El directo sigue con cortes. Vuelve a cargarlo si no mejora.")
        self.assertEqual(banco.sonidos[-1], "directo_con_cortes")
        vigilancia.aviso("Error during demuxing: I/O error", 120.0)
        self.assertEqual(len(banco.reinicios), 3)
        self.assertEqual(
            banco.anuncios.count(
                "El directo sigue con cortes. Vuelve a cargarlo si no mejora."),
            1)

    def test_olvidar_vuelve_a_contar(self):
        banco = Banco()
        vigilancia = banco.crear()
        for instante in (0.0, 30.0, 60.0):
            vigilancia.aviso("Error during demuxing: I/O error", instante)
        vigilancia.aviso("Error during demuxing: I/O error", 90.0)
        vigilancia.olvidar()
        vigilancia.aviso("Error during demuxing: I/O error", 200.0)
        self.assertEqual(len(banco.reinicios), 4)


class TestRegistro(unittest.TestCase):

    def test_registra_motivo_entrada_desfase_y_vuelta_una_sola_vez(self):
        banco = Banco()
        vigilancia = banco.crear()
        vigilancia.aviso(
            "[in#1/hls @ 1] Error during demuxing: I/O error", 0.0)
        mensaje = vigilancia.registrar_vuelta(2.5)
        self.assertIn("motivo=error", mensaje)
        self.assertIn("entrada=audio", mensaje)
        self.assertIn("desfase=7", mensaje)
        self.assertIn("vuelta_ms=2500", mensaje)
        self.assertEqual(vigilancia.registrar_vuelta(3.0), "")

    def test_con_una_entrada_el_registro_dice_unica(self):
        banco = Banco(dos_entradas=False)
        vigilancia = banco.crear()
        vigilancia.aviso(
            "[in#0/hls @ 1] Error during demuxing: I/O error", 0.0)
        self.assertIn("entrada=unica", vigilancia.registrar_vuelta(1.0))

    def test_buffer_devuelve_el_aviso_para_el_registro(self):
        banco = Banco()
        vigilancia = banco.crear()
        self.assertEqual(vigilancia.buffer(99, None),
                         "VLC_CORTE empezó porcentaje=99")
        self.assertEqual(vigilancia.buffer(100, 99), "VLC_CORTE recuperado")


class Panel:
    """Doble mínimo del panel para probar el cableado de conectar()."""

    def __init__(self, directo=True, vod=False, cargando=False,
                 fuentes=("video", "audio")):
        self.directo = directo
        self._vod_por_relevo = vod
        self._cargando = cargando
        self._url_flujo = ""
        self._relevo_fuentes = fuentes
        self._relevo_desfase = 4
        self._relevo_ffmpeg = object()
        self._cancelar_busqueda = mock.Mock()
        self._cancelar_transporte = mock.Mock()
        self._detener_relevo_ffmpeg = mock.Mock()
        self._arrancar_relevo = mock.Mock()

    def _es_directo_actual(self):
        return self.directo


class TestConectar(unittest.TestCase):

    def _conectar(self, panel, anuncios, sonar):
        return vigilancia_relevo.conectar(
            panel, anuncios.append, lambda fn, *args: fn(*args))

    def test_el_error_reinicia_con_el_mismo_desfase(self):
        panel = Panel()
        anuncios = []
        with mock.patch("bellbird.voice.sound_player.reproducir") as sonar:
            vigilancia = self._conectar(panel, anuncios, sonar)
            vigilancia.aviso(
                "[in#1/hls @ 1] Error during demuxing: I/O error", 0.0)
        panel._cancelar_busqueda.assert_called_once()
        panel._cancelar_transporte.assert_called_once()
        panel._detener_relevo_ffmpeg.assert_called_once()
        args, kwargs = panel._arrancar_relevo.call_args
        self.assertEqual(args, ("video", "audio", True))
        self.assertEqual(kwargs["desfase"], 4)
        self.assertEqual(kwargs["anuncio"], "Reconectando el directo")
        self.assertEqual(anuncios, ["Reconectando el directo"])
        sonar.assert_called_once_with("reconectando_directo")

    def test_en_grabado_no_toca_el_panel(self):
        panel = Panel(directo=False, vod=True)
        anuncios = []
        with mock.patch("bellbird.voice.sound_player.reproducir") as sonar:
            vigilancia = self._conectar(panel, anuncios, sonar)
            vigilancia.aviso("Error during demuxing: I/O error", 0.0)
        panel._detener_relevo_ffmpeg.assert_not_called()
        panel._arrancar_relevo.assert_not_called()

    def test_una_sola_entrada_se_registra_sin_culpar_a_audio_ni_video(self):
        panel = Panel(fuentes=("video", ""))
        anuncios = []
        with mock.patch("bellbird.voice.sound_player.reproducir") as sonar:
            vigilancia = self._conectar(panel, anuncios, sonar)
            vigilancia.aviso(
                "[in#0/hls @ 1] Error during demuxing: I/O error", 0.0)
            self.assertIn("entrada=unica", vigilancia.registrar_vuelta(1.0))


if __name__ == "__main__":
    unittest.main()
