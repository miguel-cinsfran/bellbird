"""Tests de luz_imagen con BMP armados en la prueba con `struct`."""

import struct
import unittest

from bellbird.obs import luz_imagen


def armar_bmp(ancho, alto, pixel, bpp=24, de_arriba_abajo=False,
              compresion=0):
    """BMP sin comprimir donde `pixel(x, y)` da (rojo, verde, azul)."""
    por_pixel = bpp // 8
    paso = ((ancho * por_pixel + 3) // 4) * 4
    orden = range(alto) if de_arriba_abajo else range(alto - 1, -1, -1)
    cuerpo = bytearray()
    for y in orden:
        fila = bytearray()
        for x in range(ancho):
            (rojo, verde, azul) = pixel(x, y)
            fila += bytes((azul, verde, rojo))
            if por_pixel == 4:
                fila.append(0)
        fila += b"\x00" * (paso - len(fila))
        cuerpo += fila
    total = 54 + len(cuerpo)
    cabecera = struct.pack("<2sIHHI", b"BM", total, 0, 0, 54)
    alto_cabecera = -alto if de_arriba_abajo else alto
    dib = struct.pack("<IiiHHII", 40, ancho, alto_cabecera, 1, bpp,
                      compresion, 0) + struct.pack("<IIII", 0, 0, 0, 0)
    return bytes(cabecera + dib + cuerpo)


def parchear(bmp, formato, desplazamiento, valor):
    copia = bytearray(bmp)
    struct.pack_into(formato, copia, desplazamiento, valor)
    return bytes(copia)


NEGRO = lambda x, y: (0, 0, 0)  # noqa: E731


class TestProporcion(unittest.TestCase):
    def test_negro_da_cero(self):
        bmp = armar_bmp(64, 36, NEGRO)
        self.assertEqual(luz_imagen.proporcion_con_luz(bmp), 0.0)

    def test_cursor_sobre_negro_sigue_negra(self):
        # El cursor: un cuadrado de 3 por 3 a 255 sobre negro de 160x90.
        pixel = lambda x, y: (255, 255, 255) if 10 <= x < 13 and 10 <= y < 13 else (0, 0, 0)  # noqa: E731
        bmp = armar_bmp(160, 90, pixel)
        self.assertAlmostEqual(luz_imagen.proporcion_con_luz(bmp),
                               9 / (160 * 90))
        self.assertTrue(luz_imagen.es_negra(bmp))

    def test_cursor_sobre_negro_32_bits(self):
        pixel = lambda x, y: (255, 255, 255) if 10 <= x < 13 and 10 <= y < 13 else (0, 0, 0)  # noqa: E731
        bmp = armar_bmp(160, 90, pixel, bpp=32)
        self.assertTrue(luz_imagen.es_negra(bmp))

    def test_dos_porciento_no_es_negra(self):
        pixel = lambda x, y: (200, 10, 10) if y == 0 and x < 40 else (0, 0, 0)  # noqa: E731
        bmp = armar_bmp(50, 40, pixel)
        self.assertAlmostEqual(luz_imagen.proporcion_con_luz(bmp), 0.02)
        self.assertFalse(luz_imagen.es_negra(bmp))

    def test_dos_porciento_32_bits(self):
        pixel = lambda x, y: (10, 200, 10) if y == 0 and x < 40 else (0, 0, 0)  # noqa: E731
        bmp = armar_bmp(50, 40, pixel, bpp=32)
        self.assertFalse(luz_imagen.es_negra(bmp))

    def test_arriba_hacia_abajo_mide_igual(self):
        pixel = lambda x, y: (100, 0, 0) if x == y else (0, 0, 0)  # noqa: E731
        abajo = armar_bmp(8, 4, pixel)
        arriba = armar_bmp(8, 4, pixel, de_arriba_abajo=True)
        self.assertEqual(luz_imagen.proporcion_con_luz(abajo),
                         luz_imagen.proporcion_con_luz(arriba))
        self.assertEqual(luz_imagen.proporcion_con_luz(arriba), 4 / 32)

    def test_arriba_hacia_abajo_32_bits(self):
        pixel = lambda x, y: (0, 0, 100) if x == y else (0, 0, 0)  # noqa: E731
        bmp = armar_bmp(8, 4, pixel, bpp=32, de_arriba_abajo=True)
        self.assertEqual(luz_imagen.proporcion_con_luz(bmp), 4 / 32)

    def test_ancho_con_relleno(self):
        # 33 de ancho obliga a un byte de relleno por fila (99 a 100).
        pixel = lambda x, y: (x, 0, 0)  # noqa: E731
        bmp = armar_bmp(33, 2, pixel)
        self.assertAlmostEqual(luz_imagen.proporcion_con_luz(bmp), 16 / 66)
        self.assertFalse(luz_imagen.es_negra(bmp))

    def test_umbral_estricto(self):
        bmp = armar_bmp(2, 1, lambda x, y: (24, 24, 24) if x == 0 else (25, 0, 0))  # noqa: E731
        self.assertEqual(luz_imagen.proporcion_con_luz(bmp), 0.5)

    def test_subir_umbral_nunca_sube(self):
        pixel = lambda x, y: (x, 0, 0)  # noqa: E731
        bmp = armar_bmp(64, 4, pixel)
        baja = luz_imagen.proporcion_con_luz(bmp, umbral=10)
        media = luz_imagen.proporcion_con_luz(bmp)
        alta = luz_imagen.proporcion_con_luz(bmp, umbral=250)
        self.assertGreaterEqual(baja, media)
        self.assertGreaterEqual(media, alta)

    def test_alfa_no_cuenta(self):
        bmp = bytearray(armar_bmp(4, 4, NEGRO, bpp=32))
        for i in range(54, len(bmp), 4):
            bmp[i + 3] = 255
        self.assertEqual(luz_imagen.proporcion_con_luz(bytes(bmp)), 0.0)


class TestBordeNegra(unittest.TestCase):
    def test_borde_exacta_no_es_negra(self):
        # 100 píxeles de 20.000 son justo el 0,5 %: no es menor.
        blancos = {(x, 0) for x in range(100)}
        pixel = lambda x, y: (255, 255, 255) if (x, y) in blancos else (0, 0, 0)  # noqa: E731
        bmp = armar_bmp(200, 100, pixel)
        self.assertEqual(luz_imagen.proporcion_con_luz(bmp), 0.005)
        self.assertFalse(luz_imagen.es_negra(bmp))

    def test_un_pixel_menos_es_negra(self):
        blancos = {(x, 0) for x in range(99)}
        pixel = lambda x, y: (255, 255, 255) if (x, y) in blancos else (0, 0, 0)  # noqa: E731
        bmp = armar_bmp(200, 100, pixel)
        self.assertTrue(luz_imagen.es_negra(bmp))


class TestFormatosInvalidos(unittest.TestCase):
    def test_basura_da_none(self):
        self.assertIsNone(luz_imagen.proporcion_con_luz(b"\x00" * 60))
        self.assertIsNone(luz_imagen.es_negra(b"\x00" * 60))

    def test_vacio_da_none(self):
        self.assertIsNone(luz_imagen.proporcion_con_luz(b""))
        self.assertIsNone(luz_imagen.es_negra(b""))

    def test_truncado_da_none(self):
        bmp = armar_bmp(64, 36, NEGRO)
        self.assertIsNone(luz_imagen.proporcion_con_luz(bmp[:len(bmp) // 2]))
        self.assertIsNone(luz_imagen.es_negra(bmp[:len(bmp) // 2]))

    def test_comprimido_da_none(self):
        bmp = parchear(armar_bmp(8, 4, NEGRO), "<I", 30, 1)
        self.assertIsNone(luz_imagen.proporcion_con_luz(bmp))
        self.assertIsNone(luz_imagen.es_negra(bmp))

    def test_16_bits_da_none(self):
        bmp = parchear(armar_bmp(8, 4, NEGRO), "<H", 28, 16)
        self.assertIsNone(luz_imagen.proporcion_con_luz(bmp))

    def test_mascara_con_24_bits_da_none(self):
        bmp = parchear(armar_bmp(8, 4, NEGRO), "<I", 30, 3)
        self.assertIsNone(luz_imagen.proporcion_con_luz(bmp))

    def test_mascara_con_32_bits_mide(self):
        bmp = parchear(armar_bmp(8, 4, NEGRO, bpp=32), "<I", 30, 3)
        self.assertEqual(luz_imagen.proporcion_con_luz(bmp), 0.0)
        self.assertTrue(luz_imagen.es_negra(bmp))

    def test_gigante_da_none(self):
        bmp = parchear(armar_bmp(8, 4, NEGRO), "<i", 18, 5000)
        self.assertIsNone(luz_imagen.proporcion_con_luz(bmp))

    def test_alto_cero_da_none(self):
        bmp = parchear(armar_bmp(8, 4, NEGRO), "<i", 22, 0)
        self.assertIsNone(luz_imagen.proporcion_con_luz(bmp))

    def test_firma_rota_da_none(self):
        bmp = b"ZZ" + armar_bmp(8, 4, NEGRO)[2:]
        self.assertIsNone(luz_imagen.proporcion_con_luz(bmp))


if __name__ == "__main__":
    unittest.main()
