"""Instalador que reemplaza la aplicación con respaldo y vuelta atrás.

Corre DENTRO del exe nuevo, extraído en `data/actualizacion/nueva/...`,
mientras la app vieja se cierra. No importa wx, no crea ventanas, no
anuncia nada y no toca el mutex de instancia única.

Cada paso se anota con fecha en `registro.log`, con `logging` propio
del módulo hacia ese archivo.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ytchat.core import actualizacion
from ytchat.core import paths


ARGUMENTO_INSTALADOR = "--instalar-actualizacion"

INTERVALO_ARRANQUE = 0.5

logger = logging.getLogger(f"ytchat.{__name__}")


def _preparar_registro(instalacion: Path) -> None:
    for manejador in list(logger.handlers):
        logger.removeHandler(manejador)
        try:
            manejador.close()
        except Exception:
            pass
    registro = paths.registro_actualizacion_en(instalacion)
    try:
        registro.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    try:
        manejador = logging.FileHandler(registro, encoding="utf-8")
    except OSError:
        return
    manejador.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(manejador)
    logger.setLevel(logging.INFO)
    logger.propagate = False


# ── Funciones reales, inyectables en las pruebas ───────────────────────────

def esperar_pid(pid: int, tope: float) -> bool:
    """Devuelve si el proceso terminó antes del tope en segundos."""
    inicio = time.monotonic()
    pid = int(pid)
    while True:
        if _termino(pid):
            return True
        if time.monotonic() - inicio >= tope:
            return False
        time.sleep(0.2)


def _termino(pid: int) -> bool:
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.restype = ctypes.c_void_p
            handle = kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return True
            try:
                kernel32.WaitForSingleObject.restype = ctypes.c_ulong
                return kernel32.WaitForSingleObject(handle, 0) == 0
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except (PermissionError, OSError):
        return False
    return False


def lanzar(orden: list[str] | str | os.PathLike):
    """Arranca un proceso y devuelve el objeto Popen para `matar`.

    Acepta la orden ya traducida (lista) o una ruta suelta, que se
    lanza tal cual.
    """
    if isinstance(orden, (str, os.PathLike)):
        orden = [str(orden)]
    return subprocess.Popen(
        list(orden),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )


def matar(proceso) -> None:
    """Termina un proceso arrancado con `lanzar`."""
    try:
        proceso.terminate()
    except Exception:
        return
    try:
        proceso.wait(timeout=10)
    except Exception:
        try:
            proceso.kill()
        except Exception:
            pass


def orden_para_exe(ruta_exe: str | os.PathLike) -> list[str]:
    """Traduce la ruta del exe a la orden que se lanza. En la app es el exe mismo."""
    return [str(ruta_exe)]


# ── Instalación ────────────────────────────────────────────────────────────

def _entradas_a_reemplazar(paquete: Path, ejecutable_viejo: str) -> list[str]:
    entradas = []
    for hijo in sorted(paquete.iterdir()):
        if hijo.name not in entradas:
            entradas.append(hijo.name)
    for nombre in (ejecutable_viejo, "_internal"):
        if nombre and nombre not in entradas:
            entradas.append(nombre)
    return [nombre for nombre in entradas
            if nombre not in ("data", "Descargas", "sounds")]


def _borrar_entrada(ruta: Path) -> None:
    if ruta.is_dir() and not ruta.is_symlink():
        shutil.rmtree(ruta)
    elif ruta.exists() or ruta.is_symlink():
        ruta.unlink()


def _copiar_entrada(origen: Path, destino: Path) -> None:
    if origen.is_dir() and not origen.is_symlink():
        shutil.copytree(origen, destino)
    else:
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen, destino)


def _temas_del_paquete(paquete: Path) -> list[str]:
    """Nombres de los temas que trae el paquete en `sounds/themes`."""
    temas = paquete / "sounds" / "themes"
    try:
        if not temas.is_dir():
            return []
        return sorted(hijo.name for hijo in temas.iterdir()
                      if hijo.is_dir() and not hijo.is_symlink())
    except OSError:
        return []


def _agregar_sonido_faltante(origen: Path, destino: Path, base_sonidos: Path,
                             agregados: list[str]) -> None:
    """Copia `origen` en `destino` solo si falta, y lo anota en `agregados`.

    `agregados` guarda rutas relativas a `base_sonidos`, para que la
    vuelta atrás las borre. Si `origen` es carpeta y `destino` ya existe,
    recorre adentro y agrega solo los archivos que falten.
    """
    if origen.is_dir() and not origen.is_symlink():
        if not destino.exists() and not destino.is_symlink():
            shutil.copytree(origen, destino)
            agregados.append(str(destino.relative_to(base_sonidos)))
            return
        try:
            hijos = sorted(origen.iterdir())
        except OSError:
            raise
        for hijo in hijos:
            _agregar_sonido_faltante(hijo, destino / hijo.name,
                                     base_sonidos, agregados)
    else:
        if destino.exists() or destino.is_symlink():
            return
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen, destino)
        agregados.append(str(destino.relative_to(base_sonidos)))


def instalar(paquete: str | os.PathLike, instalacion: str | os.PathLike,
             pid: int, ejecutable_viejo: str, desde: str,
             *, esperar_pid, lanzar, matar, tope_cierre: float = 60,
             tope_arranque: float = 90,
             orden_para=orden_para_exe) -> bool:
    """Reemplaza la instalación con el paquete nuevo, con vuelta atrás.

    `paquete` es la carpeta raíz del paquete nuevo, de donde corre el
    instalador. `esperar_pid(pid, tope)` dice si el proceso terminó;
    `lanzar(orden)` arranca un proceso que `matar(objeto)` termina.
    `orden_para` traduce la ruta del exe a la orden que se lanza: en la
    app es el exe mismo (`orden_para_exe`), en pruebas puede ser un
    intérprete con un guion, y ahí `lanzar` puede ser `subprocess.Popen`
    sin más. Devuelve verdadero si la versión nueva quedó instalada y
    confirmó.
    """
    paquete = Path(paquete)
    instalacion = Path(instalacion)
    _preparar_registro(instalacion)

    respaldo = paths.respaldo_actualizacion_en(instalacion)
    pendiente = paths.actualizacion_pendiente_en(instalacion)
    arranque = paths.arranque_confirmado_en(instalacion)
    resultado = paths.resultado_actualizacion_en(instalacion)

    def _fallo(motivo: str, con_resultado: bool = True) -> bool:
        logger.error("fallo: %s", motivo)
        if con_resultado:
            try:
                resultado.parent.mkdir(parents=True, exist_ok=True)
                resultado.write_text(json.dumps(
                    {"resultado": "fallo", "motivo": motivo},
                    ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
        return False

    def _arrancar(nombre_exe: str):
        return lanzar(orden_para(str(instalacion / nombre_exe)))

    # Paso a: espera a que termine la app vieja sin tocar nada.
    logger.info("instalador: espera al pid %s", pid)
    if not esperar_pid(pid, tope_cierre):
        logger.error("la aplicación no se cerró a tiempo")
        return False
    logger.info("la aplicación se cerró")

    # Paso b: manifiesto del paquete nuevo.
    try:
        contenido = json.loads(
            (paquete / paths.NOMBRE_MANIFIESTO).read_text(encoding="utf-8"))
        hacia = contenido.get("version") if isinstance(contenido, dict) else None
        ejecutable_nuevo = actualizacion.validar_paquete(paquete, hacia)
    except (actualizacion.PaqueteInvalido, OSError, ValueError) as error:
        return _fallo(f"el paquete no es válido: {error}")
    logger.info("paquete válido hacia la versión %s", hacia)

    # Paso c: entradas a reemplazar.
    entradas = _entradas_a_reemplazar(paquete, ejecutable_viejo)
    logger.info("entradas a reemplazar: %s", ", ".join(entradas) or "ninguna")

    # Paso d: mueve lo viejo al respaldo con os.replace.
    try:
        if respaldo.exists():
            shutil.rmtree(respaldo)
    except OSError as error:
        return _fallo(f"no se pudo vaciar el respaldo: {error}")
    movidas: list[str] = []
    temas = _temas_del_paquete(paquete)
    temas_movidos: list[str] = []
    try:
        respaldo.mkdir(parents=True, exist_ok=True)
        for nombre in entradas:
            origen = instalacion / nombre
            if not origen.exists() and not origen.is_symlink():
                continue
            os.replace(origen, respaldo / nombre)
            movidas.append(nombre)
        for tema in temas:
            origen_tema = instalacion / "sounds" / "themes" / tema
            if not origen_tema.exists() and not origen_tema.is_symlink():
                continue
            destino_tema = respaldo / "sounds" / "themes" / tema
            destino_tema.parent.mkdir(parents=True, exist_ok=True)
            os.replace(origen_tema, destino_tema)
            temas_movidos.append(tema)
    except OSError as error:
        logger.error("no se pudo mover %s al respaldo: %s",
                     instalacion / nombre, error)
        for tema in reversed(temas_movidos):
            try:
                destino_tema = instalacion / "sounds" / "themes" / tema
                destino_tema.parent.mkdir(parents=True, exist_ok=True)
                os.replace(respaldo / "sounds" / "themes" / tema,
                           destino_tema)
            except OSError:
                pass
        for nombre in reversed(movidas):
            try:
                os.replace(respaldo / nombre, instalacion / nombre)
            except OSError:
                pass
        motivo = ("no se pudo mover un archivo de la versión anterior, "
                  "quizá sigue abierto en otro programa")
        _fallo(motivo)
        try:
            _arrancar(ejecutable_viejo)
        except Exception:
            pass
        return False
    logger.info("respaldo listo con: %s", ", ".join(movidas) or "nada previo")

    # Paso e: copia lo nuevo. Cada tema de `sounds/themes` del paquete
    # reemplaza al instalado; el resto de `sounds` solo suma lo que falta.
    copiadas: list[str] = []
    temas_copiados: list[str] = []
    sonidos_agregados: list[str] = []
    # Vuelta atrás completa para todo fallo posterior al paso d: borra
    # lo copiado, devuelve el respaldo, borra el pendiente y lanza lo viejo.
    def _volver_atras() -> None:
        for nombre in copiadas:
            try:
                _borrar_entrada(instalacion / nombre)
            except OSError:
                pass
        for tema in temas_copiados:
            try:
                _borrar_entrada(instalacion / "sounds" / "themes" / tema)
            except OSError:
                pass
        _borrar_sonidos_agregados(instalacion, sonidos_agregados)
        _devolver_respaldo(respaldo, instalacion)
        try:
            pendiente.unlink()
        except OSError:
            pass
        try:
            _arrancar(ejecutable_viejo)
        except Exception:
            pass
    try:
        for hijo in sorted(paquete.iterdir()):
            if hijo.name == "sounds":
                continue
            destino = instalacion / hijo.name
            _borrar_entrada(destino)
            _copiar_entrada(hijo, destino)
            copiadas.append(hijo.name)
        origen_sonidos = paquete / "sounds"
        if origen_sonidos.is_dir():
            carpeta_sonidos = instalacion / "sounds"
            carpeta_sonidos.mkdir(parents=True, exist_ok=True)
            origen_temas = origen_sonidos / "themes"
            if origen_temas.is_dir():
                for hijo in sorted(origen_temas.iterdir()):
                    if hijo.is_dir() and not hijo.is_symlink():
                        destino_tema = carpeta_sonidos / "themes" / hijo.name
                        _borrar_entrada(destino_tema)
                        _copiar_entrada(hijo, destino_tema)
                        temas_copiados.append(hijo.name)
                    else:
                        _agregar_sonido_faltante(
                            hijo, carpeta_sonidos / "themes" / hijo.name,
                            carpeta_sonidos, sonidos_agregados)
            for hijo in sorted(origen_sonidos.iterdir()):
                if hijo.name == "themes":
                    continue
                _agregar_sonido_faltante(hijo, carpeta_sonidos / hijo.name,
                                         carpeta_sonidos, sonidos_agregados)
    except OSError as error:
        logger.error("no se pudo copiar el paquete: %s", error)
        motivo = "no se pudo copiar la versión nueva"
        _fallo(motivo)
        _volver_atras()
        return False
    logger.info("copia lista: %s", ", ".join(copiadas) or "nada")

    # Paso f: marca pendiente, lanza lo nuevo y espera la confirmación.
    try:
        pendiente.parent.mkdir(parents=True, exist_ok=True)
        pendiente.write_text(json.dumps(
            {"desde": desde, "hacia": hacia}, ensure_ascii=False),
            encoding="utf-8")
        try:
            arranque.unlink()
        except OSError:
            pass
    except OSError as error:
        motivo = f"no se pudo marcar la actualización pendiente: {error}"
        _fallo(motivo)
        _volver_atras()
        return False
    proceso_nuevo = None
    try:
        proceso_nuevo = _arrancar(ejecutable_nuevo)
    except Exception as error:
        motivo = f"la versión nueva no se pudo abrir: {error}"
        _fallo(motivo)
        _volver_atras()
        return False
    logger.info("versión nueva lanzada, espera confirmación")
    inicio = time.monotonic()
    confirmado = False
    while time.monotonic() - inicio < tope_arranque:
        if arranque.is_file():
            confirmado = True
            break
        time.sleep(INTERVALO_ARRANQUE)

    # Paso g: confirmó, se escribe el resultado antes de limpiar.
    if confirmado:
        logger.info("versión %s confirmada", hacia)
        try:
            resultado.parent.mkdir(parents=True, exist_ok=True)
            resultado.write_text(json.dumps(
                {"resultado": "ok", "desde": desde, "hacia": hacia},
                ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        try:
            if respaldo.exists():
                shutil.rmtree(respaldo)
        except OSError:
            pass
        try:
            pendiente.unlink()
        except OSError:
            pass
        return True

    # Paso h: no confirmó, se escribe el fallo antes de volver atrás.
    logger.error("la versión nueva no llegó a abrirse")
    try:
        matar(proceso_nuevo)
    except Exception:
        pass
    motivo = "la versión nueva no llegó a abrirse"
    _fallo(motivo)
    _volver_atras()
    return False


def _borrar_sonidos_agregados(instalacion: Path, nombres: list[str]) -> None:
    for nombre in nombres:
        try:
            _borrar_entrada(instalacion / "sounds" / nombre)
        except OSError:
            pass


def _devolver_respaldo(respaldo: Path, instalacion: Path) -> None:
    # Los temas van en `respaldo/sounds/themes/<tema>` para no chocar con
    # las entradas de primer nivel, y vuelven a `sounds/themes/<tema>`.
    try:
        temas = (sorted((respaldo / "sounds" / "themes").iterdir())
                 if (respaldo / "sounds" / "themes").is_dir() else [])
    except OSError:
        temas = []
    for entrada in temas:
        try:
            destino = instalacion / "sounds" / "themes" / entrada.name
            _borrar_entrada(destino)
            destino.parent.mkdir(parents=True, exist_ok=True)
            os.replace(entrada, destino)
        except OSError:
            logger.error("no se pudo devolver el tema %s", entrada.name)
    try:
        carpeta_temas = respaldo / "sounds" / "themes"
        if carpeta_temas.is_dir() and not any(carpeta_temas.iterdir()):
            carpeta_temas.rmdir()
        carpeta_sonidos = respaldo / "sounds"
        if carpeta_sonidos.is_dir() and not any(carpeta_sonidos.iterdir()):
            carpeta_sonidos.rmdir()
    except OSError:
        pass
    try:
        entradas = sorted(respaldo.iterdir()) if respaldo.is_dir() else []
    except OSError:
        return
    for entrada in entradas:
        if entrada.name == "sounds":
            continue
        try:
            destino = instalacion / entrada.name
            _borrar_entrada(destino)
            os.replace(entrada, destino)
        except OSError:
            logger.error("no se pudo devolver %s", entrada.name)


def principal_instalador(argumentos: list[str] | None = None) -> int:
    """Interpreta los argumentos, arma las funciones reales y llama a `instalar`.

    Uso: `--instalar-actualizacion <instalacion> <pid> <ejecutable_viejo> <desde>`.
    Devuelve 0 si quedó la versión nueva, 1 si no.
    """
    if argumentos is None:
        argumentos = sys.argv[1:]
    if len(argumentos) < 5 or argumentos[0] != ARGUMENTO_INSTALADOR:
        return 1
    _nombre, instalacion, pid_texto, ejecutable_viejo, desde = argumentos[:5]
    try:
        pid = int(pid_texto)
    except (TypeError, ValueError):
        return 1
    instalacion_ruta = Path(instalacion)
    paquete = paths.carpeta_instalacion()
    try:
        ok = instalar(paquete, instalacion_ruta, pid, ejecutable_viejo, desde,
                      esperar_pid=esperar_pid, lanzar=lanzar,
                      matar=matar, orden_para=orden_para_exe)
    except Exception as error:
        try:
            logger.error("instalador: %s", error)
        except Exception:
            pass
        return 1
    return 0 if ok else 1
