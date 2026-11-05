"""Pruebas de la comparación entre el YouTube de Restream y la sesión."""

import unittest

from guyrapu.restream import canal_youtube
from guyrapu.restream.api import Canal


def _canal(plataforma_id, nombre, identificador="", activo=True):
    return Canal(1, plataforma_id, "Plataforma", nombre, "", activo,
                 identificador)


class TestComparar(unittest.TestCase):

    def test_sin_canal_de_youtube(self):
        canales = [_canal(67, "tiktok", "uno"), _canal(1, "twitch", "dos")]
        self.assertEqual(canal_youtube.SIN_CANAL,
                         canal_youtube.comparar(canales, "UCsesion"))

    def test_sin_sesion_de_la_app(self):
        canales = [_canal(5, "youtube", "UCrestream")]
        self.assertEqual(canal_youtube.SIN_CANAL,
                         canal_youtube.comparar(canales, ""))

    def test_coinciden(self):
        canales = [_canal(5, "youtube", "UCsesion")]
        self.assertEqual(canal_youtube.COINCIDEN,
                         canal_youtube.comparar(canales, "UCsesion"))

    def test_no_coinciden(self):
        canales = [_canal(5, "youtube", "UCrestream")]
        self.assertEqual(canal_youtube.NO_COINCIDEN,
                         canal_youtube.comparar(canales, "UCsesion"))

    def test_dos_canales_de_youtube_coincide_el_segundo(self):
        canales = [_canal(5, "primero", "UCotro"),
                   _canal(5, "segundo", "UCsesion")]
        self.assertEqual(canal_youtube.COINCIDEN,
                         canal_youtube.comparar(canales, "UCsesion"))


class TestTexto(unittest.TestCase):

    def test_coinciden_con_los_nombres_en_orden(self):
        canales = [_canal(5, "primero", "UCotro"),
                   _canal(5, "segundo", "UCsesion")]
        self.assertEqual(
            "YouTube en Restream: primero, segundo, el mismo canal de la "
            "sesión de Bellbird.",
            canal_youtube.texto(canales, "UCsesion"))

    def test_no_coinciden(self):
        canales = [_canal(5, "primero", "UCotro")]
        self.assertEqual(
            "YouTube en Restream: primero, que no es el canal de la sesión "
            "de Bellbird.",
            canal_youtube.texto(canales, "UCsesion"))

    def test_sin_linea(self):
        canales = [_canal(67, "tiktok", "uno")]
        self.assertEqual("", canal_youtube.texto(canales, "UCsesion"))
        self.assertEqual("", canal_youtube.texto(
            [_canal(5, "youtube", "UCsesion")], ""))


if __name__ == "__main__":
    unittest.main()
