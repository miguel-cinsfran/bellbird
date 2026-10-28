"""Armadores de PNG reales para las pruebas de la revisión de OBS.

Los usan tanto las pruebas del decodificador como las de la revisión:
un PNG plano de un color y uno armado píxel por píxel con un filtro dado.
"""

import binascii
import struct
import zlib


def _paeth(izquierda, arriba, diagonal):
    base = izquierda + arriba - diagonal
    da, db, dc = abs(base - izquierda), abs(base - arriba), abs(base - diagonal)
    if da <= db and da <= dc:
        return izquierda
    if db <= dc:
        return arriba
    return diagonal


def armar_png(ancho, alto, pixel, con_alfa=True, filtro=0):
    """PNG real armado con zlib en la propia prueba."""
    plano = 4 if con_alfa else 3
    anterior = bytearray(ancho * plano)
    crudo = bytearray()
    for y in range(alto):
        cruda = bytearray()
        for x in range(ancho):
            cruda += bytes(pixel(x, y))
        crudo.append(filtro)
        for i, valor in enumerate(cruda):
            izquierda = cruda[i - plano] if i >= plano else 0
            arriba = anterior[i]
            diagonal = anterior[i - plano] if i >= plano else 0
            if filtro == 0:
                crudo.append(valor)
            elif filtro == 1:
                crudo.append((valor - izquierda) & 255)
            elif filtro == 2:
                crudo.append((valor - arriba) & 255)
            elif filtro == 3:
                crudo.append((valor - ((izquierda + arriba) >> 1)) & 255)
            else:
                crudo.append((valor - _paeth(izquierda, arriba, diagonal)) & 255)
        anterior = cruda
    tipo = 6 if con_alfa else 2

    def trozo(nombre, cuerpo):
        return (struct.pack(">I", len(cuerpo)) + nombre + cuerpo
                + struct.pack(">I", binascii.crc32(nombre + cuerpo) & 0xffffffff))

    return (b"\x89PNG\r\n\x1a\n"
            + trozo(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, tipo,
                                        0, 0, 0))
            + trozo(b"IDAT", zlib.compress(bytes(crudo)))
            + trozo(b"IEND", b""))


def png_plano(ancho, alto, valores, con_alfa=True, filtro=0):
    return armar_png(ancho, alto, lambda x, y: valores, con_alfa, filtro)
