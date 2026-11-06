"""Transformaciones puras de una fuente: centrar, ajustar, voltear y girar.

Todo lo de acá trabaja sobre el diccionario `sceneItemTransform` que entrega
OBS y devuelve una copia nueva. No habla con OBS ni con wx.
"""

from __future__ import annotations

import math

from guyrapu.core.idioma import _
from guyrapu.obs import tamano_relativo


def texto_de_tamano(ancho, lienzo_ancho) -> str:
    """El ancho de la fuente como parte del vídeo, en minúscula."""
    if not ancho or not lienzo_ancho:
        return ""
    porcentaje = int(round(float(ancho) / float(lienzo_ancho) * 100))
    clave = tamano_relativo.comun_de(porcentaje)
    if clave is not None:
        for candidata, nombre, _fraccion in tamano_relativo.COMUNES:
            if candidata == clave:
                texto = _(nombre)
                return texto[:1].lower() + texto[1:]
    return _("{p} por ciento del ancho").format(p=porcentaje)


def nombre_de_copia(ocupados, base) -> str:
    """El primer nombre libre con el sufijo de copia."""
    usados = {str(nombre).casefold() for nombre in ocupados or ()}
    candidato = _("{fuente} - copia").format(fuente=base)
    numero = 2
    while candidato.casefold() in usados:
        candidato = _("{fuente} - copia {n}").format(
            fuente=base, n=numero)
        numero += 1
    return candidato


def limpiar_transformacion(transformacion) -> dict:
    """Deja solo lo que OBS acepta al escribir una transformación.

    La lectura trae claves de solo lectura y, sin cuadro, bounds en cero.
    Mandarlas de vuelta hace que OBS rechace la operación.
    """
    from guyrapu.obs.restablecimiento import CLAVES_TRANSFORMACION
    limpia = {
        clave: valor for clave, valor in (transformacion or {}).items()
        if clave in CLAVES_TRANSFORMACION}
    if _sin_cuadro(limpia):
        for clave in ("boundsAlignment", "boundsWidth", "boundsHeight"):
            limpia.pop(clave, None)
    return limpia


def centro_de(transformacion) -> tuple:
    """El centro visible de la fuente, con la escala y el giro de OBS."""
    dx, dy = _desplazamiento_del_centro(transformacion)
    x = float(transformacion.get("positionX") or 0)
    y = float(transformacion.get("positionY") or 0)
    coseno, seno = _cos_sin(transformacion.get("rotation") or 0)
    return (x + dx * coseno - dy * seno,
            y + dx * seno + dy * coseno)


def caja_visible(transformacion) -> tuple:
    """La caja que ocupa la fuente: izquierda, arriba, ancho y alto."""
    ancho, alto = _extension_firmada(transformacion)
    ax, ay = _anclas(transformacion)
    xs = (ancho * -ax, ancho * (1 - ax))
    ys = (alto * -ay, alto * (1 - ay))
    puntos = [_punto_visible(transformacion, x, y)
              for x in xs for y in ys]
    izquierda = min(punto[0] for punto in puntos)
    arriba = min(punto[1] for punto in puntos)
    return (izquierda, arriba,
            max(punto[0] for punto in puntos) - izquierda,
            max(punto[1] for punto in puntos) - arriba)


def centrar(transformacion, lienzo_ancho, lienzo_alto) -> dict:
    """Pone el centro de la fuente en el centro del vídeo."""
    nueva = dict(transformacion)
    nueva["alignment"] = 0
    if "boundsAlignment" in nueva:
        nueva["boundsAlignment"] = 0
    nueva["positionX"] = float(lienzo_ancho) / 2
    nueva["positionY"] = float(lienzo_alto) / 2
    return nueva


def ajustar(transformacion, lienzo_ancho, lienzo_alto) -> dict:
    """Mete la fuente entera en el vídeo, con bandas si hace falta."""
    return _con_cuadro(
        transformacion, lienzo_ancho, lienzo_alto,
        "OBS_BOUNDS_SCALE_INNER")


def llenar(transformacion, lienzo_ancho, lienzo_alto) -> dict:
    """Agranda la fuente hasta cubrir todo el vídeo, recortando lo que sobra."""
    return _con_cuadro(
        transformacion, lienzo_ancho, lienzo_alto,
        "OBS_BOUNDS_SCALE_OUTER")


def voltear_horizontal(transformacion) -> dict:
    """Invierte el eje horizontal sin mover el centro de la fuente."""
    nueva = dict(transformacion)
    nueva["scaleX"] = -_escala(transformacion.get("scaleX"))
    return _conservando_centro(transformacion, nueva)


def voltear_vertical(transformacion) -> dict:
    """Invierte el eje vertical sin mover el centro de la fuente."""
    nueva = dict(transformacion)
    nueva["scaleY"] = -_escala(transformacion.get("scaleY"))
    return _conservando_centro(transformacion, nueva)


def girar(transformacion, grados) -> dict:
    """Gira la fuente los grados pedidos alrededor de su centro."""
    nueva = dict(transformacion)
    nueva["rotation"] = (
        float(transformacion.get("rotation") or 0) + float(grados)) % 360
    return _conservando_centro(transformacion, nueva)


def restablecer(transformacion) -> dict:
    """Devuelve la fuente a su tamaño original, arriba a la izquierda."""
    return {
        "positionX": 0, "positionY": 0, "alignment": 5,
        "rotation": 0, "scaleX": 1, "scaleY": 1,
        "boundsType": "OBS_BOUNDS_NONE",
        "cropLeft": 0, "cropRight": 0, "cropTop": 0, "cropBottom": 0,
    }


def frase_de_accion(fila, frase) -> str:
    """La acción y el estado nuevo de la fuente, en una sola frase."""
    primera = f"{fila.nombre} {frase}".strip()
    if primera and not primera.endswith("."):
        primera += "."
    partes = [primera]
    for dato in (getattr(fila, "posicion", ""),
                 getattr(fila, "tamano", "")):
        if dato:
            partes.append(dato[:1].upper() + dato[1:] + ".")
    return " ".join(partes)


def _con_cuadro(transformacion, lienzo_ancho, lienzo_alto, tipo):
    nueva = dict(transformacion)
    nueva["boundsType"] = tipo
    nueva["boundsAlignment"] = 0
    ancho, alto = float(lienzo_ancho), float(lienzo_alto)
    if abs(float(transformacion.get("rotation") or 0) % 180 - 90) < 1e-6:
        ancho, alto = alto, ancho
    nueva["boundsWidth"] = ancho
    nueva["boundsHeight"] = alto
    nueva["alignment"] = 0
    nueva["positionX"] = float(lienzo_ancho) / 2
    nueva["positionY"] = float(lienzo_alto) / 2
    return nueva


def _conservando_centro(original, nueva):
    centro = centro_de(original)
    nueva["positionX"], nueva["positionY"] = _posicion_para_centro(
        nueva, centro)
    return nueva


def _posicion_para_centro(transformacion, centro):
    dx, dy = _desplazamiento_del_centro(transformacion)
    coseno, seno = _cos_sin(transformacion.get("rotation") or 0)
    return (centro[0] - (dx * coseno - dy * seno),
            centro[1] - (dx * seno + dy * coseno))


def _desplazamiento_del_centro(transformacion):
    ancho, alto = _extension_firmada(transformacion)
    ax, ay = _anclas(transformacion)
    return ancho * (0.5 - ax), alto * (0.5 - ay)


def _extension_firmada(transformacion):
    escala_x = _escala(transformacion.get("scaleX"))
    escala_y = _escala(transformacion.get("scaleY"))
    if _tiene_cuadro(transformacion):
        ancho = float(transformacion.get("boundsWidth") or 0) * _signo(escala_x)
        alto = float(transformacion.get("boundsHeight") or 0) * _signo(escala_y)
        return ancho, alto
    ancho = escala_x * float(transformacion.get("sourceWidth") or 0)
    alto = escala_y * float(transformacion.get("sourceHeight") or 0)
    return ancho, alto


def _punto_visible(transformacion, x, y):
    coseno, seno = _cos_sin(transformacion.get("rotation") or 0)
    return (
        float(transformacion.get("positionX") or 0) + x * coseno - y * seno,
        float(transformacion.get("positionY") or 0) + x * seno + y * coseno)


def _anclas(transformacion):
    alineacion = int(transformacion.get("alignment") or 0)
    ax = 0 if alineacion & 1 else 1 if alineacion & 2 else 0.5
    ay = 0 if alineacion & 4 else 1 if alineacion & 8 else 0.5
    return ax, ay


def _tiene_cuadro(transformacion):
    tipo = str(transformacion.get("boundsType") or "").upper()
    return tipo not in ("", "NONE", "OBS_BOUNDS_NONE")


def _sin_cuadro(transformacion):
    if not _tiene_cuadro(transformacion):
        return True
    try:
        return (float(transformacion.get("boundsWidth") or 0) < 1
                or float(transformacion.get("boundsHeight") or 0) < 1)
    except (TypeError, ValueError):
        return True


def _escala(valor):
    numero = float(valor or 1)
    return numero if numero else 1.0


def _signo(valor):
    return -1.0 if float(valor) < 0 else 1.0


def _cos_sin(grados):
    angulo = float(grados) % 360
    exactos = {0.0: (1.0, 0.0), 90.0: (0.0, 1.0),
               180.0: (-1.0, 0.0), 270.0: (0.0, -1.0)}
    if angulo in exactos:
        return exactos[angulo]
    radianes = math.radians(angulo)
    return math.cos(radianes), math.sin(radianes)
