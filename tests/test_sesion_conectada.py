"""Sesión conectada sin wx: valores por defecto y regla del chat."""

import unittest

from bellbird.capture import deteccion
from bellbird.ui.sesion_conectada import SesionConectada


class TestSesionConectada(unittest.TestCase):

    def test_nueva_sesion_trae_los_once_valores(self):
        sesion = SesionConectada()
        self.assertEqual(sesion.live_chat_id, "")
        self.assertEqual(sesion.video_id, "")
        self.assertEqual(sesion.enlace_directo, "")
        self.assertEqual(sesion.causa_sin_chat, "")
        self.assertEqual(sesion.usuario_tiktok, "")
        self.assertEqual(sesion.url_flujo_tiktok, "")
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


class TestEsReconexionTiktok(unittest.TestCase):

    def test_mismo_usuario_tiktok_es_reconexion(self):
        sesion = SesionConectada(es_tiktok=True, usuario_tiktok="manu")
        self.assertTrue(sesion.es_reconexion_tiktok("manu"))

    def test_otro_usuario_no_es_reconexion(self):
        sesion = SesionConectada(es_tiktok=True, usuario_tiktok="manu")
        self.assertFalse(sesion.es_reconexion_tiktok("otro"))

    def test_usuario_vacio_no_es_reconexion(self):
        sesion = SesionConectada(es_tiktok=True, usuario_tiktok="")
        self.assertFalse(sesion.es_reconexion_tiktok("manu"))

    def test_sin_tiktok_no_es_reconexion(self):
        sesion = SesionConectada(es_tiktok=False, usuario_tiktok="manu")
        self.assertFalse(sesion.es_reconexion_tiktok("manu"))


if __name__ == "__main__":
    unittest.main()
