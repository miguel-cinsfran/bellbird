"""Lleva al nombre nuevo lo que quedó guardado con el nombre viejo.

Dos piezas: las claves de IA del Administrador de credenciales y los accesos
directos que apuntan al ejecutable viejo. La decisión sobre cada acceso es
una función pura; leer y escribir los `.lnk` vive en un envoltorio aparte.
Ningún fallo frena el arranque: se anota en el registro y se reintenta.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from guyrapu.ai import catalogo, claves
from guyrapu.core import diagnostico, paths

logger = diagnostico.obtener_logger(__name__)

PREFIJO_ANTERIOR = "Bellbird/ia/"
NOMBRES_VIEJOS_EXE = ("Bellbird.exe", "YTChatTTS.exe")
# El nombre con espacio es el que la gente escribe a mano en el acceso.
NOMBRES_VIEJOS_ACCESO = tuple(
    Path(nombre).stem for nombre in NOMBRES_VIEJOS_EXE) + ("YTChat TTS",)

_CREAR_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_SCRIPT_LECTURA = r"""
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$ErrorActionPreference = 'Stop'
$entrada = [Console]::OpenStandardInput()
$memoria = New-Object System.IO.MemoryStream
$entrada.CopyTo($memoria)
$texto = [System.Text.Encoding]::UTF8.GetString($memoria.ToArray())
$datos = $texto | ConvertFrom-Json
$shell = New-Object -ComObject WScript.Shell
$salida = @(foreach ($ruta in @($datos)) {
  try {
    $a = $shell.CreateShortcut($ruta)
    [pscustomobject]@{
      ruta = [string]$ruta
      destino = [string]$a.TargetPath
      argumentos = [string]$a.Arguments
      carpeta_inicio = [string]$a.WorkingDirectory
      tecla = [string]$a.Hotkey
      descripcion = [string]$a.Description
      modo_ventana = [int]$a.WindowStyle
      icono = [string]$a.IconLocation
      error = $null
    }
  } catch {
    [pscustomobject]@{ ruta=[string]$ruta; error=$_.Exception.Message }
  }
})
ConvertTo-Json -InputObject $salida -Depth 5 -Compress
"""
_SCRIPT_ESCRITURA = r"""
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$ErrorActionPreference = 'Stop'
$entrada = [Console]::OpenStandardInput()
$memoria = New-Object System.IO.MemoryStream
$entrada.CopyTo($memoria)
$texto = [System.Text.Encoding]::UTF8.GetString($memoria.ToArray())
$datos = $texto | ConvertFrom-Json
$shell = New-Object -ComObject WScript.Shell
$errores = @()
foreach ($d in @($datos)) {
  try {
    $a = $shell.CreateShortcut([string]$d.ruta)
    $a.TargetPath = [string]$d.destino
    $a.Arguments = [string]$d.argumentos
    $a.WorkingDirectory = [string]$d.carpeta_inicio
    $a.Hotkey = [string]$d.tecla
    $a.Description = [string]$d.descripcion
    $a.WindowStyle = [int]$d.modo_ventana
    $a.IconLocation = [string]$d.icono
    $a.Save()
  } catch {
    $errores += [pscustomobject]@{ ruta=[string]$d.ruta; mensaje=$_.Exception.Message }
  }
}
ConvertTo-Json -InputObject @($errores) -Depth 5 -Compress
"""


@dataclass(frozen=True)
class AccesoDirecto:
    """Un `.lnk` leído, con los campos que hay que conservar."""

    ruta: Path
    destino: str = ""
    argumentos: str = ""
    carpeta_inicio: str = ""
    tecla: str = ""
    descripcion: str = ""
    modo_ventana: int = 1
    icono: str = ""


@dataclass(frozen=True)
class Redireccion:
    """Cómo queda un acceso que pasa al ejecutable nuevo."""

    ruta: Path
    destino: str
    argumentos: str
    carpeta_inicio: str
    tecla: str
    descripcion: str
    modo_ventana: int
    icono: str
    ruta_nueva: Path


def _resolver(ruta) -> Path:
    try:
        return Path(ruta).resolve()
    except OSError:
        return Path(os.path.abspath(str(ruta)))


def _misma(ruta_a, ruta_b) -> bool:
    return os.path.normcase(str(_resolver(ruta_a))) == \
        os.path.normcase(str(_resolver(ruta_b)))


def _nombres(archivos) -> set[str]:
    return {Path(nombre).name.casefold() for nombre in archivos}


def _es_carpeta_anclados(carpeta) -> bool:
    partes = Path(carpeta).parts
    return (len(partes) >= 2
            and tuple(parte.casefold() for parte in partes[-2:])
            == ("user pinned", "taskbar"))


def _icono_redirigido(icono, app, viejos, nuevo) -> str:
    if not icono:
        return icono
    parte, coma, indice = icono.rpartition(",")
    if coma and indice.strip().isdigit():
        ruta_icono, sufijo = parte.strip().strip('"'), "," + indice.strip()
    else:
        ruta_icono, sufijo = icono.strip().strip('"'), ""
    if (Path(ruta_icono).name.casefold() not in _nombres(viejos)
            or not _misma(Path(ruta_icono).parent, app)):
        return icono
    return str(Path(app) / nuevo) + sufijo


def decidir_redireccion(acceso, carpeta_app, nombre_nuevo,
                        nombres_viejos=NOMBRES_VIEJOS_EXE, ocupados=()):
    """Devuelve cómo queda el acceso, o None si no hay que tocarlo."""
    if not acceso.destino:
        return None
    app = _resolver(carpeta_app)
    destino = Path(acceso.destino)
    if (destino.name.casefold() not in _nombres(nombres_viejos)
            or not _misma(destino.parent, app)):
        return None
    viejos_sin_ext = {nombre.casefold() for nombre in NOMBRES_VIEJOS_ACCESO}
    ruta_nueva = acceso.ruta
    if (acceso.ruta.stem.casefold() in viejos_sin_ext
            and not _es_carpeta_anclados(acceso.ruta.parent)):
        candidata = acceso.ruta.parent / (Path(nombre_nuevo).stem + ".lnk")
        if not any(_misma(candidata, ocupada) for ocupada in ocupados):
            ruta_nueva = candidata
    return Redireccion(
        ruta=acceso.ruta, destino=str(app / nombre_nuevo),
        argumentos=acceso.argumentos, carpeta_inicio=acceso.carpeta_inicio,
        tecla=acceso.tecla, descripcion=acceso.descripcion,
        modo_ventana=acceso.modo_ventana,
        icono=_icono_redirigido(acceso.icono, app, nombres_viejos,
                                nombre_nuevo),
        ruta_nueva=ruta_nueva)


def carpetas_de_accesos() -> list[Path]:
    """Escritorio, menú Inicio y anclados del usuario actual."""
    perfil = Path(os.environ.get("USERPROFILE") or Path.home())
    appdata = Path(os.environ.get("APPDATA") or perfil / "AppData" / "Roaming")
    return [
        perfil / "Desktop",
        appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        appdata / "Microsoft" / "Internet Explorer" / "Quick Launch"
        / "User Pinned" / "TaskBar",
    ]


def _powershell(script, datos):
    proceso = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        input=json.dumps(datos, ensure_ascii=False), capture_output=True,
        text=True, encoding="utf-8", creationflags=_CREAR_SIN_VENTANA,
        check=False)
    if proceso.returncode != 0:
        detalle = (proceso.stderr or proceso.stdout or "").strip()
        raise OSError(detalle or f"PowerShell devolvió {proceso.returncode}")
    try:
        return json.loads(proceso.stdout or "[]")
    except ValueError as exc:
        raise OSError(f"PowerShell devolvió una respuesta ilegible: {exc}") from exc


def leer_accesos(rutas):
    """Lee todos los `.lnk` indicados en una sola llamada a PowerShell."""
    rutas = [str(Path(ruta)) for ruta in rutas]
    if not rutas:
        return []
    crudos = _powershell(_SCRIPT_LECTURA, rutas)
    if isinstance(crudos, dict):
        crudos = [crudos]
    accesos = []
    for crudo in crudos:
        if not isinstance(crudo, dict) or crudo.get("error"):
            raise OSError(f"{crudo.get('ruta', '')}: {crudo.get('error')}")
        accesos.append(AccesoDirecto(
            ruta=Path(crudo.get("ruta", "")),
            destino=crudo.get("destino", ""),
            argumentos=crudo.get("argumentos", ""),
            carpeta_inicio=crudo.get("carpeta_inicio", ""),
            tecla=crudo.get("tecla", ""),
            descripcion=crudo.get("descripcion", ""),
            modo_ventana=int(crudo.get("modo_ventana") or 1),
            icono=crudo.get("icono", "")))
    return accesos


def escribir_accesos(redirecciones):
    """Escribe todos los accesos en una sola llamada y devuelve los fallos."""
    datos = [{"ruta": str(redireccion.ruta_nueva),
              "destino": redireccion.destino,
              "argumentos": redireccion.argumentos,
              "carpeta_inicio": redireccion.carpeta_inicio,
              "tecla": redireccion.tecla,
              "descripcion": redireccion.descripcion,
              "modo_ventana": redireccion.modo_ventana,
              "icono": redireccion.icono}
             for redireccion in redirecciones]
    if not datos:
        return []
    crudos = _powershell(_SCRIPT_ESCRITURA, datos)
    if isinstance(crudos, dict):
        crudos = [crudos]
    errores = []
    for crudo in crudos:
        if not isinstance(crudo, dict):
            continue
        detalle = crudo.get("mensaje") or crudo.get("error")
        if detalle:
            errores.append(f"{crudo.get('ruta', '')}: {detalle}")
    return errores


def _listar_accesos(carpetas, errores):
    hallados = []
    for carpeta in carpetas:
        try:
            if not Path(carpeta).is_dir():
                continue
            for ruta in sorted(Path(carpeta).rglob("*")):
                if ruta.is_file() and ruta.suffix.casefold() == ".lnk":
                    hallados.append(ruta)
        except OSError as exc:
            logger.warning("No se pudo recorrer %s: %s", carpeta, exc)
            errores.append(f"{carpeta}: {exc}")
    return hallados


def _aplicar_decisiones(accesos, app, nuevo, ocupados, errores):
    redirecciones = []
    for acceso in accesos:
        try:
            decision = decidir_redireccion(acceso, app, nuevo,
                                           ocupados=ocupados)
        except Exception as exc:
            logger.warning("No se pudo decidir el acceso %s: %s",
                           acceso.ruta, exc)
            errores.append(f"{acceso.ruta}: {exc}")
            continue
        if decision is None:
            continue
        if not _misma(decision.ruta_nueva, decision.ruta):
            try:
                os.replace(decision.ruta, decision.ruta_nueva)
            except OSError as exc:
                logger.warning("No se pudo renombrar el acceso %s: %s",
                               decision.ruta, exc)
                errores.append(f"{decision.ruta}: {exc}")
                continue
        ocupados.add(str(_resolver(decision.ruta_nueva)))
        redirecciones.append(decision)
    return redirecciones


def _dejar_marca(marca):
    try:
        marca.parent.mkdir(parents=True, exist_ok=True)
        marca.write_text("ok", encoding="utf-8")
    except OSError as exc:
        logger.warning(
            "No se pudo dejar la marca de accesos directos en %s: %s",
            marca, exc)


def migrar_accesos(carpetas=None, carpeta_app=None, nombre_nuevo=None,
                   marca=None):
    """Redirige los accesos y deja la marca solo si no hubo ningún fallo."""
    app = Path(carpeta_app) if carpeta_app is not None \
        else paths.carpeta_instalacion()
    nuevo = nombre_nuevo or paths.ejecutable_actual()
    marca = Path(marca) if marca is not None \
        else paths.marca_migracion_accesos()
    errores = []
    rutas = _listar_accesos(
        carpetas if carpetas is not None else carpetas_de_accesos(), errores)
    ocupados = {str(_resolver(ruta)) for ruta in rutas}
    accesos = []
    if rutas:
        try:
            accesos = leer_accesos(rutas)
        except Exception as exc:
            logger.warning("No se pudieron leer los accesos directos: %s", exc)
            errores.append(str(exc))
    redirecciones = _aplicar_decisiones(accesos, app, nuevo, ocupados, errores)
    if redirecciones:
        try:
            errores.extend(escribir_accesos(redirecciones))
        except Exception as exc:
            logger.warning("No se pudieron escribir los accesos directos: %s",
                           exc)
            errores.extend(f"{r.ruta_nueva}: {exc}" for r in redirecciones)
    for error in errores:
        logger.warning("Migración de accesos directos: %s", error)
    if not errores:
        _dejar_marca(marca)
    return errores


def migrar_credenciales(prefijo_anterior=PREFIJO_ANTERIOR,
                        prefijo_nuevo=claves.PREFIJO,
                        proveedores=catalogo.PROVEEDORES):
    """Pasa cada clave del prefijo viejo al nuevo, sin tocar la que ya existe."""
    migradas = []
    for proveedor in proveedores:
        try:
            if claves.leer(proveedor, prefijo=prefijo_nuevo) is not None:
                continue
            vieja = claves.leer(proveedor, prefijo=prefijo_anterior)
            if vieja is None:
                continue
            claves.guardar(proveedor, vieja, prefijo=prefijo_nuevo)
            claves.borrar(proveedor, prefijo=prefijo_anterior)
            migradas.append(proveedor)
        except Exception as exc:
            logger.warning("No se pudo migrar la clave de %s: %s",
                           proveedor, exc)
    return migradas


def necesita_migrar_accesos() -> bool:
    if not getattr(sys, "frozen", False):
        return False
    try:
        return not paths.marca_migracion_accesos().exists()
    except OSError:
        return True


def _migrar_accesos_en_hilo():
    try:
        migrar_accesos()
    except Exception as exc:
        logger.warning("Falló la migración de accesos directos: %s", exc)


def lanzar_migracion_accesos() -> bool:
    """Lanza la redirección en un hilo, una sola vez, desde el paquete."""
    if not necesita_migrar_accesos():
        return False
    hilo = threading.Thread(target=_migrar_accesos_en_hilo,
                            name="MigracionAccesos", daemon=True)
    hilo.start()
    return True
