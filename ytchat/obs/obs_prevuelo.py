"""Revisión de OBS antes de transmitir, en frases para leer en voz alta.

Recibe un cliente con `pedir(tipo, datos=None, parada=None)` como
`obs_destinos` y no crea conexiones. Nadie lo llama todavía: lo usará la
ventana Transmisión.
"""

from __future__ import annotations

import base64
import struct
import zlib
from dataclasses import dataclass


# Tipo legible por inputKind. Lo que no está acá se muestra tal cual.
_TIPOS = {
    "window_capture": "captura de ventana",
    "game_capture": "captura de juego",
    "monitor_capture": "captura de pantalla",
    "dshow_input": "cámara",
    "browser_source": "navegador",
    "image_source": "imagen",
    "ffmpeg_source": "vídeo",
    "text_gdiplus_v3": "texto",
    "text_gdiplus": "texto",
}

_MICROFONO = "wasapi_input_capture"
_ESCRITORIO = "wasapi_output_capture"

# Un píxel con algún canal por encima de esto ya es imagen, no negro.
_UMBRAL_NEGRO = 16


@dataclass(frozen=True, slots=True)
class Fuente:
    nombre: str
    tipo: str
    detalle: str
    visible: bool


@dataclass(frozen=True, slots=True)
class EntradaAudio:
    """Una entrada de audio global con su estado de silencio.

    El indicador `escritorio` distingue el audio del escritorio
    (`wasapi_output_capture`) del micrófono (`wasapi_input_capture`): la
    frase de revisión los nombra distinto y por eso necesita el dato.
    """

    nombre: str
    silenciada: bool
    escritorio: bool = False


@dataclass(frozen=True, slots=True)
class Revision:
    destino: str
    perfil: str
    coleccion: str
    ancho: int | None
    alto: int | None
    escena: str
    fuentes: tuple
    audio: tuple
    imagen_vacia: bool | None
    problemas: tuple


def _datos(cliente, tipo, datos=None, parada=None):
    respuesta = cliente.pedir(tipo, datos, parada=parada)
    return respuesta.get("responseData", {}) or {}


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


def _detalle_ventana(ajustes) -> str:
    ventana = str((ajustes or {}).get("window", "") or "")
    partes = ventana.split(":")
    titulo = partes[0].strip() if partes else ""
    if titulo:
        return titulo
    return partes[-1].strip() if partes else ""


def _leer_imagen_vacia(cliente, escena, parada) -> bool | None:
    try:
        datos = _datos(cliente, "GetSourceScreenshot",
                       {"sourceName": escena, "imageFormat": "png",
                        "imageWidth": 64}, parada)
    except Exception:
        return None
    texto = str(datos.get("imageData", "") or "")
    if "," in texto:
        texto = texto.split(",", 1)[1]
    try:
        return imagen_vacia_png(base64.b64decode(texto))
    except Exception:
        return None


def _formato(ancho, alto) -> str:
    if alto > ancho:
        return "vertical"
    if ancho > alto:
        return "horizontal"
    return "cuadrado"


def _base_obs(cliente, destino, parada):
    """Lo fijo de OBS: perfil, colección, lienzo, escena, elementos,
    entradas y escenas conocidas."""
    perfil = _datos(cliente, "GetProfileList", parada=parada).get(
        "currentProfileName", "") or ""
    coleccion = _datos(cliente, "GetSceneCollectionList",
                       parada=parada).get("currentSceneCollectionName", "") or ""
    lienzo = _datos(cliente, "GetVideoSettings", parada=parada)
    escena = _datos(cliente, "GetCurrentProgramScene",
                    parada=parada).get("currentProgramSceneName", "") or ""
    elementos = _datos(cliente, "GetSceneItemList", {"sceneName": escena},
                       parada).get("sceneItems", ()) or ()
    entradas = _datos(cliente, "GetInputList", parada=parada).get("inputs", ()) or ()
    por_nombre = {entrada.get("inputName", ""): entrada for entrada in entradas
                  if entrada.get("inputName", "")}
    try:
        escenas = {escena_dato.get("sceneName", "")
                   for escena_dato in _datos(cliente, "GetSceneList",
                                            parada=parada).get("scenes", ()) or ()}
    except Exception:
        escenas = set()
    return perfil, coleccion, lienzo, escena, elementos, entradas, por_nombre, escenas


def _detalle_fuente(cliente, nombre, clase, parada) -> str:
    if clase in ("window_capture", "game_capture"):
        try:
            ajustes = _datos(cliente, "GetInputSettings",
                             {"inputName": nombre}, parada).get(
                "inputSettings", {}) or {}
        except Exception:
            ajustes = {}
        return _detalle_ventana(ajustes)
    if clase == "browser_source":
        try:
            ajustes = _datos(cliente, "GetInputSettings",
                             {"inputName": nombre}, parada).get(
                "inputSettings", {}) or {}
        except Exception:
            ajustes = {}
        url = str(ajustes.get("url", "") or "").strip()
        if url.endswith("/chat"):
            return "panel de chat de la app"
        return ""
    return ""


def _fuentes_obs(cliente, elementos, por_nombre, escenas, parada) -> list:
    fuentes = []
    for elemento in elementos:
        nombre = elemento.get("sourceName", "") or ""
        visible = bool(elemento.get("sceneItemEnabled", True))
        clase = por_nombre.get(nombre, {}).get("inputKind", "") or ""
        if nombre in escenas:
            tipo = "escena"
        elif clase:
            tipo = _TIPOS.get(clase, clase)
        else:
            tipo = ""
        fuentes.append(Fuente(nombre, tipo,
                              _detalle_fuente(cliente, nombre, clase, parada)
                              if clase in ("window_capture", "game_capture",
                                           "browser_source") else "",
                              visible))
    return fuentes


def _audio_obs(cliente, entradas, parada) -> list:
    audio = []
    for entrada in entradas:
        clase = entrada.get("inputKind", "")
        nombre = entrada.get("inputName", "")
        if clase not in (_MICROFONO, _ESCRITORIO) or not nombre:
            continue
        try:
            silenciada = bool(_datos(cliente, "GetInputMute",
                                     {"inputName": nombre}, parada).get(
                "inputMuted", False))
        except Exception:
            continue
        audio.append(EntradaAudio(nombre, silenciada,
                                  clase == _ESCRITORIO))
    # Micrófonos primero para un orden estable venga como venga de OBS.
    audio.sort(key=lambda entrada: entrada.escritorio)
    return audio


def _problemas_revision(perfil, destino, audio, fuentes, imagen) -> list:
    problemas = []
    if perfil != destino:
        problemas.append(f"OBS está en el perfil {perfil}, no en {destino}. "
                         "Pulsa Preparar destino.")
    for entrada in audio:
        if not entrada.escritorio and entrada.silenciada:
            problemas.append(f"El micrófono {entrada.nombre} está silenciado.")
    for entrada in audio:
        if entrada.escritorio and entrada.silenciada:
            problemas.append(f"El audio del escritorio {entrada.nombre} "
                             "está silenciado.")
    if not any(fuente.visible for fuente in fuentes):
        problemas.append("La escena no tiene ninguna fuente visible. "
                         "Para agregar una: Transmisión, sección Escena, "
                         "elegir la ventana en Ventana que se captura y "
                         "pulsar Usar esa ventana.")
    if imagen is True:
        problemas.append("La imagen está vacía: la escena se ve en negro. "
                         "Revisar que la ventana capturada esté abierta y "
                         "no minimizada.")
    return problemas


def revisar(cliente, destino, parada=None) -> Revision:
    """Lee OBS y devuelve qué hay al aire y qué impide transmitir."""
    (perfil, coleccion, lienzo, escena, elementos, entradas, por_nombre,
     escenas) = _base_obs(cliente, destino, parada)
    fuentes = _fuentes_obs(cliente, elementos, por_nombre, escenas, parada)
    audio = _audio_obs(cliente, entradas, parada)
    imagen = _leer_imagen_vacia(cliente, escena, parada)
    problemas = _problemas_revision(perfil, destino, audio, fuentes, imagen)
    return Revision(destino, perfil, coleccion, lienzo.get("baseWidth"),
                    lienzo.get("baseHeight"), escena, tuple(fuentes),
                    tuple(audio), imagen, tuple(problemas))


def frase_revision(revision) -> str:
    """Resume la revisión en frases para leer antes de confirmar."""
    texto = f"Destino {revision.destino}. "
    if isinstance(revision.ancho, int) and isinstance(revision.alto, int):
        texto += (f"Perfil {revision.perfil}, formato "
                  f"{_formato(revision.ancho, revision.alto)} "
                  f"{revision.ancho} por {revision.alto}. ")
    else:
        texto += f"Perfil {revision.perfil}. "
    texto += f"Escena al aire: {revision.escena}. "
    visibles = [fuente for fuente in revision.fuentes if fuente.visible]
    if visibles:
        nombres = []
        for fuente in visibles:
            etiqueta = f"{fuente.tipo} {fuente.detalle or fuente.nombre}".strip()
            nombres.append(etiqueta if etiqueta else fuente.nombre)
        texto += "Fuentes: " + ", ".join(nombres) + ". "
    else:
        texto += "Sin fuentes visibles. "
    for entrada in revision.audio:
        estado = "silenciado" if entrada.silenciada else "con sonido"
        if not entrada.escritorio:
            texto += f"Micrófono {entrada.nombre} {estado}. "
        elif entrada.nombre == "Audio del escritorio":
            texto += f"Audio del escritorio {estado}. "
        else:
            texto += f"Audio del escritorio {entrada.nombre} {estado}. "
    texto = texto.strip()
    if revision.problemas:
        texto += " Atención: " + " ".join(revision.problemas)
    return texto
