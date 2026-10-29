"""Actualiza el ejecutable independiente de yt-dlp."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import NamedTuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bellbird.core import paths
from bellbird.core.idioma import _
from bellbird.downloads import ytdlp_bin


URL_API_RELEASES = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
NOMBRE_BINARIO = paths.NOMBRE_YTDLP
NOMBRE_FIRMAS = "SHA2-256SUMS"


def _user_agent():
    # Import local por el ciclo diagnostico, ytdlp_bin, config.
    from bellbird.core import config
    return f"Bellbird/{config.APP_VERSION}"


class ResultadoDescarga(NamedTuple):
    """Resultado que se puede mostrar sin propagar errores de red."""

    correcta: bool
    motivo: str


def resultado_actualizacion_es_fallo(estado: str) -> bool:
    """Indica si el resultado de actualizar yt-dlp es un fallo."""
    return estado not in ("ya_al_dia", "actualizado")


def mensaje_de_actualizacion(estado, version_actual="", version_nueva="",
                             motivo="") -> str:
    """Elige el anuncio breve para cada resultado de la actualización."""
    if estado == "ya_al_dia":
        # Traductores: {version} es la versión instalada o la nueva de yt-dlp.
        return _("Ya tienes yt-dlp al día, versión {version}.").format(version=version_actual or version_nueva)
    if estado == "actualizado":
        # Traductores: {version} es la versión nueva de yt-dlp.
        return _("yt-dlp se actualizó a la versión {version}.").format(version=version_nueva or version_actual)
    if estado == "sin_conexion":
        return _("No se pudo comprobar la última versión de yt-dlp. Revisa la conexión a internet.")
    if estado == "firma_incorrecta":
        return _("La descarga de yt-dlp no pasó una comprobación de seguridad. No se instaló nada.")
    if estado == "cancelado":
        return _("Se canceló la descarga de yt-dlp.")
    if motivo:
        return _("No se pudo actualizar yt-dlp: {motivo}.").format(motivo=motivo)
    return _("No se pudo actualizar yt-dlp.")


def ultima_version_ytdlp() -> tuple[str, str, str] | None:
    """Devuelve versión, descarga del ejecutable y descarga de sus firmas."""
    try:
        solicitud = Request(URL_API_RELEASES, headers={"User-Agent": _user_agent()})
        with urlopen(solicitud, timeout=ytdlp_bin.TIEMPO_ESPERA) as respuesta:
            datos = json.load(respuesta)
        activos = {activo["name"]: activo for activo in datos["assets"]}
        ejecutable = activos[NOMBRE_BINARIO]["browser_download_url"]
        firmas = activos[NOMBRE_FIRMAS]["browser_download_url"]
        return datos["tag_name"], ejecutable, firmas
    except (HTTPError, URLError, OSError, KeyError, TypeError, ValueError,
            json.JSONDecodeError):
        return None


def firma_sha256(texto: str, nombre: str) -> str:
    """Extrae la firma de un archivo SHA2-256SUMS para un nombre concreto."""
    nombre = str(nombre).strip()
    for linea in texto.splitlines():
        partes = linea.strip().split(None, 1)
        if len(partes) != 2:
            continue
        firma, archivo = partes
        if archivo.lstrip("*").strip() == nombre:
            return firma.lower()
    return ""


class _DescargaCancelada(Exception):
    pass


def porcentaje_descarga(descargado: int, total: int | None) -> int | None:
    """Calcula un porcentaje entero o None si no hay total conocido."""
    if total is None or total <= 0:
        return None
    return min(100, max(0, int(descargado * 100 / total)))


def debe_actualizar_texto_progreso(anterior: int | None, actual: int | None) -> bool:
    """Indica si el texto debe cambiar al avanzar otra decena."""
    if actual is None:
        return False
    return anterior is None or actual >= anterior + 10 or actual == 100


def _descargar_archivo(url: str, destino: Path, aviso=None, cancelar=None) -> None:
    solicitud = Request(url, headers={"User-Agent": _user_agent()})
    with urlopen(solicitud, timeout=ytdlp_bin.TIEMPO_ESPERA) as respuesta:
        total = None
        try:
            total = int(respuesta.headers.get("Content-Length"))
        except (AttributeError, TypeError, ValueError):
            pass
        descargado = 0
        with destino.open("wb") as archivo:
            while True:
                if cancelar is not None and cancelar():
                    raise _DescargaCancelada
                bloque = respuesta.read(1024 * 1024)
                if not bloque:
                    break
                archivo.write(bloque)
                descargado += len(bloque)
                if aviso is not None:
                    aviso(porcentaje_descarga(descargado, total), descargado, total)


def descargar_ytdlp(url: str, firma: str, destino: str | os.PathLike,
                    aviso_progreso=None, cancelar=None) -> ResultadoDescarga:
    """Descarga, verifica y reemplaza un ejecutable sin ejecutar el temporal."""
    if not url.lower().startswith("https://"):
        return ResultadoDescarga(False, "la descarga exige un enlace https")
    destino = Path(destino)
    temporal = None
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
                prefix=".yt-dlp-", suffix=".tmp", dir=destino.parent,
                delete=False) as archivo:
            temporal = Path(archivo.name)
        if aviso_progreso is None and cancelar is None:
            _descargar_archivo(url, temporal)
        else:
            _descargar_archivo(url, temporal, aviso_progreso, cancelar)
        resumen = hashlib.sha256()
        with temporal.open("rb") as archivo:
            for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
                resumen.update(bloque)
        if resumen.hexdigest().lower() != firma.strip().lower():
            return ResultadoDescarga(False, "la firma SHA-256 no coincide")
        os.replace(temporal, destino)
        temporal = None
        return ResultadoDescarga(True, "yt-dlp actualizado")
    except _DescargaCancelada:
        return ResultadoDescarga(False, "descarga cancelada")
    except (OSError, HTTPError, URLError, ValueError) as error:
        return ResultadoDescarga(False, f"no se pudo descargar yt-dlp: {error}")
    finally:
        if temporal is not None:
            try:
                temporal.unlink()
            except OSError:
                pass


def asegurar_ytdlp(destino: str | os.PathLike | None = None) -> ResultadoDescarga:
    """Asegura una copia local y no descarga si ya existe un binario."""
    if destino is None:
        destino = ytdlp_bin._ruta_actualizada()
    destino = Path(destino)
    if ytdlp_bin.ruta_ytdlp() is not None:
        return ResultadoDescarga(True, "yt-dlp ya está disponible")
    ultima = ultima_version_ytdlp()
    if ultima is None:
        return ResultadoDescarga(False, "no se pudo consultar la última versión")
    _sin_uso, url_ejecutable, url_firmas = ultima
    try:
        solicitud = Request(url_firmas, headers={"User-Agent": _user_agent()})
        with urlopen(solicitud, timeout=ytdlp_bin.TIEMPO_ESPERA) as respuesta:
            texto_firmas = respuesta.read().decode("utf-8")
    except (HTTPError, URLError, OSError, UnicodeError):
        return ResultadoDescarga(False, "no se pudieron descargar las firmas")
    firma = firma_sha256(texto_firmas, NOMBRE_BINARIO)
    if not firma:
        return ResultadoDescarga(False, "no se encontró la firma de yt-dlp.exe")
    return descargar_ytdlp(url_ejecutable, firma, destino)


def actualizar_ytdlp(avisar_antes_descarga=None, aviso_progreso=None,
                     cancelar=None) -> tuple[str, str, str]:
    """Compara con la última publicada y actualiza si hace falta.

    Devuelve (estado, versión instalada, versión nueva).
    """
    ruta = ytdlp_bin.ruta_ytdlp()
    version_instalada = ytdlp_bin.version_ytdlp(ruta) if ruta else ""
    ultima = ultima_version_ytdlp()
    if ultima is None:
        return "sin_conexion", version_instalada, ""

    version_nueva, url_ejecutable, url_firmas = ultima
    if ruta and version_instalada == version_nueva:
        return "ya_al_dia", version_instalada, version_nueva

    try:
        solicitud = Request(url_firmas, headers={"User-Agent": _user_agent()})
        with urlopen(solicitud, timeout=ytdlp_bin.TIEMPO_ESPERA) as respuesta:
            texto_firmas = respuesta.read().decode("utf-8")
    except (HTTPError, URLError, OSError, UnicodeError):
        return "sin_conexion", version_instalada, version_nueva

    firma = firma_sha256(texto_firmas, NOMBRE_BINARIO)
    if not firma:
        return "otro_fallo", version_instalada, version_nueva
    if avisar_antes_descarga is not None:
        avisar_antes_descarga(version_nueva)
    resultado = descargar_ytdlp(url_ejecutable, firma, ytdlp_bin._ruta_actualizada(),
                                aviso_progreso, cancelar)
    if resultado.correcta:
        return "actualizado", version_instalada, version_nueva
    if "firma" in resultado.motivo.lower():
        return "firma_incorrecta", version_instalada, version_nueva
    if "cancelada" in resultado.motivo.lower():
        return "cancelado", version_instalada, version_nueva
    return "otro_fallo", version_instalada, version_nueva
