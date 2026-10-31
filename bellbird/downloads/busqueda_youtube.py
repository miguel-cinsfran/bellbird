"""Motor de búsqueda de YouTube con yt-dlp, sin interfaz.

Razón: buscar en YouTube con yt-dlp y entregar los resultados. Lo usa la
pestaña de búsqueda y tiene pruebas puras.
"""

from __future__ import annotations

import base64
import json
import subprocess
import time
from dataclasses import dataclass
from urllib.parse import quote, quote_plus

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.downloads import ytdlp_bin
from bellbird.downloads.motivo_error import motivo_de_error

logger = diagnostico.obtener_logger(__name__)

CANTIDADES = (10, 20, 30, 50)
CANTIDAD_DEFECTO = 20


def clasificar_entrada(texto: str) -> tuple[str, str]:
    """Distingue vacío, enlace o búsqueda, sin usar la red."""
    s = (texto or "").strip() if isinstance(texto, str) else ""
    if not s:
        return ("vacio", "")
    if any(letra.isspace() for letra in s):
        return ("busqueda", s)
    bajo = s.lower()
    if bajo.startswith(("http://", "https://")):
        return ("enlace", s)
    if bajo.startswith("www."):
        return ("enlace", "https://" + s)
    if "/" in s:
        cabeza = s.split("/", 1)[0]
        partes = cabeza.split(".")
        if "." in cabeza and all(partes):
            if not cabeza.startswith(".") and not cabeza.endswith("."):
                return ("enlace", "https://" + s)
    return ("busqueda", s)


@dataclass(frozen=True)
class Filtros:
    """Filtros de la búsqueda, con los valores que acepta YouTube."""

    tipo: str = "videos"
    duracion: str = ""
    fecha: str = ""
    orden: str = "relevancia"


_FECHA_A_NUM = {"hoy": 2, "semana": 3, "mes": 4, "anio": 5}
_TIPO_A_NUM = {"videos": 1, "canales": 2, "listas": 3}
_DURACION_A_NUM = {"corta": 1, "larga": 2, "media": 3}


def codigo_sp(filtros: Filtros) -> str:
    """El parámetro sp de la búsqueda, en base64.

    Orden de campo: fecha (08), tipo (10), duración (18) y directo (40).
    Listas y canales llevan solo su tipo. Directo no lleva tipo.
    """
    interior = bytearray()
    if filtros.tipo in ("listas", "canales"):
        interior += bytes([0x10, _TIPO_A_NUM[filtros.tipo]])
    elif filtros.tipo == "directo":
        if filtros.fecha in _FECHA_A_NUM:
            interior += bytes([0x08, _FECHA_A_NUM[filtros.fecha]])
        if filtros.duracion in _DURACION_A_NUM:
            interior += bytes([0x18, _DURACION_A_NUM[filtros.duracion]])
        interior += bytes([0x40, 0x01])
    else:
        if filtros.fecha in _FECHA_A_NUM:
            interior += bytes([0x08, _FECHA_A_NUM[filtros.fecha]])
        interior += bytes([0x10, _TIPO_A_NUM["videos"]])
        if filtros.duracion in _DURACION_A_NUM:
            interior += bytes([0x18, _DURACION_A_NUM[filtros.duracion]])
    externo = bytes([0x12, len(interior)]) + bytes(interior)
    return base64.b64encode(externo).decode("ascii")


def url_busqueda(texto: str, filtros: Filtros) -> str:
    """La URL de resultados de YouTube para ese texto y esos filtros."""
    return (
        "https://www.youtube.com/results?search_query="
        + quote_plus(texto)
        + "&sp="
        + quote(codigo_sp(filtros))
    )


@dataclass
class Resultado:
    """Un resultado de la búsqueda, listo para mostrar."""

    id: str
    url: str
    titulo: str
    canal: str
    duracion: int | None
    vistas: int | None
    marca_tiempo: int | None
    descripcion: str
    tipo: str
    en_directo: bool
    programado: bool


def _tipo_de_entrada(entrada: dict, url: str) -> str:
    bajo = url.lower()
    if "/playlist" in bajo or "list=" in bajo:
        return "lista"
    if ("/channel/" in bajo or "/@" in bajo or "/c/" in bajo
            or "/user/" in bajo):
        return "canal"
    if (entrada.get("ie_key") or "") == "YoutubeTab":
        return "canal"
    return "video"


def _entero_o_nada(valor) -> int | None:
    return valor if isinstance(valor, int) else None


def interpretar(texto_json: str) -> list[Resultado]:
    """Los resultados del JSON de yt-dlp. Un JSON inválido da lista vacía."""
    try:
        datos = json.loads(texto_json)
    except (TypeError, ValueError):
        return []
    if isinstance(datos, dict):
        entradas = datos.get("entries")
        if entradas is None:
            if datos.get("url") and datos.get("title"):
                entradas = [datos]
            else:
                return []
    elif isinstance(datos, list):
        entradas = datos
    else:
        return []
    resultados = []
    for entrada in entradas or []:
        if not isinstance(entrada, dict):
            continue
        url = entrada.get("url") or ""
        titulo = entrada.get("title") or ""
        if not url or not titulo:
            continue
        directo = entrada.get("live_status") or ""
        descripcion = entrada.get("description") or ""
        resultados.append(Resultado(
            id=str(entrada.get("id") or ""),
            url=str(url),
            titulo=str(titulo),
            canal=str(entrada.get("channel") or entrada.get("uploader") or ""),
            duracion=_entero_o_nada(entrada.get("duration")),
            vistas=_entero_o_nada(entrada.get("view_count")),
            marca_tiempo=_entero_o_nada(entrada.get("timestamp")),
            descripcion=descripcion if isinstance(descripcion, str) else "",
            tipo=_tipo_de_entrada(entrada, str(url)),
            en_directo=directo == "is_live",
            programado=directo == "is_upcoming",
        ))
    return resultados


_VENTANA_DIAS = {"hoy": 1, "semana": 7, "mes": 31, "anio": 366}


def refiltrar(resultados: list[Resultado], filtros: Filtros,
              ahora: float) -> list:
    """Saca lo que cae fuera de la ventana de fecha, conserva sin fecha."""
    ventana = _VENTANA_DIAS.get(filtros.fecha)
    if ventana is None:
        return list(resultados)
    tope = ventana * 86400
    salida = []
    for item in resultados:
        if item.marca_tiempo is None:
            salida.append(item)
            continue
        try:
            diferencia = float(ahora) - float(item.marca_tiempo)
        except (TypeError, ValueError):
            salida.append(item)
            continue
        if diferencia <= tope:
            salida.append(item)
    return salida


def ordenar(resultados: list[Resultado], orden: str) -> list:
    """Ordena de mayor a menor, estable, con lo sin dato al final."""
    if orden == "fecha":
        return sorted(
            resultados,
            key=lambda r: (r.marca_tiempo is None, -(r.marca_tiempo or 0)))
    if orden == "vistas":
        return sorted(
            resultados,
            key=lambda r: (r.vistas is None, -(r.vistas or 0)))
    if orden == "duracion":
        return sorted(
            resultados,
            key=lambda r: (r.duracion is None, -(r.duracion or 0)))
    return list(resultados)


@dataclass
class RespuestaBusqueda:
    """Lo que devuelve buscar: resultados, error y si hay más."""

    resultados: list
    error: str
    hay_mas: bool
    titulo: str = ""
    total: int = 0


def _motivo_en_stderr(salida_error: str) -> str | None:
    motivo = None
    for linea in (salida_error or "").splitlines():
        hallado = motivo_de_error(linea)
        if hallado:
            motivo = hallado
    return motivo


def _correr(argumentos):
    """El proceso terminado de yt-dlp, o None si no se pudo ejecutar."""
    try:
        return subprocess.run(
            argumentos, capture_output=True, text=True, encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=60, check=False)
    except Exception as error:
        logger.debug("yt-dlp: %s", error)
        return None


def buscar(texto: str, filtros: Filtros, inicio: int,
           cantidad: int) -> RespuestaBusqueda:
    """Busca en YouTube con yt-dlp. No lanza nunca."""
    ruta = ytdlp_bin.ruta_ytdlp()
    if ruta is None:
        return RespuestaBusqueda([], _("yt-dlp no está instalado"), False)
    url = url_busqueda(texto, filtros)
    terminado = _correr([
        ruta, *ytdlp_bin.argumentos_comunes(), "-J", "--flat-playlist",
        "--no-warnings", "--encoding", "utf-8", "--socket-timeout", "20",
        "--extractor-args", "youtubetab:approximate_date",
        "--playlist-start", str(inicio),
        "--playlist-end", str(inicio + cantidad - 1), url,
    ])
    if terminado is None or terminado.returncode != 0:
        motivo = _motivo_en_stderr(getattr(terminado, "stderr", "") or "")
        if motivo:
            return RespuestaBusqueda([], motivo, False)
        logger.debug("buscar: %s", getattr(terminado, "returncode", "sin proceso"))
        return RespuestaBusqueda(
            [], _("No se pudo completar la búsqueda. Comprueba la conexión e "
                 "inténtalo de nuevo."), False)
    brutos = interpretar(getattr(terminado, "stdout", ""))
    hay_mas = len(brutos) >= cantidad
    return RespuestaBusqueda(refiltrar(brutos, filtros, time.time()), "", hay_mas)


def es_enlace_de_lista(url) -> bool:
    """Si el enlace es una lista: YouTube con /playlist o conjuntos de SoundCloud."""
    bajo = url.casefold() if isinstance(url, str) else ""
    if "/sets/" in bajo:
        return "soundcloud" in bajo
    if "youtube" in bajo or "youtu.be" in bajo:
        return "/playlist" in bajo and "watch" not in bajo
    return False


def contenido(url, inicio, cantidad) -> RespuestaBusqueda:
    """El contenido de una lista o un canal, por tandas. Solo trae vídeos."""
    ruta = ytdlp_bin.ruta_ytdlp()
    if ruta is None:
        return RespuestaBusqueda([], _("yt-dlp no está instalado"), False, "", 0)
    bajo = url.casefold() if isinstance(url, str) else ""
    marcas = ("/channel/", "/@", "/c/", "/user/")
    intentos = [url + "/videos", url] if any(m in bajo for m in marcas) else [url]
    ultima = RespuestaBusqueda(
        [], _("No se pudo leer el contenido. Comprueba la conexión e "
              "inténtalo de nuevo."), False, "", 0)
    for intento in intentos:
        terminado = _correr([
            ruta, *ytdlp_bin.argumentos_comunes(), "-J", "--flat-playlist",
            "--no-warnings", "--socket-timeout", "20",
            "--playlist-start", str(inicio),
            "--playlist-end", str(inicio + cantidad - 1), intento,
        ])
        if terminado is None or terminado.returncode != 0:
            motivo = _motivo_en_stderr(getattr(terminado, "stderr", "") or "")
            if motivo:
                ultima = RespuestaBusqueda([], motivo, False, "", 0)
            continue
        try:
            datos = json.loads(getattr(terminado, "stdout", ""))
            if not isinstance(datos, dict):
                continue
        except (TypeError, ValueError):
            continue
        videos = [r for r in interpretar(getattr(terminado, "stdout", ""))
                  if r.tipo == "video"]
        total = datos.get("playlist_count") or 0
        return RespuestaBusqueda(
            videos, "", len(datos.get("entries") or []) >= cantidad,
            str(datos.get("title") or ""), total if isinstance(total, int) else 0)
    return ultima
