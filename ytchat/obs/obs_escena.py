"""Descripción hablada de la escena al aire de OBS.

Arma, solo con los datos que ya entrega OBS, la frase que dice cómo está
armada la escena: qué fuentes tiene, en qué orden (qué está adelante de
qué), dónde está cada una, si se ve y si algo la tapa. Es lógica pura, sin
wx ni red: la usan el atajo Ctrl+F2 y la ventana Transmisión.
"""

from __future__ import annotations

from ytchat.obs import obs_disposicion


# Cubre este porcentaje del lienzo o más y se considera imagen completa.
_UMBRAL_TODO = 95.0
# Tapada en este porcentaje o más por una fuente visible de más adelante,
# se considera que no aparece en la imagen.
_UMBRAL_TAPA_ENTERA = 95.0
# Por debajo de este porcentaje de tapa o de recorte no se dice nada.
_UMBRAL_AVISO = 10.0


def _rectangulo_de(elemento):
    """Rectángulo visible (izquierda, arriba, ancho, alto) o None.

    None cuando la transformación no sirve: falta, no es un dict o no
    trae posición y tamaño positivos. Con bounds activos el tamaño
    visible sale de boundsWidth y boundsHeight.
    """
    try:
        transformacion = elemento.get("sceneItemTransform") or {}
        x = float(transformacion["positionX"])
        y = float(transformacion["positionY"])
        ancho = float(transformacion.get("width", 0))
        alto = float(transformacion.get("height", 0))
        tipo_bounds = str(transformacion.get("boundsType") or "").upper()
        if tipo_bounds not in ("", "NONE", "OBS_BOUNDS_NONE"):
            ancho_bounds = float(transformacion.get("boundsWidth") or 0)
            alto_bounds = float(transformacion.get("boundsHeight") or 0)
            if ancho_bounds > 0 and alto_bounds > 0:
                ancho, alto = ancho_bounds, alto_bounds
        if ancho <= 0 or alto <= 0:
            return None
        alineacion = int(transformacion.get("alignment", 0))
        return obs_disposicion.rectangulo(x, y, ancho, alto, alineacion)
    except (KeyError, TypeError, ValueError):
        return None


def _visible(elemento) -> bool:
    return bool(elemento.get("sceneItemEnabled", True))


def zona_cercana(rect, lienzo_ancho, lienzo_alto) -> str:
    """Nombre del anclaje más cercano por el centro del rectángulo.

    Los nueve anclajes forman una cuadrícula de tres por tres sobre el
    lienzo. Cuando el rectángulo no calza en ninguno (anclaje_de pide el
    margen del 2 %), se elige el más cercano comparando centros: el del
    rectángulo contra el que tendría ese mismo tamaño puesto en cada
    anclaje. Así un panel grande en la esquina sigue diciendo esa
    esquina aunque su centro caiga en otra celda.
    """
    try:
        if not rect or not lienzo_ancho or not lienzo_alto:
            return ""
        centro_x = float(rect[0]) + float(rect[2]) / 2
        centro_y = float(rect[1]) + float(rect[3]) / 2
    except (TypeError, ValueError, IndexError):
        return ""
    mejor, mejor_distancia = "", None
    for nombre in obs_disposicion.ANCLAJES:
        x, y, alineacion = obs_disposicion.coordenadas(
            nombre, lienzo_ancho, lienzo_alto)
        esperado = obs_disposicion.rectangulo(
            x, y, rect[2], rect[3], alineacion)
        esperado_x = esperado[0] + esperado[2] / 2
        esperado_y = esperado[1] + esperado[3] / 2
        distancia = ((centro_x - esperado_x) ** 2
                     + (centro_y - esperado_y) ** 2)
        if mejor_distancia is None or distancia < mejor_distancia:
            mejor, mejor_distancia = nombre, distancia
    return mejor


def _texto_de_anclaje(nombre, rect, lienzo_ancho, lienzo_alto) -> str:
    """Texto en minúscula del anclaje dado, con los mismos textos de siempre.

    Arma un rectángulo de ese mismo tamaño puesto justo en el anclaje y
    lo describe con el panel: si esa tabla cambia, esta frase la sigue.
    """
    x, y, alineacion = obs_disposicion.coordenadas(
        nombre, lienzo_ancho, lienzo_alto)
    esperado = obs_disposicion.rectangulo(
        x, y, rect[2], rect[3], alineacion)
    snap = obs_disposicion.SnapshotPanel(
        conectado=True, izquierda=esperado[0], arriba=esperado[1],
        ancho=int(round(esperado[2])), alto=int(round(esperado[3])),
        lienzo_ancho=lienzo_ancho, lienzo_alto=lienzo_alto)
    texto = obs_disposicion.describir(snap, ("posicion",), "corto")
    if not texto:
        return ""
    texto = texto[:-1] if texto.endswith(".") else texto
    return texto[:1].lower() + texto[1:]


def _texto_anclaje(rect, lienzo_ancho, lienzo_alto) -> str:
    """Texto del anclaje en minúscula, o zona cercana con «cerca» si no calza.

    Reusa la descripción de posición del panel en vez de copiar su tabla:
    si esa tabla cambia, esta frase la sigue.
    """
    if not obs_disposicion.anclaje_de(rect, lienzo_ancho, lienzo_alto):
        nombre = zona_cercana(rect, lienzo_ancho, lienzo_alto)
        if not nombre:
            return ""
        texto = _texto_de_anclaje(nombre, rect, lienzo_ancho, lienzo_alto)
        if not texto:
            return ""
        if texto.startswith("esquina"):
            return f"cerca de la {texto}"
        return f"cerca del {texto}"
    snap = obs_disposicion.SnapshotPanel(
        conectado=True, izquierda=rect[0], arriba=rect[1],
        ancho=int(round(rect[2])), alto=int(round(rect[3])),
        lienzo_ancho=lienzo_ancho, lienzo_alto=lienzo_alto)
    texto = obs_disposicion.describir(snap, ("posicion",), "corto")
    if not texto:
        return ""
    texto = texto[:-1] if texto.endswith(".") else texto
    return texto[:1].lower() + texto[1:]


def _quien_mas_tapa(rect, delanteros) -> tuple:
    """(nombre, porcentaje) de la fuente visible que más tapa a rect.

    Solo cuentan las fuentes visibles de más adelante. Si ninguna tapa
    nada, devuelve (None, 0.0).
    """
    nombre = None
    maximo = 0.0
    for otro_nombre, otro_rect in delanteros:
        porcentaje = obs_disposicion.solape(otro_rect, rect)
        if porcentaje > maximo:
            nombre, maximo = otro_nombre, porcentaje
    return nombre, maximo


def _frase_fuente(numero, elemento, rect, delanteros, lienzo_ancho,
                  lienzo_alto, tipos) -> str:
    nombre = str(elemento.get("sourceName") or "sin nombre")
    tipo = (tipos or {}).get(nombre, "")
    visible = _visible(elemento)
    if rect is None or not lienzo_ancho or not lienzo_alto:
        posicion, tamano = "posición desconocida", ""
    elif rect[2] * rect[3] / (lienzo_ancho * lienzo_alto) * 100 >= _UMBRAL_TODO:
        posicion, tamano = "ocupa toda la imagen", ""
    else:
        posicion = _texto_anclaje(rect, lienzo_ancho, lienzo_alto) or "en una posición libre"
        tamano = f"{int(round(rect[2]))} por {int(round(rect[3]))} píxeles"
    if not visible:
        estado = "oculta en OBS"
    else:
        tapa, porcentaje = _quien_mas_tapa(rect, delanteros) if rect is not None else (None, 0.0)
        if tapa is not None and porcentaje >= _UMBRAL_TAPA_ENTERA:
            estado = (f"visible en OBS, pero no aparece en la imagen: "
                      f"la tapa entera {tapa}")
        elif tapa is not None and porcentaje >= _UMBRAL_AVISO:
            estado = (f"se ve en parte: {tapa} tapa el "
                      f"{int(round(porcentaje))} por ciento")
        else:
            estado = "se ve"
    if rect is not None and lienzo_ancho and lienzo_alto:
        fuera = obs_disposicion.fuera_del_lienzo(rect, lienzo_ancho, lienzo_alto)
        if fuera >= _UMBRAL_AVISO:
            estado += f" y un {int(round(fuera))} por ciento queda fuera de la imagen"
    partes = [f"{numero}: {nombre}"]
    if tipo:
        partes.append(str(tipo))
    partes += [posicion]
    if tamano:
        partes.append(tamano)
    partes.append(estado)
    return ", ".join(partes) + "."


def describir_escena(escena, elementos, lienzo_ancho, lienzo_alto, tipos) -> str:
    """Frase con la escena al aire y una oración por fuente.

    Las fuentes salen de adelante hacia atrás (sceneItemIndex más alto
    primero). Cada oración trae nombre, tipo, posición, tamaño y estado,
    una por línea para que NVDA la recorra por partes.
    """
    ordenados = sorted(elementos or (),
                       key=lambda elemento: elemento.get("sceneItemIndex", 0),
                       reverse=True)
    if not ordenados:
        return f"Escena al aire: {escena}. No tiene fuentes."
    palabra = "1 fuente" if len(ordenados) == 1 else f"{len(ordenados)} fuentes"
    lineas = [f"Escena al aire: {escena}. {palabra}, de adelante hacia atrás."]
    rects = [_rectangulo_de(elemento) for elemento in ordenados]
    for numero, (elemento, rect) in enumerate(zip(ordenados, rects), 1):
        delanteros = [(str(otro.get("sourceName") or "sin nombre"), otro_rect)
                      for otro, otro_rect in zip(ordenados[:numero - 1], rects[:numero - 1])
                      if _visible(otro) and otro_rect is not None]
        lineas.append(_frase_fuente(numero, elemento, rect, delanteros,
                                    lienzo_ancho, lienzo_alto, tipos))
    return "\n".join(lineas)
