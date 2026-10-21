"""Dice si una captura BMP de OBS está negra o casi negra.

Puro, solo biblioteca estándar: el BMP chico lo da OBS en 2 ms y se lee
con `struct`, sin decodificar el JPEG con wx ni sumar Pillow.
"""

from __future__ import annotations

import struct


# Medidos el 21/10/2026 en esta PC: con la cortina de pantalla de NVDA la
# captura sale negra salvo el cursor, que queda a 255 y ocupa unos 9
# píxeles de 14.400 (el 0,06 %); el brillo medio dio 1.
UMBRAL_LUZ = 24
PROPORCION_NEGRA = 0.005

_LADO_MAXIMO = 4096


def _cabecera(datos):
    """Ancho, alto, bits y desplazamiento a píxeles, o None si no es BMP."""
    if not isinstance(datos, (bytes, bytearray, memoryview)):
        return None
    if len(datos) < 54 or bytes(datos[0:2]) != b"BM":
        return None
    try:
        (_tam, _r1, _r2, desplazamiento) = struct.unpack("<IHHI", datos[2:14])
        tam_dib = struct.unpack("<I", datos[14:18])[0]
        if tam_dib < 40 or len(datos) < 14 + tam_dib:
            return None
        (ancho, alto, planos, bits, compresion) = struct.unpack(
            "<iiHHI", datos[18:34])
    except struct.error:
        return None
    if planos != 1 or bits not in (24, 32):
        return None
    if compresion != 0 and not (compresion == 3 and bits == 32):
        return None
    alto = abs(alto)
    if ancho <= 0 or alto <= 0:
        return None
    if ancho > _LADO_MAXIMO or alto > _LADO_MAXIMO:
        return None
    if desplazamiento < 14 + tam_dib or desplazamiento > len(datos):
        return None
    return (ancho, alto, bits, desplazamiento)


def proporcion_con_luz(bmp, umbral=UMBRAL_LUZ):
    """Fracción de píxeles con luz mayor que `umbral`, o None.

    Solo BMP sin comprimir (0, o 3 con 32 bits) de 24 o 32 bits, filas de
    abajo hacia arriba o de arriba hacia abajo. La luz de un píxel es el
    mayor de sus tres canales; el alfa no cuenta. Cualquier otro formato,
    un BMP roto o truncado, o más de 4.096 por lado, da None.
    """
    cabecera = _cabecera(bmp)
    if cabecera is None:
        return None
    (ancho, alto, bits, desplazamiento) = cabecera
    por_pixel = bits // 8
    paso = ((ancho * por_pixel + 3) // 4) * 4
    if desplazamiento + paso * alto > len(bmp):
        return None
    con_luz = 0
    for fila in range(alto):
        base = desplazamiento + fila * paso
        for equis in range(ancho):
            o = base + equis * por_pixel
            if bmp[o] > umbral or bmp[o + 1] > umbral or bmp[o + 2] > umbral:
                con_luz += 1
    return con_luz / (ancho * alto)


def es_negra(bmp):
    """True si casi no hay luz, False si hay, None si no se pudo medir."""
    proporcion = proporcion_con_luz(bmp)
    if proporcion is None:
        return None
    return proporcion < PROPORCION_NEGRA
