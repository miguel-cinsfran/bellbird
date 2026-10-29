"""Pseudotraducción de los avisos y cuadros del envío al chat.

Sin ventanas: el MessageBox va simulado y la API también. El mensaje de
error lo arma `bellbird/youtube/youtube_api.py`: pasa tal cual, sin marcar.
"""

import unittest
from unittest import mock

from tests.pseudo_prueba import con_pseudo
from bellbird.ui import gui
from bellbird.ui import gui_envio_chat as envio


def _hilo_inmediato(objetivo, _nombre):
    hilo = mock.Mock()
    hilo.start.side_effect = lambda: objetivo()
    return hilo


class TestPseudoEnvioChat(unittest.TestCase):
    """Los textos propios salen marcados; el error ajeno pasa tal cual."""

    def test_mensaje_enviado_sale_marcado(self):
        frame = mock.Mock()
        frame.sesion.live_chat_id = "LCID"
        with con_pseudo():
            envio.enviar_live_redactado(frame, "hola")
        _accion, mensaje = frame._accion_api.call_args.args
        self.assertTrue(mensaje.startswith("[¡"), mensaje)

    def test_enviando_sale_marcado(self):
        frame = mock.Mock()
        captados = []
        with con_pseudo(), \
                mock.patch.object(gui, "anunciar", captados.append), \
                mock.patch.object(gui.diagnostico, "crear_hilo",
                                  side_effect=_hilo_inmediato), \
                mock.patch.object(gui, "credenciales"), \
                mock.patch.object(gui, "youtube_api"), \
                mock.patch.object(gui.wx, "CallAfter",
                                  side_effect=lambda f, *a: f(*a)):
            envio.accion_api(frame, mock.Mock(), "Mensaje enviado al chat")
        self.assertEqual(captados, ["[¡Enviando!]"])
        frame._api_ok.assert_called_once_with("Mensaje enviado al chat",
                                              "enviado")

    def test_error_de_api_cuadro_propio_y_mensaje_ajeno(self):
        frame = mock.Mock()
        captado = {}

        def caja(mensaje, titulo, estilo, padre=None):
            captado["mensaje"] = mensaje
            captado["titulo"] = titulo
            return gui.wx.ID_OK

        with con_pseudo(), \
                mock.patch.object(gui.wx, "MessageBox", caja), \
                mock.patch.object(gui._snd, "reproducir"), \
                mock.patch.object(gui, "anunciar"), \
                mock.patch.object(gui.youtube_api, "sesion_caducada",
                                  return_value=False), \
                mock.patch.object(gui.youtube_api, "mensaje_error_api",
                                  return_value="falla ajena"), \
                mock.patch("bellbird.ui.gui_preferencias.ofrecer_iniciar_sesion",
                           return_value=False):
            envio.api_err(frame, RuntimeError("x"))
        self.assertTrue(captado["titulo"].startswith("[¡"), captado)
        self.assertEqual(captado["mensaje"], "falla ajena")

    def test_sesion_caducada_anuncia_el_mensaje_ajeno(self):
        frame = mock.Mock()
        captados = []
        with con_pseudo(), \
                mock.patch.object(gui.youtube_api, "sesion_caducada",
                                  return_value=True), \
                mock.patch.object(gui.youtube_api, "mensaje_error_api",
                                  return_value="sesión caducada"), \
                mock.patch.object(gui, "anunciar", captados.append), \
                mock.patch.object(gui._snd, "reproducir"), \
                mock.patch("bellbird.ui.gui_preferencias.ofrecer_iniciar_sesion",
                           return_value=False):
            envio.api_err(frame, RuntimeError("x"))
        self.assertEqual(captados, ["sesión caducada"])
        frame._actualizar_estado_online.assert_called_once_with()

    def test_programados_detenidos_salen_marcados(self):
        for caducada in (True, False):
            with self.subTest(caducada=caducada):
                frame = mock.Mock()
                frame._config = {"programados_activo": True}
                captados = []
                with con_pseudo(), \
                        mock.patch.object(gui.youtube_api, "sesion_caducada",
                                          return_value=caducada), \
                        mock.patch.object(gui, "anunciar",
                                          captados.append):
                    envio.programado_fallo(frame, RuntimeError("x"))
                self.assertEqual(len(captados), 1)
                self.assertTrue(captados[0].startswith("[¡"), captados)
                self.assertFalse(frame._config["programados_activo"])

    def test_moderar_pregunta_titulo_y_aviso_salen_marcados(self):
        for segundos in (300, None):
            with self.subTest(segundos=segundos):
                frame = mock.Mock()
                frame.sesion.live_chat_id = "LCID"
                captado = {}

                def caja(mensaje, titulo, estilo, padre=None):
                    captado["mensaje"] = mensaje
                    captado["titulo"] = titulo
                    return gui.wx.YES

                with con_pseudo(), \
                        mock.patch.object(gui.wx, "MessageBox", caja):
                    envio.moderar(frame, "Ana", "CANAL", segundos)
                self.assertTrue(captado["mensaje"].startswith("[¡"),
                                captado)
                self.assertTrue(captado["titulo"].startswith("[¡"), captado)
                _accion, ok = frame._accion_api.call_args.args
                self.assertTrue(ok.startswith("[¡"), ok)

    def test_moderar_con_no_no_actua(self):
        frame = mock.Mock()
        with mock.patch.object(gui.wx, "MessageBox",
                               return_value=gui.wx.NO):
            envio.moderar(frame, "Ana", "CANAL", 300)
        frame._accion_api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
