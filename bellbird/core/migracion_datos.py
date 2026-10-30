"""Muda los datos de usuario de la raíz a la subcarpeta de datos.

Módulo puro, sin wx: recibe todas las rutas por parámetro y nunca arma
una por su cuenta. No lanza nunca: cada fallo se anota en el resultado
y se sigue con el elemento siguiente.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from bellbird.core import diagnostico

logger = diagnostico.obtener_logger(__name__)


@dataclass
class ResultadoMigracion:
    """Lo que hizo un llamado a migrar, en nombres de archivo."""

    movidos: list[str] = field(default_factory=list)
    copiados: list[str] = field(default_factory=list)
    conflictos: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


def _trasladar(vieja: Path, nueva: Path, datos: Path,
               resultado: ResultadoMigracion) -> None:
    """Aplica las reglas a un solo elemento, sin lanzar."""
    try:
        if vieja == nueva:
            return
        if not vieja.exists() and not vieja.is_symlink():
            return
        if nueva.exists() or nueva.is_symlink():
            resultado.conflictos.append(nueva.name)
            return
        try:
            datos.mkdir(parents=True, exist_ok=True)
            nueva.parent.mkdir(parents=True, exist_ok=True)
            os.replace(vieja, nueva)
            resultado.movidos.append(nueva.name)
        except OSError:
            try:
                if vieja.is_dir() and not vieja.is_file():
                    shutil.copytree(vieja, nueva)
                else:
                    shutil.copy2(vieja, nueva)
                resultado.copiados.append(nueva.name)
            except Exception as exc_copia:
                resultado.errores.append(f"{nueva.name}: {exc_copia}")
    except Exception as exc:
        resultado.errores.append(f"{nueva.name}: {exc}")


def _rotados_de(vieja: Path, datos: Path,
                nuevo: Path | None = None) -> list[tuple[Path, Path]]:
    """Rotados que acompañan a un archivo, como pares vieja y nueva.

    Con `nuevo`, los rotados nuevos llevan ese nombre con el sufijo viejo:
    sirve para renombrar un registro con sus rotados.
    """
    hallados: list[tuple[Path, Path]] = []
    try:
        padre = vieja.parent
        if not padre.is_dir():
            return hallados
        prefijo = vieja.name + "."
        for hijo in sorted(padre.iterdir()):
            if hijo == vieja or not hijo.is_file():
                continue
            if not hijo.name.startswith(prefijo):
                continue
            resto = hijo.name[len(prefijo):]
            if resto.isdigit():
                if nuevo is None:
                    hallados.append((hijo, datos / hijo.name))
                else:
                    hallados.append(
                        (hijo, nuevo.parent / (nuevo.name + "." + resto)))
    except OSError:
        pass
    return hallados


def _copiar_sounds_ini(instalacion: Path, datos: Path, sounds_ini: Path,
                       resultado: ResultadoMigracion) -> None:
    """La plantilla de sonidos de la raíz solo se copia, nunca se mueve."""
    try:
        destino_sonidos = Path(sounds_ini)
        vieja_sonidos = instalacion / destino_sonidos.name
        if vieja_sonidos == destino_sonidos:
            return
        if destino_sonidos.exists() or destino_sonidos.is_symlink():
            return
        if vieja_sonidos.is_file():
            try:
                datos.mkdir(parents=True, exist_ok=True)
                destino_sonidos.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(vieja_sonidos, destino_sonidos)
                resultado.copiados.append(destino_sonidos.name)
            except Exception as exc:
                resultado.errores.append(f"{destino_sonidos.name}: {exc}")
    except Exception as exc:
        try:
            resultado.errores.append(f"{Path(sounds_ini).name}: {exc}")
        except Exception as error:
            logger.debug("no se pudo anotar el fallo de sounds.ini en el resultado: %s", error)


def _migrar_binario(vieja: Path, nueva: Path,
                    resultado: ResultadoMigracion) -> None:
    """Copia el binario viejo a su nombre nuevo y lo borra solo si la copia quedó igual."""
    try:
        if not vieja.is_file():
            return
        if nueva.exists() or nueva.is_symlink():
            resultado.conflictos.append(nueva.name)
            return
        try:
            nueva.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(vieja, nueva)
        except OSError as exc:
            resultado.errores.append(f"{nueva.name}: {exc}")
            return
        if nueva.stat().st_size != vieja.stat().st_size:
            try:
                nueva.unlink()
            except OSError:
                pass
            resultado.errores.append(
                f"{nueva.name}: la copia quedó con otro tamaño")
            return
        resultado.copiados.append(nueva.name)
        try:
            vieja.unlink()
        except OSError as exc:
            resultado.errores.append(f"{vieja.name}: {exc}")
            return
        try:
            vieja.parent.rmdir()
        except OSError:
            pass
    except Exception as exc:
        resultado.errores.append(f"{nueva.name}: {exc}")


def _migrar_registro(vieja: Path, nueva: Path, datos: Path,
                     resultado: ResultadoMigracion) -> None:
    """Renombra un registro y sus rotados al nombre nuevo, sin pisar el que ya exista."""
    try:
        _trasladar(vieja, nueva, datos, resultado)
        for vieja_rot, nueva_rot in _rotados_de(vieja, datos, nueva):
            _trasladar(vieja_rot, nueva_rot, datos, resultado)
    except Exception as exc:
        resultado.errores.append(f"{nueva.name}: {exc}")


def migrar(instalacion: Path, datos: Path, rutas: list[Path],
           sounds_ini: Path,
           pares_anteriores: tuple | None = None) -> ResultadoMigracion:
    """Mueve cada ruta desde la raíz hasta la carpeta de datos.

    Para cada archivo también se migran sus rotados, que llevan el mismo
    nombre con punto y dígitos al final. Si el destino ya existe no se
    toca nada y se anota el conflicto. Si el movimiento falla se intenta
    la copia y la vieja se deja donde está. Con pares (vieja, nueva)
    también lleva el yt-dlp y los registros a sus nombres nuevos, sin
    pisar nada: el binario se copia y se borra el viejo solo si la copia
    quedó con el mismo tamaño, y los registros se renombran con rotados.
    """
    resultado = ResultadoMigracion()
    instalacion = Path(instalacion)
    datos = Path(datos)
    for ruta in rutas:
        try:
            nueva = Path(ruta)
            try:
                vieja = instalacion / nueva.relative_to(datos)
            except ValueError as exc:
                resultado.errores.append(f"{nueva.name}: {exc}")
                continue
            _trasladar(vieja, nueva, datos, resultado)
            for vieja_rot, nueva_rot in _rotados_de(vieja, datos):
                _trasladar(vieja_rot, nueva_rot, datos, resultado)
        except Exception as exc:
            try:
                resultado.errores.append(f"{Path(ruta).name}: {exc}")
            except Exception as error:
                logger.debug("no se pudo anotar el fallo de migración en el resultado: %s", error)
    _copiar_sounds_ini(instalacion, datos, sounds_ini, resultado)
    if pares_anteriores is not None:
        binarios, registros = pares_anteriores
        for vieja, nueva in binarios:
            _migrar_binario(Path(vieja), Path(nueva), resultado)
        for vieja, nueva in registros:
            _migrar_registro(Path(vieja), Path(nueva), datos, resultado)
    return resultado
