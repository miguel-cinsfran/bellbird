"""Origen, respaldo y restauración de los datos de música real."""

from __future__ import annotations

import array
import configparser
import math
import random
import shutil
import tempfile
import time
import wave
from pathlib import Path

from banco_app import Aplicacion, contestar_salir_si_aparece
from bellbird.core import paths
from bellbird.core.config import (
    codificar_texto_ini, decodificar_texto_ini, guardar_opciones)
from bellbird.music.biblioteca import EXTENSIONES

from musica_real import _TOPE_RECORRIDO, medidor_sonido


def preparar_origen(rec):
    """Elige los temas y las rutas. Devuelve los elegidos, o None si no sigue."""
    if medidor_sonido is None or not medidor_sonido.DISPONIBLE:
        rec.res.no_probado("musica_real: sin medidor de sonido en esta PC")
        return None

    pedida = (getattr(rec.args, "carpeta_musica", None) or "").strip()
    if pedida:
        origen = Path(pedida).expanduser()
    else:
        origen = None
        try:
            lector = configparser.ConfigParser(interpolation=None)
            lector.read(paths.config_ini(), encoding="utf-8")
            cruda = lector.get("musica", "carpeta", fallback="").strip()
            if cruda:
                origen = Path(decodificar_texto_ini(cruda))
        except Exception:
            origen = None
        if origen is None:
            origen = Path.home() / "Music"
    if not origen.is_dir():
        rec.res.no_probado(f"musica_real: no hay carpeta de música en «{origen}»")
        return None
    candidatos = sorted(
        (p for p in origen.rglob("*")
         if p.is_file() and p.suffix.lower() in EXTENSIONES),
        key=lambda p: str(p).lower())
    if len(candidatos) < 5:
        rec.res.no_probado(f"musica_real: la carpeta «{origen}» tiene "
                           f"{len(candidatos)} temas y hacen falta 5")
        return None
    elegidos = random.Random(18102026).sample(candidatos, 5)
    rec.nombres_archivo = ([f"{i + 1:02d} {f.name}"
                            for i, f in enumerate(elegidos)]
                           + ["06 corto QA.wav"])
    if any(", " in Path(nombre).stem for nombre in rec.nombres_archivo):
        rec.res.no_probado(
            "musica_real: un tema elegido tiene una coma en el nombre y no "
            "se puede separar el título del artista y la duración")
        return None

    rec.ruta_config = paths.config_ini()
    rec.ruta_listas = paths.listas_musica()
    rec.ruta_estado = paths.estado_musica()
    rec.ruta_etiquetas = paths.cache_etiquetas_musica()
    return elegidos


def preparar_datos(rec, elegidos):
    """Carpeta temporal, respaldo, claves de música y aplicación propia."""
    rec.tmp_musica = Path(tempfile.mkdtemp(prefix="qa-musica-"))
    rec.tmp_respaldo = Path(tempfile.mkdtemp(prefix="qa-musica-respaldo-"))
    for i, fuente in enumerate(elegidos):
        shutil.copy2(fuente, rec.tmp_musica / rec.nombres_archivo[i])
    with wave.open(str(rec.tmp_musica / "06 corto QA.wav"), "w") as oleada:
        oleada.setnchannels(1)
        oleada.setsampwidth(2)
        oleada.setframerate(44100)
        muestras = array.array(
            "h", (int(16383 * math.sin(2 * math.pi * 440 * i / 44100))
                  for i in range(44100 * 3)))
        oleada.writeframes(muestras.tobytes())
    respaldar(rec)
    cambiar_claves(rec)
    arrancar_aplicacion(rec)
    rec._tope = time.monotonic() + _TOPE_RECORRIDO


def respaldar(rec):
    """Copia la configuración, las listas y los estados a otra temporal."""
    if rec.ruta_config.is_file():
        rec.respaldo_config = rec.ruta_config.read_bytes()
        (rec.tmp_respaldo / "config.ini").write_bytes(rec.respaldo_config)
    if rec.ruta_listas.is_dir():
        rec.listas_habia = True
        shutil.copytree(rec.ruta_listas, rec.tmp_respaldo / "listas")
    if rec.ruta_estado.is_file():
        rec.respaldo_estado = rec.ruta_estado.read_bytes()
        (rec.tmp_respaldo / "musica_estado.json").write_bytes(
            rec.respaldo_estado)
    if rec.ruta_etiquetas.is_file():
        rec.respaldo_etiquetas = rec.ruta_etiquetas.read_bytes()
        (rec.tmp_respaldo / "etiquetas_musica.json").write_bytes(
            rec.respaldo_etiquetas)


def cambiar_claves(rec):
    """Fija solo las claves de música necesarias."""
    cambios = [
        ("musica", "carpeta", codificar_texto_ini(str(rec.tmp_musica))),
        ("musica", "volumen", "40"),
        ("musica", "aleatorio", "false"),
        ("musica", "repetir", "false"),
        ("musica", "retomar", "false"),
        ("musica", "decir", "titulo"),
        ("musica", "decir_pausa", "true"),
        ("musica", "sonido_tema", "true"),
        ("musica", "preguntar_igualar", "false"),
        ("musica", "mostrar_cola", "false"),
        ("musica", "atajos_globales", "false"),
    ]
    if rec.ruta_config.is_file():
        if not guardar_opciones(rec.ruta_config, cambios):
            rec.corta("musica_real: no se pudo fijar la configuración "
                      "de música")
    else:
        nuevo = configparser.ConfigParser(interpolation=None)
        nuevo["musica"] = {clave: valor for _, clave, valor in cambios}
        with open(rec.ruta_config, "w", encoding="utf-8") as f:
            nuevo.write(f)


def arrancar_aplicacion(rec):
    """Levanta una aplicación propia, con la sonda adentro."""
    rec.propia = Aplicacion(rec.app.anuncios_ruta.parent / "musica_real")
    rec.propia.arrancar()
    if not rec.propia.esperar_lista(segundos=60):
        rec.corta("musica_real: la aplicación no contestó al ping en 60 s")
    if not rec.propia.dijo("grabador instalado"):
        rec.corta("musica_real: la sonda no dejó constancia; "
                  "podría estar hablando")
    try:
        pid_sonda = rec.propia.pedir("pid").get("datos", {}).get("pid")
    except Exception as exc:
        rec.corta(f"musica_real: no se pudo leer el pid de la sonda: {exc}")
    if not isinstance(pid_sonda, int) or pid_sonda <= 0:
        rec.corta("musica_real: la sonda devolvió un pid inválido")
    rec.pids = {rec.propia.proceso.pid, pid_sonda}
    rec.sin_salida = False


def cerrar_aplicacion(rec):
    """Cierra la aplicación propia y, si no se va, la mata."""
    if rec.propia is None:
        return
    try:
        try:
            rec.propia.pedir("salir", tiempo=5.0, tolerar=True)
        except Exception:
            pass
        try:
            contestar_salir_si_aparece(segundos=2.0)
        except Exception:
            pass
        limite = time.monotonic() + 15.0
        while (rec.propia.proceso is not None
               and rec.propia.proceso.poll() is None
               and time.monotonic() < limite):
            time.sleep(0.5)
        if (rec.propia.proceso is not None
                and rec.propia.proceso.poll() is None):
            try:
                rec.propia.proceso.kill()
            except Exception:
                pass
            rec.res.nota("musica_real: la aplicación no cerró en 15 s "
                         "y se la mató")
    finally:
        try:
            rec.propia._salida.close()
        except Exception:
            pass


def restaurar_config(rec):
    """Devuelve `config.ini` a como estaba, o lo borra si lo creó la escena."""
    try:
        if rec.respaldo_config is None:
            try:
                rec.ruta_config.unlink()
            except FileNotFoundError:
                pass
            if rec.ruta_config.exists():
                rec.res.fallo("musica_real: config.ini no existía y no se "
                              "pudo borrar el creado")
        else:
            rec.ruta_config.write_bytes(rec.respaldo_config)
            if rec.ruta_config.read_bytes() != rec.respaldo_config:
                rec.res.fallo("musica_real: config.ini no quedó idéntico "
                              "al respaldo")
    except Exception as exc:
        rec.res.fallo(f"musica_real: no se pudo restaurar config.ini: {exc}")


def restaurar_carpetas(rec):
    """Devuelve la carpeta de listas, el estado y las etiquetas a como estaban."""
    try:
        shutil.rmtree(rec.ruta_listas, ignore_errors=True)
        if rec.listas_habia:
            shutil.copytree(rec.tmp_respaldo / "listas", rec.ruta_listas)
    except Exception as exc:
        rec.res.fallo("musica_real: no se pudo restaurar la carpeta "
                      f"de listas: {exc}")
    for nombre, ruta, respaldo in (
            ("musica_estado.json", rec.ruta_estado, rec.respaldo_estado),
            ("etiquetas_musica.json", rec.ruta_etiquetas,
             rec.respaldo_etiquetas)):
        try:
            if respaldo is None:
                try:
                    ruta.unlink()
                except FileNotFoundError:
                    pass
                if ruta.exists():
                    rec.res.fallo(f"musica_real: {nombre} no existía y no "
                                  "se pudo borrar el creado")
            else:
                ruta.write_bytes(respaldo)
        except Exception as exc:
            rec.res.fallo(f"musica_real: no se pudo restaurar {nombre}: "
                          f"{exc}")


def limpiar_temporales(rec):
    """Borra las dos carpetas temporales de la escena."""
    if rec.tmp_musica is not None:
        shutil.rmtree(rec.tmp_musica, ignore_errors=True)
    if rec.tmp_respaldo is not None:
        shutil.rmtree(rec.tmp_respaldo, ignore_errors=True)


def restaurar(rec):
    """Deja los datos del usuario exactamente como estaban."""
    cerrar_aplicacion(rec)
    restaurar_config(rec)
    restaurar_carpetas(rec)
    limpiar_temporales(rec)
