"""Revisión de OBS antes de transmitir, en frases para leer en voz alta.

Recibe un cliente con `pedir(tipo, datos=None, parada=None)` como
`obs_destinos` y no crea conexiones. Nadie lo llama todavía: lo usará la
ventana Transmisión.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

from ytchat.core.idioma import N_, _
from ytchat.obs.obs_png import imagen_vacia_png
from ytchat.obs import obs_grabacion


# Tipo legible por inputKind. Lo que no está acá se muestra tal cual.
_TIPOS = {
    "window_capture": N_("captura de ventana"),
    "game_capture": N_("captura de juego"),
    "monitor_capture": N_("captura de pantalla"),
    "dshow_input": N_("cámara"),
    "browser_source": N_("navegador"),
    "image_source": N_("imagen"),
    "ffmpeg_source": N_("vídeo"),
    "text_gdiplus_v3": N_("texto"),
    "text_gdiplus": N_("texto"),
}

_TIPO_ESCENA = N_("escena")

_MICROFONO = "wasapi_input_capture"
_ESCRITORIO = "wasapi_output_capture"


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
    avisos: tuple = ()


def _datos(cliente, tipo, datos=None, parada=None):
    respuesta = cliente.pedir(tipo, datos, parada=parada)
    return respuesta.get("responseData", {}) or {}


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
        return _("vertical")
    if ancho > alto:
        return _("horizontal")
    return _("cuadrado")


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
            return _("panel de chat de la app")
        return ""
    return ""


def _fuentes_obs(cliente, elementos, por_nombre, escenas, parada) -> list:
    fuentes = []
    for elemento in elementos:
        nombre = elemento.get("sourceName", "") or ""
        visible = bool(elemento.get("sceneItemEnabled", True))
        clase = por_nombre.get(nombre, {}).get("inputKind", "") or ""
        if nombre in escenas:
            tipo = _(_TIPO_ESCENA)
        elif clase:
            tipo = _(_TIPOS[clase]) if clase in _TIPOS else clase
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
        problemas.append(_("OBS está en el perfil {perfil}, no en {destino}. Pulsa "
                           "Preparar destino.").format(perfil=perfil, destino=destino))
    for entrada in audio:
        if not entrada.escritorio and entrada.silenciada:
            problemas.append(_("El micrófono {nombre} está silenciado.").format(
                nombre=entrada.nombre))
    for entrada in audio:
        if entrada.escritorio and entrada.silenciada:
            problemas.append(_("El audio del escritorio {nombre} está silenciado.").format(
                nombre=entrada.nombre))
    if not any(fuente.visible for fuente in fuentes):
        problemas.append(_("La escena no tiene ninguna fuente visible. "
                           "Para agregar una: Transmisión, sección Escena, elegir la ventana "
                           "en Ventana que se captura y pulsar Usar esa ventana."))
    if imagen is True:
        problemas.append(_("La imagen está vacía: la escena se ve en negro. "
                           "Revisar que la ventana capturada esté abierta y no minimizada."))
    return problemas


def revisar(cliente, destino, parada=None, grabar=False) -> Revision:
    """Lee OBS y devuelve qué hay al aire y qué impide transmitir."""
    (perfil, coleccion, lienzo, escena, elementos, entradas, por_nombre,
     escenas) = _base_obs(cliente, destino, parada)
    fuentes = _fuentes_obs(cliente, elementos, por_nombre, escenas, parada)
    audio = _audio_obs(cliente, entradas, parada)
    imagen = _leer_imagen_vacia(cliente, escena, parada)
    problemas = _problemas_revision(perfil, destino, audio, fuentes, imagen)
    avisos = ()
    if grabar and obs_grabacion.codificador_propio_en_obs(
            cliente, parada) is True:
        avisos = (_(obs_grabacion.AVISO_CODIFICADOR),)
    return Revision(destino, perfil, coleccion, lienzo.get("baseWidth"),
                    lienzo.get("baseHeight"), escena, tuple(fuentes),
                    tuple(audio), imagen, tuple(problemas), tuple(avisos))


def frase_revision(revision) -> str:
    """Resume la revisión en frases para leer antes de confirmar."""
    partes = [_("Destino {destino}.").format(destino=revision.destino)]
    if isinstance(revision.ancho, int) and isinstance(revision.alto, int):
        partes.append(_("Perfil {perfil}, formato {formato} {ancho} por {alto}.").format(
            perfil=revision.perfil, formato=_formato(revision.ancho, revision.alto),
            ancho=revision.ancho, alto=revision.alto))
    else:
        partes.append(_("Perfil {perfil}.").format(perfil=revision.perfil))
    partes.append(_("Escena al aire: {escena}.").format(escena=revision.escena))
    visibles = [fuente for fuente in revision.fuentes if fuente.visible]
    if visibles:
        nombres = [(f"{fuente.tipo} {fuente.detalle or fuente.nombre}".strip()
                     or fuente.nombre) for fuente in visibles]
        partes.append(_("Fuentes: {fuentes}.").format(fuentes=", ".join(nombres)))
    else:
        partes.append(_("Sin fuentes visibles."))
    for entrada in revision.audio:
        estado = _("silenciado") if entrada.silenciada else _("con sonido")
        if not entrada.escritorio:
            partes.append(_("Micrófono {nombre} {estado}.").format(
                nombre=entrada.nombre, estado=estado))
        elif entrada.nombre == "Audio del escritorio":
            partes.append(_("Audio del escritorio {estado}.").format(estado=estado))
        else:
            partes.append(_("Audio del escritorio {nombre} {estado}.").format(
                nombre=entrada.nombre, estado=estado))
    if revision.problemas:
        partes.append(_("Atención: {problemas}").format(problemas=" ".join(revision.problemas)))
    if revision.avisos:
        partes.append(" ".join(revision.avisos))
    return " ".join(partes)
