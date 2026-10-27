"""Sesión conectada sin wx: valores por defecto y regla del chat."""

import unittest

from ytchat.capture import deteccion
from ytchat.ui.sesion_conectada import SesionConectada


class TestSesionConectada(unittest.TestCase):

    def test_nueva_sesion_trae_los_diez_valores(self):
        sesion = SesionConectada()
        self.assertEqual(sesion.live_chat_id, "")
        self.assertEqual(sesion.video_id, "")
        self.assertEqual(sesion.enlace_directo, "")
        self.assertEqual(sesion.causa_sin_chat, "")
        self.assertEqual(sesion.usuario_tiktok, "")
        self.assertEqual(sesion.conexion_propia, False)
        self.assertEqual(sesion.chat_propio, False)
        self.assertEqual(sesion.tipo_video, deteccion.DESCONOCIDO)
        self.assertEqual(sesion.es_tiktok, False)
        self.assertEqual(sesion.descartes_avisado, False)

    def test_acepta_chat_de_sin_video_id(self):
        sesion = SesionConectada(video_id="abc")
        self.assertTrue(sesion.acepta_chat_de(None))

    def test_acepta_chat_del_mismo_video(self):
        sesion = SesionConectada(video_id="abc")
        self.assertTrue(sesion.acepta_chat_de("abc"))

    def test_rechaza_chat_de_otro_video(self):
        sesion = SesionConectada(video_id="nuevo")
        self.assertFalse(sesion.acepta_chat_de("viejo"))


if __name__ == "__main__":
    unittest.main()
