"""Dice si el PNG de la escena está vacío, sin hablar con OBS.

Recibe los bytes del PNG y devuelve si trae solo negro o transparencia.
Lo usa la revisión previa a transmitir con la captura ya decodificada.
"""

import struct
import zlib


# Un píxel con algún canal por encima de esto ya es imagen, no negro.
_UMBRAL_NEGRO = 16


def _paeth(izquierda, arriba, diagonal) -> int:
    base = izquierda + arriba - diagonal
    da, db, dc = abs(base - izquierda), abs(base - arriba), abs(base - diagonal)
    if da <= db and da <= dc:
        return izquierda
    if db <= dc:
        return arriba
    return diagonal


def _trozos_png(datos: bytes):
    """Firma y trozos de un PNG, o None si no es un PNG sano.

    Devuelve (ancho, alto, profundidad, color, compresión, filtro,
    entrelazado, idat). Los trozos auxiliares se ignoran.
    """
    if bytes(datos[:8]) != b"\x89PNG\r\n\x1a\n":
        return None
    ancho = alto = None
    profundidad = color = compresion = filtro = entrelazado = None
    idat = b""
    posicion = 8
    while posicion + 8 <= len(datos):
        (largo, tipo) = struct.unpack(">I4s", datos[posicion:posicion + 8])
        inicio = posicion + 8
        fin = inicio + largo
        if fin + 4 > len(datos):
            return None
        cuerpo = datos[inicio:fin]
        if tipo == b"IHDR":
            if largo != 13:
                return None
            (ancho, alto, profundidad, color, compresion, filtro,
             entrelazado) = struct.unpack(">IIBBBBB", cuerpo)
        elif tipo == b"IDAT":
            idat += cuerpo
        elif tipo == b"IEND":
            break
        posicion = fin + 4
    if ancho is None or not idat:
        return None
    return (ancho, alto, profundidad, color, compresion, filtro,
            entrelazado, idat)


def _formato_soportado(profundidad, color, compresion, filtro,
                       entrelazado) -> bool:
    return (profundidad == 8 and color in (2, 6) and compresion == 0
            and filtro == 0 and entrelazado == 0)


def _tamanio_razonable(ancho, alto) -> bool:
    return ancho > 0 and alto > 0 and ancho * alto <= 4096 * 4096


def _revertir_filtro(codigo, linea, anterior, por_pixel) -> bool:
    """Deshace el filtro PNG de una línea. Falso si el filtro no existe."""
    paso = len(linea)
    if codigo == 1:
        for i in range(por_pixel, paso):
            linea[i] = (linea[i] + linea[i - por_pixel]) & 255
    elif codigo == 2:
        for i in range(paso):
            linea[i] = (linea[i] + anterior[i]) & 255
    elif codigo == 3:
        for i in range(paso):
            izquierda = linea[i - por_pixel] if i >= por_pixel else 0
            linea[i] = (linea[i] + ((izquierda + anterior[i]) >> 1)) & 255
    elif codigo == 4:
        for i in range(paso):
            izquierda = linea[i - por_pixel] if i >= por_pixel else 0
            arriba = anterior[i]
            diagonal = anterior[i - por_pixel] if i >= por_pixel else 0
            linea[i] = (linea[i] + _paeth(izquierda, arriba, diagonal)) & 255
    elif codigo != 0:
        return False
    return True


def _linea_rgba_con_imagen(linea) -> bool:
    for i in range(0, len(linea), 4):
        if linea[i + 3] == 0:
            continue
        if (linea[i] >= _UMBRAL_NEGRO
                or linea[i + 1] >= _UMBRAL_NEGRO
                or linea[i + 2] >= _UMBRAL_NEGRO):
            return True
    return False


def _linea_rgb_con_imagen(linea) -> bool:
    for i in range(0, len(linea), 3):
        if (linea[i] >= _UMBRAL_NEGRO
                or linea[i + 1] >= _UMBRAL_NEGRO
                or linea[i + 2] >= _UMBRAL_NEGRO):
            return True
    return False


def _linea_con_imagen(linea, color) -> bool:
    if color == 6:
        return _linea_rgba_con_imagen(linea)
    return _linea_rgb_con_imagen(linea)


def _pixeles_vacios(crudo: bytes, ancho, alto, color):
    """¿Todos los píxeles son negro o transparencia? None si el largo no
    coincide con las dimensiones de la cabecera."""
    por_pixel = 3 if color == 2 else 4
    paso = ancho * por_pixel
    if len(crudo) != alto * (1 + paso):
        return None
    anterior = bytearray(paso)
    desplazamiento = 0
    for _sin_uso in range(alto):
        codigo = crudo[desplazamiento]
        desplazamiento += 1
        linea = bytearray(crudo[desplazamiento:desplazamiento + paso])
        desplazamiento += paso
        if not _revertir_filtro(codigo, linea, anterior, por_pixel):
            return None
        if _linea_con_imagen(linea, color):
            return False
        anterior = linea
    return True


def imagen_vacia_png(datos: bytes) -> bool | None:
    """¿El PNG trae solo negro o transparencia? None si no se puede saber.

    Decodifica con `zlib` y `struct` de la biblioteca estándar: filtros PNG
    0 a 4, color tipo 6 (RGBA) y 2 (RGB), 8 bits. Cualquier otro formato o
    un PNG roto devuelve None en vez de adivinar.
    """
    try:
        trozos = _trozos_png(datos)
        if trozos is None:
            return None
        (ancho, alto, profundidad, color, compresion, filtro, entrelazado,
         idat) = trozos
        if not _formato_soportado(profundidad, color, compresion, filtro,
                                  entrelazado):
            return None
        if not _tamanio_razonable(ancho, alto):
            return None
        return _pixeles_vacios(zlib.decompress(idat), ancho, alto, color)
    except Exception:
        return None
