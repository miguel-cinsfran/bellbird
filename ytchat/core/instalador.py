"""Instalador que reemplaza la aplicación con respaldo y vuelta atrás.

Corre DENTRO del exe nuevo, extraído en `data/actualizacion/nueva/...`,
mientras la app vieja se cierra. No importa wx, no crea ventanas, no
anuncia nada y no toca el mutex de instancia única.

Cada paso se anota con fecha en `registro.log`, con `logging` propio
del módulo hacia ese archivo.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ytchat.core import actualizacion
from ytchat.core import espera_proceso
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


def _huella_sha256(ruta: Path) -> str | None:
    """SHA-256 en minúsculas del archivo, o None si no se puede leer."""
    try:
        resumen = hashlib.sha256()
        with open(ruta, "rb") as abierto:
            while True:
                bloque = abierto.read(65536)
                if not bloque:
                    break
                resumen.update(bloque)
        return resumen.hexdigest().lower()
    except OSError:
        return None


def _leer_manifiesto_sonidos(instalacion: Path) -> dict | None:
    """Manifiesto viejo de sonidos, o None si no hay o no se entiende."""
    try:
        datos = json.loads(
            (instalacion / paths.NOMBRE_MANIFIESTO_SONIDOS).read_text(
                encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(datos, dict):
        return None
    return {clave: str(valor).lower() for clave, valor in datos.items()
            if isinstance(clave, str) and isinstance(valor, str)}


def _es_del_usuario(ruta_respaldo: Path, relativa: str, par_nuevo: Path,
                    manifiesto_viejo: dict | None) -> bool:
    """Dice si el sonido del respaldo lo cambió o agregó el usuario.

    `relativa` es la ruta con `/` como separador, relativa a `sounds/`.
    Con manifiesto viejo, es del usuario si no figura con exactamente
    esa huella. Sin manifiesto no hay forma de distinguir: ante la duda
    es del usuario, salvo que sea byte a byte igual al nuevo.
    """
    if manifiesto_viejo is not None:
        huella_vieja = manifiesto_viejo.get(relativa)
        if huella_vieja is None:
            return True
        return _huella_sha256(ruta_respaldo) != huella_vieja
    if not par_nuevo.is_file() or par_nuevo.is_symlink():
        return True
    return _huella_sha256(ruta_respaldo) != _huella_sha256(par_nuevo)


def _devolver_sonidos_usuario(respaldo: Path, instalacion: Path, tema: str,
                              manifiesto_viejo: dict | None) -> None:
    """Copia de vuelta al tema nuevo los sonidos del usuario del respaldo.

    Pasa después de copiar el tema nuevo: cada archivo del usuario pisa
    al del paquete si tiene el mismo nombre. El respaldo queda intacto,
    así que la vuelta atrás sigue devolviendo la carpeta vieja entera.
    """
    base_respaldo = respaldo / "sounds"
    origen_tema = base_respaldo / "themes" / tema
    if not origen_tema.is_dir():
        return
    try:
        archivos = sorted(origen_tema.rglob("*"))
    except OSError:
        return
    for origen in archivos:
        if origen.is_dir() or origen.is_symlink():
            continue
        try:
            relativa = origen.relative_to(base_respaldo).as_posix()
            destino = (instalacion / "sounds" / "themes" / tema
                       / origen.relative_to(origen_tema))
        except ValueError:
            continue
        if not _es_del_usuario(origen, relativa, destino, manifiesto_viejo):
            continue
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origen, destino)
        except OSError as error:
            logger.error("no se pudo conservar el sonido %s: %s",
                         relativa, error)
            continue
        logger.info("sonido del usuario conservado: %s", relativa)


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


@dataclass
class _Progreso:
    """Lo movido y copiado hasta ahora, para deshacerlo al volver atrás."""
    movidas: list[str] = field(default_factory=list)
    temas_movidos: list[str] = field(default_factory=list)
    copiadas: list[str] = field(default_factory=list)
    temas_copiados: list[str] = field(default_factory=list)
    sonidos_agregados: list[str] = field(default_factory=list)


def _fallar(resultado: Path, motivo: str,
            con_resultado: bool = True) -> bool:
    logger.error("fallo: %s", motivo)
    if con_resultado:
        try:
            resultado.parent.mkdir(parents=True, exist_ok=True)
            resultado.write_text(json.dumps(
                {"resultado": "fallo", "motivo": motivo},
                ensure_ascii=False), encoding="utf-8")
        except OSError as error:
            logger.warning("no se pudo escribir el resultado en %s: %s", resultado, error)
    return False


def _arrancar_en(instalacion: Path, nombre_exe: str, lanzar,
                 orden_para):
    return lanzar(orden_para(str(instalacion / nombre_exe)))


def _relanzar_viejo(instalacion: Path, ejecutable_viejo: str, lanzar,
                    orden_para) -> None:
    try:
        _arrancar_en(instalacion, ejecutable_viejo, lanzar, orden_para)
    except Exception as error:
        logger.warning("no se pudo relanzar %s: %s", ejecutable_viejo, error)


def _esperar_cierre(esperar_pid, pid: int, tope_cierre: float) -> bool:
    logger.info("instalador: espera al pid %s", pid)
    if not esperar_pid(pid, tope_cierre):
        logger.error("la aplicación no se cerró a tiempo")
        return False
    logger.info("la aplicación se cerró")
    return True


def _validar_paquete(paquete: Path) -> tuple:
    contenido = json.loads(
        (paquete / paths.NOMBRE_MANIFIESTO).read_text(encoding="utf-8"))
    hacia = contenido.get("version") if isinstance(contenido, dict) else None
    ejecutable_nuevo = actualizacion.validar_paquete(paquete, hacia)
    logger.info("paquete válido hacia la versión %s", hacia)
    return hacia, ejecutable_nuevo


def _manifiesto_viejo(instalacion: Path) -> dict | None:
    # Se lee antes de mover nada, porque `sonidos.json` es una entrada
    # de primer nivel y se reemplaza.
    manifiesto = _leer_manifiesto_sonidos(instalacion)
    if manifiesto is None:
        logger.info("sin manifiesto viejo de sonidos: "
                    "ante la duda se conserva lo del usuario")
    return manifiesto


def _vaciar_respaldo(respaldo: Path) -> str | None:
    try:
        if respaldo.exists():
            shutil.rmtree(respaldo)
    except OSError as error:
        return f"no se pudo vaciar el respaldo: {error}"
    return None


def _deshacer_movidas(instalacion: Path, respaldo: Path,
                      progreso: _Progreso) -> None:
    for tema in reversed(progreso.temas_movidos):
        try:
            destino_tema = instalacion / "sounds" / "themes" / tema
            destino_tema.parent.mkdir(parents=True, exist_ok=True)
            os.replace(respaldo / "sounds" / "themes" / tema, destino_tema)
        except OSError as error:
            logger.warning("no se pudo devolver el tema %s: %s", tema, error)
    for nombre in reversed(progreso.movidas):
        try:
            os.replace(respaldo / nombre, instalacion / nombre)
        except OSError as error:
            logger.warning("no se pudo devolver %s: %s", nombre, error)


def _mover_al_respaldo(instalacion: Path, respaldo: Path,
                       entradas: list[str], temas: list[str],
                       progreso: _Progreso) -> None:
    try:
        respaldo.mkdir(parents=True, exist_ok=True)
        for nombre in entradas:
            origen = instalacion / nombre
            if not origen.exists() and not origen.is_symlink():
                continue
            os.replace(origen, respaldo / nombre)
            progreso.movidas.append(nombre)
        for tema in temas:
            origen_tema = instalacion / "sounds" / "themes" / tema
            if not origen_tema.exists() and not origen_tema.is_symlink():
                continue
            destino_tema = respaldo / "sounds" / "themes" / tema
            destino_tema.parent.mkdir(parents=True, exist_ok=True)
            os.replace(origen_tema, destino_tema)
            progreso.temas_movidos.append(tema)
    except OSError as error:
        logger.error("no se pudo mover %s al respaldo: %s",
                     instalacion / nombre, error)
        _deshacer_movidas(instalacion, respaldo, progreso)
        raise


def _copiar_raiz(paquete: Path, instalacion: Path,
                 progreso: _Progreso) -> None:
    for hijo in sorted(paquete.iterdir()):
        if hijo.name == "sounds":
            continue
        destino = instalacion / hijo.name
        _borrar_entrada(destino)
        _copiar_entrada(hijo, destino)
        progreso.copiadas.append(hijo.name)


def _copiar_sonidos(paquete: Path, instalacion: Path, respaldo: Path,
                    manifiesto_viejo: dict | None,
                    progreso: _Progreso) -> None:
    # Cada tema de `sounds/themes` del paquete reemplaza al instalado;
    # el resto de `sounds` solo suma lo que falta.
    origen_sonidos = paquete / "sounds"
    if not origen_sonidos.is_dir():
        return
    carpeta_sonidos = instalacion / "sounds"
    carpeta_sonidos.mkdir(parents=True, exist_ok=True)
    origen_temas = origen_sonidos / "themes"
    if origen_temas.is_dir():
        for hijo in sorted(origen_temas.iterdir()):
            if hijo.is_dir() and not hijo.is_symlink():
                destino_tema = carpeta_sonidos / "themes" / hijo.name
                _borrar_entrada(destino_tema)
                _copiar_entrada(hijo, destino_tema)
                progreso.temas_copiados.append(hijo.name)
                _devolver_sonidos_usuario(respaldo, instalacion, hijo.name,
                                          manifiesto_viejo)
            else:
                _agregar_sonido_faltante(
                    hijo, carpeta_sonidos / "themes" / hijo.name,
                    carpeta_sonidos, progreso.sonidos_agregados)
    for hijo in sorted(origen_sonidos.iterdir()):
        if hijo.name == "themes":
            continue
        _agregar_sonido_faltante(hijo, carpeta_sonidos / hijo.name,
                                 carpeta_sonidos, progreso.sonidos_agregados)


def _copiar_paquete(paquete: Path, instalacion: Path, respaldo: Path,
                    manifiesto_viejo: dict | None,
                    progreso: _Progreso) -> None:
    _copiar_raiz(paquete, instalacion, progreso)
    _copiar_sonidos(paquete, instalacion, respaldo, manifiesto_viejo,
                    progreso)


def _marcar_pendiente(pendiente: Path, arranque: Path, desde: str,
                      hacia: str) -> None:
    pendiente.parent.mkdir(parents=True, exist_ok=True)
    pendiente.write_text(json.dumps(
        {"desde": desde, "hacia": hacia}, ensure_ascii=False),
        encoding="utf-8")
    try:
        arranque.unlink()
    except OSError as error:
        logger.warning("no se pudo borrar el arranque anterior %s: %s", arranque, error)


def _volver_atras(progreso: _Progreso, instalacion: Path, respaldo: Path,
                  pendiente: Path, ejecutable_viejo: str, lanzar,
                  orden_para) -> None:
    # Vuelta atrás completa para todo fallo posterior al respaldo: borra
    # lo copiado, devuelve el respaldo, borra el pendiente y lanza lo viejo.
    for nombre in progreso.copiadas:
        try:
            _borrar_entrada(instalacion / nombre)
        except OSError as error:
            logger.warning("no se pudo borrar %s: %s", instalacion / nombre, error)
    for tema in progreso.temas_copiados:
        try:
            _borrar_entrada(instalacion / "sounds" / "themes" / tema)
        except OSError as error:
            logger.warning("no se pudo borrar el tema %s: %s", tema, error)
    _borrar_sonidos_agregados(instalacion, progreso.sonidos_agregados)
    _devolver_respaldo(respaldo, instalacion)
    try:
        pendiente.unlink()
    except OSError as error:
        logger.warning("no se pudo borrar el pendiente %s: %s", pendiente, error)
    _relanzar_viejo(instalacion, ejecutable_viejo, lanzar, orden_para)


def _esperar_confirmacion(arranque: Path, tope_arranque: float) -> bool:
    inicio = time.monotonic()
    while time.monotonic() - inicio < tope_arranque:
        if arranque.is_file():
            return True
        time.sleep(INTERVALO_ARRANQUE)
    return False


def _cerrar_exito(respaldo: Path, pendiente: Path, resultado: Path,
                  desde: str, hacia: str) -> None:
    logger.info("versión %s confirmada", hacia)
    try:
        resultado.parent.mkdir(parents=True, exist_ok=True)
        resultado.write_text(json.dumps(
            {"resultado": "ok", "desde": desde, "hacia": hacia},
            ensure_ascii=False), encoding="utf-8")
    except OSError as error:
        logger.warning("no se pudo escribir el resultado en %s: %s", resultado, error)
    try:
        if respaldo.exists():
            shutil.rmtree(respaldo)
    except OSError as error:
        logger.debug("no se pudo borrar el respaldo %s: %s", respaldo, error)
    try:
        pendiente.unlink()
    except OSError as error:
        logger.warning("no se pudo borrar el pendiente %s: %s", pendiente, error)


def _lanzar_y_cerrar(instalacion: Path, ejecutable_nuevo: str,
                     ejecutable_viejo: str, pendiente: Path, arranque: Path,
                     respaldo: Path, resultado: Path, desde: str,
                     hacia: str, lanzar, matar, orden_para,
                     tope_arranque: float, progreso: _Progreso) -> bool:
    try:
        proceso_nuevo = _arrancar_en(instalacion, ejecutable_nuevo, lanzar,
                                     orden_para)
    except Exception as error:
        _fallar(resultado, f"la versión nueva no se pudo abrir: {error}")
        _volver_atras(progreso, instalacion, respaldo, pendiente,
                      ejecutable_viejo, lanzar, orden_para)
        return False
    logger.info("versión nueva lanzada, espera confirmación")
    if _esperar_confirmacion(arranque, tope_arranque):
        _cerrar_exito(respaldo, pendiente, resultado, desde, hacia)
        return True
    logger.error("la versión nueva no llegó a abrirse")
    try:
        matar(proceso_nuevo)
    except Exception:
        pass
    _fallar(resultado, "la versión nueva no llegó a abrirse")
    _volver_atras(progreso, instalacion, respaldo, pendiente,
                  ejecutable_viejo, lanzar, orden_para)
    return False


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
    paquete, instalacion = Path(paquete), Path(instalacion)
    _preparar_registro(instalacion)
    respaldo = paths.respaldo_actualizacion_en(instalacion)
    pendiente = paths.actualizacion_pendiente_en(instalacion)
    arranque = paths.arranque_confirmado_en(instalacion)
    resultado = paths.resultado_actualizacion_en(instalacion)
    progreso = _Progreso()
    if not _esperar_cierre(esperar_pid, pid, tope_cierre):
        return False
    try:
        hacia, ejecutable_nuevo = _validar_paquete(paquete)
    except (actualizacion.PaqueteInvalido, OSError, ValueError) as error:
        return _fallar(resultado, f"el paquete no es válido: {error}")
    entradas = _entradas_a_reemplazar(paquete, ejecutable_viejo)
    logger.info("entradas a reemplazar: %s", ", ".join(entradas) or "ninguna")
    manifiesto_viejo = _manifiesto_viejo(instalacion)
    if (motivo := _vaciar_respaldo(respaldo)) is not None:
        return _fallar(resultado, motivo)
    try:
        _mover_al_respaldo(instalacion, respaldo, entradas,
                           _temas_del_paquete(paquete), progreso)
    except OSError:
        _fallar(resultado,
                "no se pudo mover un archivo de la versión anterior, "
                "quizá sigue abierto en otro programa, como OBS. "
                "Ciérralo y vuelve a intentarlo")
        _relanzar_viejo(instalacion, ejecutable_viejo, lanzar, orden_para)
        return False
    logger.info("respaldo listo con: %s", ", ".join(progreso.movidas) or "nada previo")
    try:
        _copiar_paquete(paquete, instalacion, respaldo, manifiesto_viejo,
                        progreso)
    except OSError as error:
        logger.error("no se pudo copiar el paquete: %s", error)
        _fallar(resultado, "no se pudo copiar la versión nueva")
        _volver_atras(progreso, instalacion, respaldo, pendiente,
                      ejecutable_viejo, lanzar, orden_para)
        return False
    logger.info("copia lista: %s", ", ".join(progreso.copiadas) or "nada")
    try:
        _marcar_pendiente(pendiente, arranque, desde, hacia)
    except OSError as error:
        _fallar(resultado,
                f"no se pudo marcar la actualización pendiente: {error}")
        _volver_atras(progreso, instalacion, respaldo, pendiente,
                      ejecutable_viejo, lanzar, orden_para)
        return False
    return _lanzar_y_cerrar(
        instalacion, ejecutable_nuevo, ejecutable_viejo, pendiente, arranque,
        respaldo, resultado, desde, hacia, lanzar, matar, orden_para,
        tope_arranque, progreso)


def _borrar_sonidos_agregados(instalacion: Path, nombres: list[str]) -> None:
    for nombre in nombres:
        try:
            _borrar_entrada(instalacion / "sounds" / nombre)
        except OSError as error:
            logger.debug("no se pudo borrar el sonido agregado %s: %s", nombre, error)


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
                      esperar_pid=espera_proceso.esperar_pid, lanzar=lanzar,
                      matar=matar, orden_para=orden_para_exe)
    except Exception as error:
        try:
            logger.error("instalador: %s", error)
        except Exception:
            pass
        return 1
    return 0 if ok else 1
