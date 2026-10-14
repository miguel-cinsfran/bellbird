"""Motor del actualizador, sin interfaz.

Consulta la última versión publicada en GitHub, baja y verifica el
paquete, y deja archivos de estado para que el instalador y la app se
coordinen. La interfaz vive en el encargo siguiente y no está acá.

El estilo de red copia a `ytchat.downloads.ytdlp_bin`: urllib,
descarga por bloques con aviso de progreso y función de cancelación,
archivo temporal y `os.replace`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import NamedTuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ytchat.core import paths


URL_ULTIMA_VERSION = (
    "https://api.github.com/repos/miguel-cinsfran/bellbird/releases/latest"
)
USER_AGENT = "ytchat-tts/2.0"
TIEMPO_ESPERA = 30

logger = logging.getLogger(f"ytchat.{__name__}")


class PaqueteInvalido(Exception):
    """El paquete descargado no sirve para instalar."""


class PaqueteElegido(NamedTuple):
    """Lo que `elegir_paquete` saca de la respuesta JSON de la API."""

    version: str
    notas: str
    url_zip: str
    url_firma: str
    tamanio: int | None


class ResultadoDescarga(NamedTuple):
    """Resultado que se puede mostrar sin propagar errores de red."""

    correcta: bool
    motivo: str


# ── Versiones ─────────────────────────────────────────────────────────────

_VERSION_RE = re.compile(r"^v?(\d+(?:\.\d+)*)$")


def version_como_tupla(texto: str | None) -> tuple[int, ...] | None:
    """Convierte un texto de versión en tupla de enteros comparable.

    "v2.10.0", "2.10.0" y "2.10" dan tuplas; "2.10" equivale a "2.10.0".
    Un texto que no es versión devuelve None.
    """
    if not isinstance(texto, str):
        return None
    texto = texto.strip()
    if not _VERSION_RE.match(texto):
        return None
    partes = tuple(int(p) for p in texto.lstrip("v").split("."))
    while len(partes) < 3:
        partes = partes + (0,)
    return partes


def hay_version_nueva(actual: str | None, publicada: str | None) -> bool:
    """Verdadero solo si la publicada es estrictamente mayor. Nunca compara textos."""
    tupla_actual = version_como_tupla(actual)
    tupla_publicada = version_como_tupla(publicada)
    if tupla_actual is None or tupla_publicada is None:
        return False
    return tupla_publicada > tupla_actual


# ── Consulta ───────────────────────────────────────────────────────────────

def _es_https(url: object) -> bool:
    return isinstance(url, str) and url.lower().startswith("https://")


def elegir_paquete(release: dict | None) -> PaqueteElegido | None:
    """Saca versión, notas y URLs del paquete de la respuesta JSON de la API.

    Paquete compatible: un activo cuyo nombre termina en `.zip` y otro
    activo llamado exactamente igual más `.sha256`. Si hay varios zip
    con firma, None por ambiguo. No se depende de ningún nombre de
    archivo en particular. Las URL tienen que ser https.
    """
    if not isinstance(release, dict):
        return None
    activos = release.get("assets")
    if not isinstance(activos, list):
        return None
    nombres = {}
    for activo in activos:
        if not isinstance(activo, dict):
            continue
        nombre = activo.get("name")
        url = activo.get("browser_download_url")
        if isinstance(nombre, str) and isinstance(url, str):
            nombres[nombre] = url
    candidatos = [nombre for nombre in nombres
                  if nombre.lower().endswith(".zip")
                  and (nombre + ".sha256") in nombres]
    if len(candidatos) != 1:
        return None
    nombre_zip = candidatos[0]
    url_zip = nombres[nombre_zip]
    url_firma = nombres[nombre_zip + ".sha256"]
    if not _es_https(url_zip) or not _es_https(url_firma):
        return None
    version = release.get("tag_name", "")
    if not isinstance(version, str) or version_como_tupla(version) is None:
        return None
    notas = release.get("body") or ""
    if not isinstance(notas, str):
        notas = ""
    tamanio = None
    for activo in activos:
        if (isinstance(activo, dict)
                and activo.get("name") == nombre_zip
                and isinstance(activo.get("size"), int)):
            tamanio = activo.get("size")
    return PaqueteElegido(version=version, notas=notas, url_zip=url_zip,
                           url_firma=url_firma, tamanio=tamanio)


def consultar_ultima_version() -> PaqueteElegido | None:
    """Consulta la última release y devuelve lo de `elegir_paquete`.

    None ante cualquier error de red o de JSON.
    """
    try:
        solicitud = Request(URL_ULTIMA_VERSION,
                            headers={"User-Agent": USER_AGENT})
        with urlopen(solicitud, timeout=TIEMPO_ESPERA) as respuesta:
            datos = json.load(respuesta)
        return elegir_paquete(datos)
    except (HTTPError, URLError, OSError, TypeError, ValueError):
        return None


# ── Firma ──────────────────────────────────────────────────────────────────

_FIRMA_RE = re.compile(r"[0-9a-fA-F]{64}")


def leer_firma(texto: str | None) -> str:
    """Devuelve el primer bloque de 64 hex del archivo de firma, en minúsculas.

    Ignora el nombre de archivo que venga al lado, porque GitHub cambia
    los espacios de los nombres de los activos por puntos y el nombre
    escrito adentro deja de coincidir. Cadena vacía si no hay ninguno.
    """
    if not isinstance(texto, str):
        return ""
    encontrado = _FIRMA_RE.search(texto)
    return encontrado.group(0).lower() if encontrado else ""


# ── Descarga ───────────────────────────────────────────────────────────────

class _DescargaCancelada(Exception):
    pass


def _descargar_archivo(url: str, destino: Path, aviso=None, cancelar=None) -> None:
    solicitud = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(solicitud, timeout=TIEMPO_ESPERA) as respuesta:
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
                    if total:
                        aviso(min(100, max(0, int(descargado * 100 / total))))
                    else:
                        aviso(None)


def _descargar_texto(url: str) -> str:
    solicitud = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(solicitud, timeout=TIEMPO_ESPERA) as respuesta:
        return respuesta.read().decode("utf-8")


def descargar_paquete(url_zip: str, url_firma: str, destino: str | os.PathLike,
                       aviso_progreso=None, cancelar=None,
                       permitir_http: bool = False) -> ResultadoDescarga:
    """Baja la firma, baja el zip a un temporal, comprueba el SHA-256 y
    recién entonces hace `os.replace` al destino.

    Por defecto exige https en ambas URL; `permitir_http` existe solo
    para las pruebas contra un servidor local y nunca se usa en la app.
    El temporal no queda nunca en disco.
    """
    if not permitir_http and not (_es_https(url_zip) and _es_https(url_firma)):
        return ResultadoDescarga(False, "la descarga exige URL https")
    destino = Path(destino)
    temporal = None
    try:
        try:
            texto_firma = _descargar_texto(url_firma)
        except _DescargaCancelada:
            return ResultadoDescarga(False, "descarga cancelada")
        except (OSError, HTTPError, URLError, ValueError, UnicodeError) as error:
            return ResultadoDescarga(
                False, f"no se pudo descargar la firma: {error}")
        firma = leer_firma(texto_firma)
        if not firma:
            return ResultadoDescarga(False, "el paquete no trae firma")
        destino.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
                prefix=".paquete-", suffix=".tmp", dir=destino.parent,
                delete=False) as archivo:
            temporal = Path(archivo.name)
        _descargar_archivo(url_zip, temporal, aviso_progreso, cancelar)
        resumen = hashlib.sha256()
        with temporal.open("rb") as archivo:
            for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
                resumen.update(bloque)
        if resumen.hexdigest().lower() != firma:
            return ResultadoDescarga(False, "la firma SHA-256 no coincide")
        os.replace(temporal, destino)
        temporal = None
        return ResultadoDescarga(True, "paquete descargado")
    except _DescargaCancelada:
        return ResultadoDescarga(False, "descarga cancelada")
    except (OSError, HTTPError, URLError, ValueError) as error:
        return ResultadoDescarga(
            False, f"no se pudo descargar el paquete: {error}")
    finally:
        if temporal is not None:
            try:
                temporal.unlink()
            except OSError:
                pass


# ── Extracción y validación ────────────────────────────────────────────────

def extraer_paquete(zip: str | os.PathLike, destino: str | os.PathLike) -> Path:
    """Extrae con `zipfile` rechazando entradas que escapen de `destino`.

    Borra `destino` si existe. Devuelve la carpeta raíz del paquete: si
    el zip tiene una única carpeta de primer nivel, esa; si no, `destino`.
    """
    destino = Path(destino)
    if destino.exists():
        _borrar_arbol(destino)
    destino.mkdir(parents=True, exist_ok=True)
    base = destino.resolve()
    with zipfile.ZipFile(zip) as archivo:
        # Primera pasada: rechazar antes de escribir nada.
        for entrada in archivo.infolist():
            ruta = (destino / entrada.filename).resolve()
            if ruta != base and base not in ruta.parents:
                _borrar_arbol(destino)
                destino.mkdir(parents=True, exist_ok=True)
                raise PaqueteInvalido(
                    f"el paquete trae una ruta fuera de lugar: {entrada.filename}")
        for entrada in archivo.infolist():
            ruta = (destino / entrada.filename).resolve()
            if entrada.is_dir():
                ruta.mkdir(parents=True, exist_ok=True)
            else:
                ruta.parent.mkdir(parents=True, exist_ok=True)
                with archivo.open(entrada) as origen, ruta.open("wb") as salida:
                    shutil.copyfileobj(origen, salida)
    primeros = sorted(p for p in destino.iterdir())
    if len(primeros) == 1 and primeros[0].is_dir():
        return primeros[0]
    return destino


def _borrar_arbol(carpeta: Path) -> None:
    for hijo in sorted(carpeta.iterdir()):
        if hijo.is_dir() and not hijo.is_symlink():
            _borrar_arbol(hijo)
            hijo.rmdir()
        else:
            hijo.unlink()
    carpeta.rmdir()


def validar_paquete(carpeta: str | os.PathLike,
                    version_esperada: str) -> str:
    """Comprueba el manifiesto y el contenido mínimo del paquete.

    Devuelve el nombre del ejecutable o lanza `PaqueteInvalido` con un
    motivo en español para anunciar.
    """
    carpeta = Path(carpeta)
    manifiesto = carpeta / paths.NOMBRE_MANIFIESTO
    if not manifiesto.is_file():
        raise PaqueteInvalido("el paquete no trae manifiesto")
    try:
        datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PaqueteInvalido("el manifiesto del paquete no se entiende")
    if not isinstance(datos, dict):
        raise PaqueteInvalido("el manifiesto del paquete no se entiende")
    version = datos.get("version")
    if version_como_tupla(version) != version_como_tupla(version_esperada):
        raise PaqueteInvalido(
            "la versión del paquete no coincide con la publicada")
    ejecutable = datos.get("ejecutable")
    if (not isinstance(ejecutable, str) or not ejecutable.lower().endswith(".exe")
            or "/" in ejecutable or "\\" in ejecutable
            or ejecutable in (".", "..")):
        raise PaqueteInvalido("el ejecutable del paquete no es válido")
    if not (carpeta / ejecutable).is_file():
        raise PaqueteInvalido("el paquete no trae el ejecutable")
    for prohibido in ("data", "Descargas"):
        if (carpeta / prohibido).exists():
            raise PaqueteInvalido(
                f"el paquete trae {prohibido}, que es del usuario")
    return ejecutable


def carpeta_admite_escritura(carpeta: str | os.PathLike) -> bool:
    """Crea y borra un archivo de prueba. Falso si no puede."""
    try:
        testigo = Path(carpeta) / ".prueba-escritura"
        testigo.write_bytes(b"ok")
        testigo.unlink()
        return True
    except OSError:
        return False


# ── Estado ─────────────────────────────────────────────────────────────────

def confirmar_arranque(version_actual: str,
                       instalacion: str | os.PathLike | None = None) -> None:
    """Si hay `pendiente.json` hacia esta versión, escribe `arranque-ok`. Nunca lanza."""
    try:
        base = Path(instalacion) if instalacion is not None else paths.carpeta_instalacion()
        pendiente = paths.actualizacion_pendiente_en(base)
        if not pendiente.is_file():
            return
        datos = json.loads(pendiente.read_text(encoding="utf-8"))
        if isinstance(datos, dict) and datos.get("hacia") == version_actual:
            paths.arranque_confirmado_en(base).write_text("ok", encoding="utf-8")
    except (OSError, ValueError):
        pass


def tomar_resultado(instalacion: str | os.PathLike | None = None) -> dict | None:
    """Lee `resultado.json`, lo borra y lo devuelve como dict.

    Además borra la carpeta `nueva` si quedó. Nunca lanza; ante un
    archivo corrupto devuelve None y lo borra.
    """
    try:
        base = Path(instalacion) if instalacion is not None else paths.carpeta_instalacion()
        try:
            nueva = paths.paquete_extraido_en(base)
            if nueva.exists():
                _borrar_arbol(nueva)
        except OSError:
            pass
        archivo = paths.resultado_actualizacion_en(base)
        if not archivo.is_file():
            return None
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            try:
                archivo.unlink()
            except OSError:
                pass
            return None
        try:
            archivo.unlink()
        except OSError:
            pass
        return datos if isinstance(datos, dict) else None
    except OSError:
        return None


def lanzar_instalador(carpeta_paquete: str | os.PathLike, ejecutable: str,
                      instalacion: str | os.PathLike, ejecutable_actual: str,
                      pid: int, version_actual: str) -> None:
    """Arranca el instalador que corre dentro del paquete nuevo, sin esperar."""
    ruta = Path(carpeta_paquete) / ejecutable
    subprocess.Popen(
        [str(ruta), "--instalar-actualizacion", str(instalacion), str(pid),
         ejecutable_actual, version_actual],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )
