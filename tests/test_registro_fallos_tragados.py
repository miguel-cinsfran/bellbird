"""Avisos en el registro cuando falla algo que el usuario eligió o guardó.

Cada prueba fuerza el fallo por el cableado real y comprueba que el aviso
queda en el registro y que el flujo sigue igual que antes.
"""

import configparser
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.rutas_temporales import redirigir_rutas


class TestConfigSonidos(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_activar_invalido_avisa_y_mantiene_valor(self):
        from bellbird.core import config
        with redirigir_rutas(self._tmp.name):
            (Path(self._tmp.name) / "sounds.ini").write_text(
                "[sonidos]\nactivar = quizás\n", encoding="utf-8")
            with self.assertLogs("bellbird.config", level="WARNING") as logs:
                sonidos = config.cargar_sonidos()
        self.assertTrue(sonidos["activar"])
        self.assertTrue(any("activar" in mensaje for mensaje in logs.output))

    def test_volumen_invalido_avisa_y_mantiene_valor(self):
        from bellbird.core import config
        with redirigir_rutas(self._tmp.name):
            (Path(self._tmp.name) / "sounds.ini").write_text(
                "[sonidos]\nvolumen = alto\n", encoding="utf-8")
            with self.assertLogs("bellbird.config", level="WARNING") as logs:
                sonidos = config.cargar_sonidos()
        self.assertEqual(sonidos["volumen"], 0.7)
        self.assertTrue(any("volumen" in mensaje for mensaje in logs.output))

    def test_tema_invalido_avisa_y_mantiene_valor(self):
        from bellbird.core import config
        real_get = configparser.ConfigParser.get

        def get_fallido(self, *args, **kwargs):
            if args[:2] == ("sonidos", "tema"):
                raise ValueError("tema roto")
            return real_get(self, *args, **kwargs)

        with redirigir_rutas(self._tmp.name):
            (Path(self._tmp.name) / "sounds.ini").write_text(
                "[sonidos]\ntema = suave\n", encoding="utf-8")
            with mock.patch.object(configparser.ConfigParser, "get",
                                   get_fallido):
                with self.assertLogs("bellbird.config", level="WARNING") as logs:
                    sonidos = config.cargar_sonidos()
        self.assertEqual(sonidos["eventos"]["copiar"],
                         Path(self._tmp.name) / "sounds" / "themes"
                         / config._TEMA_DEFECTO / "copiar.wav")
        self.assertTrue(any("tema" in mensaje for mensaje in logs.output))


class TestBotonDirecto(unittest.TestCase):

    def test_guardar_destino_falla_avisa_y_sigue(self):
        from bellbird.ui import boton_directo
        marco = SimpleNamespace(
            _config={},
            _guardar_destino_transmision=mock.Mock(
                side_effect=RuntimeError("disco lleno")),
        )
        falso_self = SimpleNamespace(_marco=marco, boton=mock.Mock())
        with mock.patch("bellbird.ui.gui_elegir_destino.pedir_destino",
                        return_value=("YouTube", "")), \
             mock.patch.object(boton_directo, "anunciar"), \
             mock.patch.object(boton_directo._snd, "reproducir"), \
             mock.patch.object(boton_directo.diagnostico, "crear_hilo") as crear_hilo:
            with self.assertLogs("bellbird.boton_directo", level="WARNING") as logs:
                boton_directo.BotonDirecto._transmitir(falso_self)
        marco._guardar_destino_transmision.assert_called_once_with("YouTube")
        crear_hilo.assert_called_once()
        self.assertTrue(any("destino" in mensaje for mensaje in logs.output))

    def test_guardar_usuario_falla_avisa_y_sigue(self):
        from bellbird.ui import boton_directo
        marco = SimpleNamespace(
            _config={},
            _guardar_destino_transmision=mock.Mock(),
            _guardar_usuario_tiktok=mock.Mock(
                side_effect=RuntimeError("disco lleno")),
        )
        falso_self = SimpleNamespace(_marco=marco, boton=mock.Mock())
        with mock.patch("bellbird.ui.gui_elegir_destino.pedir_destino",
                        return_value=("TikTok", "alguien")), \
             mock.patch.object(boton_directo, "anunciar"), \
             mock.patch.object(boton_directo._snd, "reproducir"), \
             mock.patch.object(boton_directo.diagnostico, "crear_hilo") as crear_hilo:
            with self.assertLogs("bellbird.boton_directo", level="WARNING") as logs:
                boton_directo.BotonDirecto._transmitir(falso_self)
        crear_hilo.assert_called_once()
        self.assertTrue(any("usuario" in mensaje for mensaje in logs.output))

    def test_guardar_token_falla_avisa_y_no_lanza(self):
        from bellbird.ui import boton_directo
        cliente = mock.Mock()
        cliente.flujo_reutilizable.return_value = ()
        cliente.token_actualizado.return_value = "nuevo-token"
        with mock.patch("bellbird.youtube.credenciales.cargar", return_value={}), \
             mock.patch("bellbird.youtube.credenciales.hay_sesion", return_value=True), \
             mock.patch("bellbird.youtube.credenciales.efectivas", return_value={}), \
             mock.patch("bellbird.youtube.youtube_api.ClienteYouTube",
                        return_value=cliente), \
             mock.patch("bellbird.youtube.credenciales.guardar_campo",
                        side_effect=RuntimeError("disco lleno")):
            cerrar = boton_directo.BotonDirecto._cierre_en_youtube(mock.Mock())
            with self.assertLogs("bellbird.boton_directo", level="WARNING") as logs:
                cerrar()
        self.assertTrue(any("token" in mensaje for mensaje in logs.output))


class TestDirectoHuerfano(unittest.TestCase):

    def test_guardar_token_falla_avisa_y_no_lanza(self):
        from bellbird.ui import gui_directo_huerfano
        cliente = mock.Mock()
        cliente.token_actualizado.return_value = "nuevo-token"
        with mock.patch.object(gui_directo_huerfano.credenciales, "guardar_campo",
                               side_effect=RuntimeError("disco lleno")):
            with self.assertLogs("bellbird.gui_directo_huerfano",
                                 level="WARNING") as logs:
                gui_directo_huerfano._guardar_token_si_hay(cliente)
        self.assertTrue(any("token" in mensaje for mensaje in logs.output))


class TestTransmision(unittest.TestCase):

    def test_guardar_usuario_falla_avisa_y_actualiza(self):
        from bellbird.ui import gui_transmision
        from bellbird.obs import transmision_directa
        falso_self = SimpleNamespace(
            _usuario_tiktok="",
            _transmitiendo=False,
            _guardar_usuario=mock.Mock(side_effect=RuntimeError("disco lleno")),
            _supervisar=None,
            cho_destino=SimpleNamespace(GetStringSelection=lambda: "TikTok"),
            txt_usuario_tiktok=SimpleNamespace(GetValue=lambda: "nuevo"),
            _en_hilo=mock.Mock(),
        )
        with mock.patch.object(transmision_directa, "decidir_transmision",
                               return_value=transmision_directa.REVISAR), \
             mock.patch("bellbird.capture.tiktok_vivo.usuario_tiktok",
                        return_value="nuevo"):
            with self.assertLogs("bellbird.gui_transmision", level="WARNING") as logs:
                gui_transmision.TransmisionDialog._transmitir(falso_self, None)
        self.assertEqual(falso_self._usuario_tiktok, "nuevo")
        falso_self._en_hilo.assert_called_once()
        self.assertTrue(any("usuario" in mensaje for mensaje in logs.output))

    def test_recordar_destino_falla_avisa_y_no_lanza(self):
        from bellbird.ui import gui_transmision
        falso_self = SimpleNamespace(
            _guardar_destino=mock.Mock(side_effect=RuntimeError("disco lleno")))
        with self.assertLogs("bellbird.gui_transmision", level="WARNING") as logs:
            gui_transmision.TransmisionDialog._recordar_destino(falso_self, "YouTube")
        falso_self._guardar_destino.assert_called_once_with("YouTube")
        self.assertTrue(any("destino" in mensaje for mensaje in logs.output))


if __name__ == "__main__":
    unittest.main()
