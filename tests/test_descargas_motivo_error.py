"""Pruebas de motivo_de_error: la causa en llano de un fallo de yt-dlp."""

import unittest

from ytchat.downloads.motivo_error import motivo_de_error


EDAD = ("ERROR: [youtube] O2yixU7XjGU: Sign in to confirm your age. Use "
        "--cookies-from-browser or --cookies for the authentication.")


class TestMotivoDeError(unittest.TestCase):

    def test_edad_restringida(self):
        self.assertEqual(
            motivo_de_error(EDAD),
            "El vídeo tiene restricción de edad y YouTube pide iniciar sesión.")

    def test_edad_con_otras_mayusculas(self):
        self.assertEqual(
            motivo_de_error(EDAD.replace("Sign in to confirm your age",
                                         "SIGN IN TO CONFIRM YOUR AGE")),
            "El vídeo tiene restricción de edad y YouTube pide iniciar sesión.")

    def test_marca_age_restricted(self):
        self.assertEqual(
            motivo_de_error("ERROR: [youtube] abc: This video is age-restricted."),
            "El vídeo tiene restricción de edad y YouTube pide iniciar sesión.")

    def test_privado(self):
        self.assertEqual(
            motivo_de_error("ERROR: [youtube] abc: Private video. Sign in if "
                            "you've been granted access to this video."),
            "El vídeo es privado.")

    def test_solo_miembros(self):
        self.assertEqual(
            motivo_de_error("ERROR: [youtube] abc: Join this channel to get "
                            "access to members-only content like this video."),
            "El vídeo es solo para miembros del canal.")

    def test_solo_miembros_sin_invitacion(self):
        self.assertEqual(
            motivo_de_error("ERROR: [youtube] abc: This is a members-only video."),
            "El vídeo es solo para miembros del canal.")

    def test_no_robot(self):
        self.assertEqual(
            motivo_de_error("ERROR: [youtube] abc: Sign in to confirm you're "
                            "not a bot. Use --cookies-from-browser."),
            "YouTube pide confirmar que no eres un robot. Vuelve a "
            "intentarlo más tarde.")

    def test_no_disponible(self):
        self.assertEqual(
            motivo_de_error("ERROR: [youtube] abc: Video unavailable"),
            "El vídeo no está disponible.")

    def test_no_disponible_en_frase(self):
        self.assertEqual(
            motivo_de_error("ERROR: [youtube] abc: This video is not available."),
            "El vídeo no está disponible.")

    def test_desconocido_da_none(self):
        self.assertIsNone(
            motivo_de_error("ERROR: [youtube] abc: Unable to download webpage"))

    def test_none_da_none(self):
        self.assertIsNone(motivo_de_error(None))

    def test_vacio_da_none(self):
        self.assertIsNone(motivo_de_error(""))


if __name__ == "__main__":
    unittest.main()
