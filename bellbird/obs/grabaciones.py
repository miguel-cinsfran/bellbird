"""Registro de las grabaciones que la app detuvo.

Su única razón para cambiar: qué grabaciones recuerda la app y cómo se
dicen. El disco se lee y se escribe acá, siempre con una ruta opcional:
sin ruta usa `paths.grabaciones()`, para que las pruebas no toquen los
datos reales.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path

from bellbird.core import archivos, diagnostico, paths
from bellbird.core.idioma import _
from bellbird.music.pregunta_igualar import texto_tamano

logger = diagnostico.obtener_logger(__name__)

TOPE_ENTRADAS = 200

_CANDADO = threading.Lock()


def _ruta_de(ruta):
    return ruta or paths.grabaciones()


def _leer_sin_candado(ruta) -> list:
    datos = archivos.leer_json(_ruta_de(ruta), [])
    if not isinstance(datos, list):
        return []
    return [entrada for entrada in datos if isinstance(entrada, dict)]


def _escribir(entradas, ruta) -> None:
    archivos.escribir_json_atomico(_ruta_de(ruta), entradas)


def leer(ruta=None) -> list:
    """Las grabaciones anotadas, de la más nueva a la más vieja."""
    with _CANDADO:
        return _leer_sin_candado(ruta)


def anotar(archivo, ruta=None, ahora=None) -> None:
    """Agrega la grabación al principio y conserva como mucho 200.

    Un fallo de disco se registra y no llega a quien anunció el archivo.
    """
    entrada = {"ruta": str(archivo),
               "fecha": ahora if ahora is not None else datetime.now().timestamp()}
    with _CANDADO:
        try:
            entradas = _leer_sin_candado(ruta)
            _escribir(([entrada] + entradas)[:TOPE_ENTRADAS], ruta)
        except Exception as error:
            logger.debug("no se pudo anotar la grabación: %s", error)


def existentes(ruta=None) -> list:
    """Las entradas cuyo archivo sigue en el disco, con su tamaño."""
    resultado = []
    with _CANDADO:
        for entrada in _leer_sin_candado(ruta):
            archivo = entrada.get("ruta") or ""
            try:
                tamano = os.path.getsize(archivo)
            except OSError:
                continue
            resultado.append({**entrada, "tamano": tamano})
    return resultado


def quitar(archivo, ruta=None) -> None:
    """Saca la entrada de la lista; nunca toca el archivo del disco."""
    with _CANDADO:
        try:
            entradas = _leer_sin_candado(ruta)
            resto = [entrada for entrada in entradas
                     if str(entrada.get("ruta") or "") != str(archivo)]
            if resto != entradas:
                _escribir(resto, ruta)
        except Exception as error:
            logger.debug("no se pudo quitar la grabación: %s", error)


def texto_fila(entrada) -> str:
    """«nombre, dd/mm/aaaa hh:mm, tamaño» para una fila de la lista."""
    nombre = Path(str(entrada.get("ruta") or "")).name
    fecha = _fecha_mostrada(entrada.get("fecha"))
    tamano = texto_tamano(entrada.get("tamano") or 0)
    return _("{nombre}, {fecha}, {tamano}").format(
        nombre=nombre, fecha=fecha, tamano=tamano)


def _fecha_mostrada(segundos) -> str:
    try:
        fecha = datetime.fromtimestamp(float(segundos))
    except (TypeError, ValueError, OSError):
        return ""
    # Traductores: fecha y hora de una grabación; se ordena como la fecha
    # corta de Windows en ese idioma. {hora} y {minuto} van con dos cifras.
    return _("{dia}/{mes}/{anio} {hora}:{minuto}").format(
        dia=f"{fecha.day:02d}", mes=f"{fecha.month:02d}",
        anio=f"{fecha.year:04d}", hora=f"{fecha.hour:02d}",
        minuto=f"{fecha.minute:02d}")


def anotar_y_decir(archivo, ruta=None) -> str:
    """Anota la grabación y devuelve la frase que se anuncia.

    Sin archivo devuelve la frase de siempre, como si OBS no hubiera
    informado la ruta.
    """
    if not archivo:
        from bellbird.obs import obs_estado
        return obs_estado.frase_resultado("grabacion_detenida")
    anotar(archivo, ruta)
    nombre = Path(str(archivo)).name
    return _("Grabación guardada: {nombre}").format(nombre=nombre)
