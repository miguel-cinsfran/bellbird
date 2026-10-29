"""Tests del decodificador de PNG de la escena."""

import binascii
import struct
import unittest
import zlib

from bellbird.obs import obs_png
from bellbird.obs.obs_png import imagen_vacia_png
from bellbird.obs.obs_prevuelo import EntradaAudio
from tests.png_prueba import armar_png, png_plano


def _trozo(nombre: bytes, cuerpo: bytes) -> bytes:
    return (struct.pack(">I", len(cuerpo)) + nombre + cuerpo
            + struct.pack(">I", binascii.crc32(nombre + cuerpo) & 0xffffffff))


def _png_con_idat(ancho, alto, tipo_color, carga_idat: bytes) -> bytes:
    """PNG con la carga IDAT dada, para forzar ramas del decodificador."""
    return (b"\x89PNG\r\n\x1a\n"
            + _trozo(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8,
                                         tipo_color, 0, 0, 0))
            + _trozo(b"IDAT", carga_idat)
            + _trozo(b"IEND", b""))


class ImagenVaciaPngTest(unittest.TestCase):
    def test_todo_transparente_es_vacia(self):
        self.assertIs(imagen_vacia_png(png_plano(3, 2, (0, 0, 0, 0))), True)

    def test_todo_negro_es_vacia(self):
        self.assertIs(imagen_vacia_png(png_plano(3, 2, (0, 0, 0, 255))), True)
        self.assertIs(imagen_vacia_png(png_plano(3, 2, (15, 15, 15, 255))),
                      True)

    def test_un_pixel_claro_no_es_vacia(self):
        png = armar_png(3, 2, lambda x, y: (200, 100, 50, 255)
                        if (x, y) == (1, 1) else (0, 0, 0, 0))
        self.assertIs(imagen_vacia_png(png), False)

    def test_pixel_claro_transparente_sigue_vacia(self):
        png = armar_png(2, 2, lambda x, y: (200, 200, 200, 0))
        self.assertIs(imagen_vacia_png(png), True)

    def test_rgb_sin_alfa(self):
        self.assertIs(imagen_vacia_png(png_plano(2, 2, (0, 0, 0), False)),
                      True)
        png = armar_png(2, 2, lambda x, y: (0, 200, 0) if (x, y) == (0, 0)
                        else (0, 0, 0), False)
        self.assertIs(imagen_vacia_png(png), False)

    def test_filtros_distintos_decodifican(self):
        for filtro in (0, 1, 2, 3, 4):
            with self.subTest(filtro=filtro):
                png = armar_png(
                    4, 3, lambda x, y: ((x * 40 + y * 7) % 256,
                                        (x * 13 + y * 29) % 256,
                                        (x * 5 + y * 11) % 256, 255),
                    filtro=filtro)
                self.assertIs(imagen_vacia_png(png), False)

    def test_basura_da_none(self):
        self.assertIsNone(imagen_vacia_png(b"esto no es un png"))
        self.assertIsNone(imagen_vacia_png(b""))
        png = armar_png(2, 2, lambda x, y: (0, 0, 0, 0))
        self.assertIsNone(imagen_vacia_png(png[:40]))

    def test_gris_sin_soporte_da_none(self):
        png = bytearray(armar_png(2, 2, lambda x, y: (0, 0, 0, 0)))
        png[25] = 0
        self.assertIsNone(imagen_vacia_png(bytes(png)))

    def test_entrada_audio_conserva_si_es_escritorio(self):
        self.assertFalse(EntradaAudio("Mic/Aux", False).escritorio)
        self.assertTrue(EntradaAudio("Audio del escritorio", False,
                                     True).escritorio)

    def test_trozo_truncado_da_none(self):
        png = armar_png(2, 2, lambda x, y: (0, 0, 0, 0))
        self.assertIsNone(imagen_vacia_png(png[:30]))

    def test_ihdr_con_largo_invalido_da_none(self):
        png = bytearray(armar_png(2, 2, lambda x, y: (0, 0, 0, 0)))
        png[8:12] = b"\x00\x00\x00\x05"
        self.assertIsNone(imagen_vacia_png(bytes(png)))

    def test_ancho_cero_da_none(self):
        png = bytearray(armar_png(2, 2, lambda x, y: (0, 0, 0, 0)))
        png[16:20] = b"\x00\x00\x00\x00"
        self.assertIsNone(imagen_vacia_png(bytes(png)))

    def test_dimension_enorme_da_none(self):
        png = bytearray(armar_png(2, 2, lambda x, y: (0, 0, 0, 0)))
        png[16:20] = struct.pack(">I", 5000)
        png[20:24] = struct.pack(">I", 5000)
        self.assertIsNone(imagen_vacia_png(bytes(png)))

    def test_idat_con_largo_incorrecto_da_none(self):
        png = _png_con_idat(2, 2, 6, zlib.compress(b"corto"))
        self.assertIsNone(imagen_vacia_png(png))

    def test_filtro_desconocido_da_none(self):
        png = _png_con_idat(1, 1, 6, zlib.compress(bytes([7, 0, 0, 0, 0])))
        self.assertIsNone(imagen_vacia_png(png))

    def test_idat_corrupto_da_none(self):
        png = _png_con_idat(2, 2, 6, b"esto-no-es-zlib")
        self.assertIsNone(imagen_vacia_png(png))

    def test_trozo_auxiliar_se_ignora(self):
        base = armar_png(2, 2, lambda x, y: (0, 0, 0, 0))
        con_texto = base[:33] + _trozo(b"tEXt", b"a\x00b") + base[33:]
        self.assertIs(imagen_vacia_png(con_texto), True)

    def test_paeth_elige_diagonal(self):
        self.assertEqual(obs_png._paeth(10, 200, 105), 105)

    def test_paeth_elige_arriba(self):
        self.assertEqual(obs_png._paeth(100, 0, 90), 0)


if __name__ == "__main__":
    unittest.main()
