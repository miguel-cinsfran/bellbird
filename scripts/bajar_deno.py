#!/usr/bin/env python
"""Baja deno empaquetado para yt-dlp y lo deja en una carpeta.

Uso:
    uv run python scripts/bajar_deno.py DESTINO

Pide la última publicación de deno en GitHub, baja el zip de Windows
de 64 bits con su firma, comprueba el SHA-256 y solo si coincide
extrae `deno.exe` en DESTINO. La firma no viene en formato
SHA2-256SUMS como la de yt-dlp: es la salida de `Get-FileHash` de
PowerShell, con una línea `Hash      : CBA84B...` en mayúsculas.

Sale con 0 si dejó `deno.exe` y con otro código si no, con el motivo
en una línea. Sin deno el paquete sale igual, solo sin ese archivo.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Raíz del repositorio: la carpeta de arriba de la suya.
RAIZ = str(Path(__file__).resolve().parent.parent)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from bellbird.core import paths  # noqa: E402

URL_API_RELEASES = "https://api.github.com/repos/denoland/deno/releases/latest"
NOMBRE_ZIP = "deno-x86_64-pc-windows-msvc.zip"
NOMBRE_FIRMAS = "deno-x86_64-pc-windows-msvc.zip.sha256sum"
TIEMPO_ESPERA = 30


def _agente() -> str:
    from bellbird.core import config
    return f"Bellbird/{config.APP_VERSION}"


def firma_desde_get_file_hash(texto: str) -> str:
    """La firma de una salida de `Get-FileHash`, en minúsculas o vacío."""
    for linea in (texto or "").splitlines():
        if ":" not in linea:
            continue
        izquierda, _, derecha = linea.partition(":")
        if izquierda.strip().lower() != "hash":
            continue
        candidato = derecha.strip().split()[0] if derecha.strip() else ""
        if len(candidato) == 64 and all(
                letra in "0123456789abcdefABCDEF" for letra in candidato):
            return candidato.lower()
    return ""


def _pedir_json(url: str):
    solicitud = Request(url, headers={"User-Agent": _agente(),
                                      "Accept": "application/vnd.github+json"})
    with urlopen(solicitud, timeout=TIEMPO_ESPERA) as respuesta:
        return json.load(respuesta)


def _pedir_texto(url: str) -> str:
    solicitud = Request(url, headers={"User-Agent": _agente()})
    with urlopen(solicitud, timeout=TIEMPO_ESPERA) as respuesta:
        return respuesta.read().decode("utf-8")


def _descargar(url: str, destino: Path) -> None:
    solicitud = Request(url, headers={"User-Agent": _agente()})
    with urlopen(solicitud, timeout=TIEMPO_ESPERA) as respuesta:
        with destino.open("wb") as archivo:
            while True:
                bloque = respuesta.read(1024 * 1024)
                if not bloque:
                    break
                archivo.write(bloque)


def _activos(datos) -> tuple[str, str]:
    try:
        activos = {activo["name"]: activo
                   for activo in datos["assets"]}
        zip_url = activos[NOMBRE_ZIP]["browser_download_url"]
        firmas_url = activos[NOMBRE_FIRMAS]["browser_download_url"]
    except (KeyError, TypeError, AttributeError):
        return "", ""
    if not isinstance(zip_url, str) or not isinstance(firmas_url, str):
        return "", ""
    return zip_url, firmas_url


def instalar_zip(ruta_zip: Path, destino: Path,
                 firma_esperada: str) -> tuple[bool, str]:
    """Comprueba el zip y extrae `deno.exe` en destino. No deja nada si falla."""
    ruta_zip, destino = Path(ruta_zip), Path(destino)
    try:
        resumen = hashlib.sha256()
        with ruta_zip.open("rb") as archivo:
            for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
                resumen.update(bloque)
    except OSError as error:
        return False, f"no se pudo leer el zip de deno: {error}"
    if resumen.hexdigest().lower() != firma_esperada.strip().lower():
        return False, "la firma SHA-256 de deno no coincide"
    try:
        with zipfile.ZipFile(ruta_zip) as archivo:
            try:
                datos = archivo.read(paths.NOMBRE_DENO)
            except KeyError:
                return False, "el zip de deno no trae deno.exe"
        destino.mkdir(parents=True, exist_ok=True)
        (destino / paths.NOMBRE_DENO).write_bytes(datos)
    except (OSError, zipfile.BadZipFile) as error:
        return False, f"no se pudo dejar deno.exe: {error}"
    return True, "deno listo"


def _bajar_publicacion(destino: Path) -> tuple[bool, str]:
    try:
        datos = _pedir_json(URL_API_RELEASES)
    except (HTTPError, URLError, OSError, ValueError) as error:
        return False, f"no se pudo consultar la publicación de deno: {error}"
    version = datos.get("tag_name", "") if isinstance(datos, dict) else ""
    url_zip, url_firmas = _activos(datos)
    if not url_zip or not url_firmas:
        return False, "la publicación de deno no trae los archivos de Windows"
    if not url_zip.lower().startswith("https://"):
        return False, "la descarga de deno no usa https"
    try:
        texto_firmas = _pedir_texto(url_firmas)
    except (HTTPError, URLError, OSError, UnicodeError) as error:
        return False, f"no se pudieron descargar las firmas de deno: {error}"
    firma = firma_desde_get_file_hash(texto_firmas)
    if not firma:
        return False, "no se encontró la firma de deno"
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(prefix="deno-", suffix=".zip",
                                         delete=False) as archivo:
            temporal = Path(archivo.name)
        _descargar(url_zip, temporal)
        ok, motivo = instalar_zip(temporal, destino, firma)
    except (HTTPError, URLError, OSError, ValueError) as error:
        return False, f"no se pudo descargar deno: {error}"
    finally:
        if temporal is not None:
            try:
                temporal.unlink()
            except OSError:
                pass
    if not ok:
        return False, motivo
    etiqueta = f" {version}" if version else ""
    return True, f"deno{etiqueta} en {destino}"


def main(destino_texto: str) -> int:
    destino = Path(destino_texto)
    ok, motivo = _bajar_publicacion(destino)
    print(("OK: " if ok else "AVISO: ") + motivo)
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: bajar_deno.py DESTINO")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
