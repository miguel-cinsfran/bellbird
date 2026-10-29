#!/usr/bin/env python
"""Smoke test y verificación de accesibilidad de YTChat TTS.

Pensado para correrlo en Windows (donde está wxPython y el árbol de
accesibilidad). Tres fases, cada una se ejecuta solo si el entorno la permite:

  Fase 1  (cualquier SO):   importa los módulos de lógica pura.
  Fase 2  (necesita wx):    importa los módulos de GUI. Esto EJECUTA el código
                            a nivel de módulo y caza NameError, imports
                            circulares y atributos inexistentes que la simple
                            compilación (py_compile) no detecta.
  Fase 3  (Windows + pywinauto): lanza la aplicación, recorre el árbol de
                            accesibilidad (UI Automation, el mismo que lee
                            NVDA) y avisa de los controles interactivos sin
                            nombre accesible. Después cierra la app.

Uso:
    python scripts/smoke_test.py            # todas las fases disponibles
    python scripts/smoke_test.py --no-gui   # solo fases 1 y 2 (no abre la ventana)

Para la fase 3 hace falta:  pip install pywinauto
"""

from __future__ import annotations

import csv
import importlib
import os
import re
import subprocess
import sys

# Raíz del repositorio: la carpeta padre de scripts/.
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, RAIZ)

from bellbird.core.config import APP_NAME  # noqa: E402

# Tipos de control que deben tener SIEMPRE un nombre accesible (lo que NVDA
# anuncia al llegar a ellos con Tab). Si alguno aparece sin nombre, es un fallo
# de accesibilidad.
_INTERACTIVOS = {"Button", "Edit", "ComboBox", "List", "CheckBox", "RadioButton"}

# Qué cubre en realidad la fase 3, para que un «OK» no se lea como «todos los
# controles tienen nombre»: solo recorre la pantalla sin conectar. El resto de
# las superficies las audita el banco de QA.
ALCANCE_FASE3 = (
    "Solo la pantalla sin conectar: URL, Conectar, menús y barra de estado. "
    "La lista del chat, las pestañas, el cuadro de escritura y el reproductor "
    "los audita el banco de QA (qa/conducir.py).")


def _modulos_de_la_raiz() -> tuple[list[str], list[str]]:
    """(módulos puros, módulos de GUI) descubiertos en el paquete `bellbird`.

    Antes era una lista a mano y se quedaba corta: cada módulo nuevo
    (relevo_ffmpeg, obs_*, overlay_*, programados…) se quedaba fuera del
    smoke sin que nadie lo notara. Es de GUI si importa wx a nivel de módulo;
    los que lo importan dentro de una función siguen siendo puros. Los nombres
    son completos (`bellbird.core.config`), para que cada módulo se importe una
    sola vez y no haya dos copias en memoria.
    """
    puros, gui = [], []
    paquete = os.path.join(RAIZ, "bellbird")
    for dirpath, _dirnames, nombres in os.walk(paquete):
        for nombre in sorted(nombres):
            if not nombre.endswith(".py") or nombre == "__init__.py":
                continue
            ruta = os.path.join(dirpath, nombre)
            with open(ruta, encoding="utf-8", errors="replace") as f:
                fuente = f.read()
            modulo = os.path.relpath(ruta, RAIZ)[:-3].replace(os.sep, ".")
            if re.search(r"^(?:import wx\b|from wx\b)", fuente, re.M):
                gui.append(modulo)
            else:
                puros.append(modulo)
    return puros, gui


# Piso: si mañana alguien mueve las carpetas otra vez, el descubrimiento
# vuelve vacío y el smoke quedaría en verde sin comprobar nada. Menos de 50
# módulos es que mira para otro lado, y tiene que decirlo.
_MINIMO_MODULOS = 50

# Piso de controles de la pantalla principal desconectada, que en la última
# corrida buena dio 31. Menos de 20 es que se recorrió otra ventana, como el
# aviso de instancia única (6 controles).
_MINIMO_CONTROLES = 20


_MODULOS_PUROS, _MODULOS_GUI = _modulos_de_la_raiz()

_PREFIJO_TITULO = APP_NAME
_PROCESOS_APLICACION = {"python.exe", "pythonw.exe", "bellbird.exe"}

# El nombre se duplica a propósito: importar main.py arrastra wx y medio
# paquete. Una prueba vigila que coincida con el de main.py.
_MUTEX_INSTANCIA = "YTChatTTS_SingleInstance_Mutex"
_SYNCHRONIZE = 0x00100000
_ERROR_ACCESS_DENIED = 5

_MENSAJE_INSTANCIA_ABIERTA = (
    "Ya hay una YTChat abierta en esta sesión, quizá en otro escritorio. "
    "Ciérrala y vuelve a correr el smoke: la fase 3 no audita ni cierra una "
    "aplicación que no abrió ella.")

# Plazo de espera de la ventana en la fase 3: la aplicación puede tardar en
# arrancar (imports de wx, libVLC), y un plazo corto daba falsos negativos.
_PLAZO_VENTANA = 40

# Tope al subir por el mapa de padres: un ciclo no puede colgar la fase 3.
_TOPE_PROFUNDIDAD = 256


def ventana_es_de_la_aplicacion(titulo: str, nombre_proceso: str) -> bool:
    """Indica si título y proceso identifican la ventana de la aplicación."""
    return (titulo.startswith(_PREFIJO_TITULO)
            and nombre_proceso.lower() in _PROCESOS_APLICACION)


def hay_otra_instancia_abierta(nombre: str = _MUTEX_INSTANCIA) -> bool:
    """Indica si el mutex de instancia única ya está tomado en la sesión.

    El mutex vale para toda la sesión, así que también detecta una YTChat
    abierta en otro escritorio, donde el recorrido de ventanas no llega.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenMutexW.restype = ctypes.c_void_p
        kernel32.OpenMutexW.argtypes = [ctypes.c_uint32, ctypes.c_int,
                                        ctypes.c_wchar_p]
        handle = kernel32.OpenMutexW(_SYNCHRONIZE, False, nombre)
        if handle:
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel32.CloseHandle(ctypes.c_void_p(handle))
            return True
        return ctypes.get_last_error() == _ERROR_ACCESS_DENIED
    except Exception:
        return False


def es_descendiente(pid: int, raiz: int, padres: dict[int, int]) -> bool:
    """Indica si pid es raiz o desciende de ella según el mapa de padres.

    El mapa es pid -> ppid, una foto de los procesos en un instante. Sube
    por los padres con tope de profundidad, así un ciclo en el mapa devuelve
    False en vez de colgarse.
    """
    if pid == raiz:
        return True
    vistos = set()
    actual = pid
    for _ in range(_TOPE_PROFUNDIDAD):
        if actual in vistos:
            return False
        vistos.add(actual)
        padre = padres.get(actual)
        if padre is None:
            return False
        if padre == raiz:
            return True
        actual = padre
    return False


def mensaje_fallo_ventana(proceso_vivo: bool, ventanas_ajenas: list,
                          plazo: int = _PLAZO_VENTANA) -> str:
    """Elige el mensaje de fallo de la fase 3 cuando no hubo ventana propia.

    Distingue si la aplicación lanzada ya terminó de si sigue arrancando, y
    anota las ventanas ajenas con el mismo título que se ignoraron por no
    ser del árbol lanzado.
    """
    if proceso_vivo:
        base = (f"la ventana no apareció en {plazo} s y la aplicación "
                "sigue arrancando")
    else:
        base = "la aplicación terminó sin abrir la ventana"
    if ventanas_ajenas:
        detalle = ", ".join(str(v) for v in ventanas_ajenas)
        if len(ventanas_ajenas) == 1:
            base += f"; se ignoró 1 ventana ajena con ese título ({detalle})"
        else:
            base += (f"; se ignoraron {len(ventanas_ajenas)} ventanas ajenas "
                     f"con ese título ({detalle})")
    return base


def mapa_padres_procesos() -> dict[int, int]:
    """Foto de los procesos como mapa pid -> ppid, en Windows.

    Se usa para saber si una ventana es del árbol que lanzó la fase 3 y si
    ese árbol sigue vivo. Si la foto falla, devuelve un mapa vacío y quien
    llama supone que el árbol sigue vivo, para no dar por muerta una
    aplicación que sigue arrancando.
    """
    if sys.platform != "win32":
        return {}
    try:
        import ctypes
        from ctypes import wintypes

        class _EntradaProceso(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        foto = kernel32.CreateToolhelp32Snapshot(0x2, 0)
        if foto == wintypes.HANDLE(-1).value:
            return {}
        try:
            entrada = _EntradaProceso()
            entrada.dwSize = ctypes.sizeof(_EntradaProceso)
            kernel32.Process32FirstW.argtypes = [wintypes.HANDLE,
                                                 ctypes.POINTER(_EntradaProceso)]
            kernel32.Process32FirstW.restype = wintypes.BOOL
            kernel32.Process32NextW.argtypes = [wintypes.HANDLE,
                                                ctypes.POINTER(_EntradaProceso)]
            kernel32.Process32NextW.restype = wintypes.BOOL
            mapa: dict[int, int] = {}
            if not kernel32.Process32FirstW(foto, ctypes.byref(entrada)):
                return {}
            while True:
                mapa[int(entrada.th32ProcessID)] = int(
                    entrada.th32ParentProcessID)
                if not kernel32.Process32NextW(foto, ctypes.byref(entrada)):
                    break
            return mapa
        finally:
            kernel32.CloseHandle(foto)
    except Exception:
        return {}


def arbol_sigue_vivo(raiz: int | None, padres: dict[int, int]) -> bool:
    """Indica si raiz o algún descendiente suyo sigue en la foto de procesos.

    Sin foto (mapa vacío) o sin raiz conocida supone que sigue vivo: cortar
    la espera en ese caso daría por muerta una aplicación que sigue
    arrancando.
    """
    if raiz is None or not padres:
        return True
    if raiz in padres:
        return True
    return any(es_descendiente(pid, raiz, padres) for pid in padres)


def interactivos_sin_nombre(controles) -> list[str]:
    """Tipos de control interactivo que no tienen nombre accesible."""
    return [tipo for tipo, nombre in controles
            if tipo in _INTERACTIVOS and not nombre]


def mensaje_fallo_controles(total: int,
                            piso: int = _MINIMO_CONTROLES) -> str | None:
    """Devuelve el fallo si no se alcanzó el piso de controles."""
    if total >= piso:
        return None
    return (f"se recorrieron solo {total} controles (piso: {piso}): "
            "la ventana recorrida probablemente no es la pantalla principal")


def _nombre_proceso(pid: int) -> str:
    """Devuelve el nombre de imagen del proceso indicado en Windows."""
    resultado = subprocess.run(
        ["tasklist", "/fi", f"PID eq {pid}", "/fo", "csv", "/nh"],
        capture_output=True, text=True, encoding="mbcs", errors="replace",
        check=False)
    filas = list(csv.reader(resultado.stdout.splitlines()))
    return filas[0][0] if filas and filas[0] else ""


def _titulo(texto):
    print("\n" + "=" * 60)
    print("  " + texto)
    print("=" * 60)


def fase1_logica() -> bool:
    _titulo("FASE 1 — Importar lógica pura (cualquier SO)")
    total = len(_MODULOS_PUROS) + len(_MODULOS_GUI)
    if total < _MINIMO_MODULOS:
        print(f"  [FALLO] se descubrieron solo {total} módulos en bellbird/ "
              f"(piso: {_MINIMO_MODULOS}): el descubrimiento mira para otro "
              "lado y el smoke quedaría en verde sin comprobar nada.")
        return False
    ok = True
    for nombre in _MODULOS_PUROS:
        try:
            importlib.import_module(nombre)
            print(f"  [ok]    import {nombre}")
        except Exception as exc:
            ok = False
            print(f"  [FALLO] import {nombre}: {exc.__class__.__name__}: {exc}")
    print(f"  Módulos puros importados: {len(_MODULOS_PUROS)} de {total}")
    return ok


def fase2_gui() -> bool:
    _titulo("FASE 2 — Importar módulos de GUI (necesita wxPython)")
    try:
        import wx  # noqa: F401
    except ImportError:
        print("  [saltada] wxPython no está instalado. En Windows:")
        print("            pip install -r requirements.txt")
        return True  # no es un fallo, solo no aplica en este entorno
    ok = True
    print(f"  wxPython {wx.version()}")
    for nombre in _MODULOS_GUI:
        try:
            importlib.import_module(nombre)
            print(f"  [ok]    import {nombre}")
        except Exception as exc:
            ok = False
            print(f"  [FALLO] import {nombre}: {exc.__class__.__name__}: {exc}")
    print(f"  Módulos de GUI importados: {len(_MODULOS_GUI)}")
    return ok


def _recorrer(win):
    """Devuelve lista de (tipo, nombre) de win y sus descendientes."""
    salida = []
    try:
        elementos = [win] + win.descendants()
    except Exception as exc:
        print(f"  No se pudo recorrer la ventana: {exc}")
        return salida
    for el in elementos:
        try:
            info = el.element_info
            salida.append((info.control_type or "?", (info.name or "").strip()))
        except Exception:
            pass
    return salida


def fase3_accesibilidad() -> bool:
    _titulo("FASE 3 — Árbol de accesibilidad (solo Windows + pywinauto)")
    if sys.platform != "win32":
        print("  [saltada] No es Windows; no hay árbol UI Automation que leer.")
        return True
    try:
        import time
        from pywinauto import Application, Desktop
    except ImportError:
        print("  [saltada] pywinauto no está instalado.  pip install pywinauto")
        return True

    main_py = os.path.join(RAIZ, "main.py")
    cmd = f'"{sys.executable}" "{main_py}"'
    # wait_for_idle=False: el ejecutable lanzado es python.exe (proceso de
    # consola que luego abre la ventana wx). pywinauto, por defecto, llama a
    # WaitForInputIdle sobre ese proceso y falla con el error 1471 ("no es un
    # proceso GUI").
    #
    # Además, NO buscamos la ventana por el PID que lanzamos: bajo `uv` el
    # python.exe del venv es un trampolín que reejecuta el intérprete base en un
    # proceso hijo, y es ese hijo quien crea la ventana. Por eso localizamos la
    # ventana por título en todo el escritorio, pero solo aceptamos la que sea
    # del árbol lanzado y al cerrar solo tocamos ese árbol: nunca se audita ni
    # se cierra una aplicación que no abrió esta fase.
    ventanas_ajenas = []

    def _buscar_ventana(raiz=None, padres=None):
        # Iteramos los top-level del escritorio y casamos por título. Es más
        # fiable con backend UIA que window(title_re=...).exists(), y nos da
        # directamente el wrapper sobre el que recorrer descendientes.
        # Con raiz conocida, las ventanas con ese título que no sean del árbol
        # lanzado se ignoran (quedan anotadas para el mensaje de fallo).
        try:
            for w in Desktop(backend="uia").windows():
                try:
                    titulo = w.window_text() or ""
                    if not titulo.startswith(_PREFIJO_TITULO):
                        continue
                    pid = w.element_info.process_id
                    nombre_proceso = _nombre_proceso(pid)
                    # El título no basta: una carpeta abierta puede llamarse igual.
                    if not ventana_es_de_la_aplicacion(titulo, nombre_proceso):
                        ventanas_ajenas.append(nombre_proceso or "desconocido")
                        continue
                    if (raiz is not None and padres is not None
                            and not es_descendiente(pid, raiz, padres)):
                        ventanas_ajenas.append(f"proceso {pid}")
                        continue
                    return w
                except Exception:
                    continue
        except Exception:
            pass
        return None

    # Si ya hay una ventana de la aplicación, es del dueño u otra corrida:
    # no se lanza nada, no se audita y no se cierra nada ajeno.
    previa = _buscar_ventana()
    if previa is not None:
        try:
            pid_previa = previa.element_info.process_id
        except Exception:
            pid_previa = "desconocido"
        print(f"  [FALLO] Ya hay una ventana de YTChat abierta (proceso "
              f"{pid_previa}). Ciérrala y vuelve a correr el smoke: la fase 3 "
              f"no audita ni cierra una aplicación que no abrió ella.")
        return False

    if hay_otra_instancia_abierta():
        print(f"  [FALLO] {_MENSAJE_INSTANCIA_ABIERTA}")
        return False

    print(f"  Lanzando: {cmd}")
    ventanas_ajenas.clear()
    app = Application(backend="uia").start(cmd, work_dir=RAIZ,
                                           wait_for_idle=False)
    raiz_pid = getattr(app, "process", None)
    win_pid = None
    try:
        # Sondeo manual hasta el plazo: la ventana puede tardar en aparecer.
        # Si el árbol lanzado ya terminó, se corta en el acto en vez de
        # esperar el plazo entero.
        win = None
        proceso_vivo = True
        limite = time.monotonic() + _PLAZO_VENTANA
        while time.monotonic() < limite:
            padres = mapa_padres_procesos()
            win = _buscar_ventana(raiz_pid, padres)
            if win is not None:
                break
            if not arbol_sigue_vivo(raiz_pid, padres):
                proceso_vivo = False
                break
            time.sleep(0.5)
        if win is None:
            raise TimeoutError(mensaje_fallo_ventana(proceso_vivo,
                                                     ventanas_ajenas))
        win_pid = win.element_info.process_id
        print("  Ventana visible. Recorriendo controles...\n")

        controles = _recorrer(win)
        for tipo, nombre in controles:
            etiqueta = nombre if nombre else "(SIN NOMBRE)"
            print(f"    {tipo:12s}  {etiqueta}")

        print(f"\n  Total de controles: {len(controles)}")
        fallo_controles = mensaje_fallo_controles(len(controles))
        if fallo_controles:
            print(f"  [FALLO] {fallo_controles}")
            return False
        sin_nombre = interactivos_sin_nombre(controles)
        if sin_nombre:
            print(f"  [AVISO ACCESIBILIDAD] {len(sin_nombre)} control(es) "
                  f"interactivo(s) SIN nombre: {', '.join(sin_nombre)}")
            return False
        print("  [ok] Todos los controles interactivos tienen nombre accesible.")
        print("  Alcance: " + ALCANCE_FASE3)
        return True
    except Exception as exc:
        print(f"  [FALLO] {exc.__class__.__name__}: {exc}")
        return False
    finally:
        cerrado = False
        # El proceso real de la ventana (hijo bajo uv) y el lanzado pueden ser
        # distintos, pero ambos son del árbol lanzado: solo se mata lo propio.
        # Una ventana ajena nunca llega a win_pid porque _buscar_ventana la
        # ignora, y acá se verifica de nuevo por si la foto cambió.
        if win_pid is not None:
            try:
                if (raiz_pid is None or win_pid == raiz_pid
                        or es_descendiente(win_pid, raiz_pid,
                                           mapa_padres_procesos())):
                    Application(backend="uia").connect(process=win_pid).kill()
                    cerrado = True
            except Exception:
                pass
        try:
            app.kill()
            cerrado = True
        except Exception:
            pass
        if cerrado:
            print("\n  Aplicación cerrada.")


def main():
    no_gui = "--no-gui" in sys.argv
    os.chdir(RAIZ)
    if RAIZ not in sys.path:
        sys.path.insert(0, RAIZ)

    r1 = fase1_logica()
    r2 = fase2_gui()
    r3 = True if no_gui else fase3_accesibilidad()

    _titulo("RESUMEN")
    print(f"  Fase 1 (lógica):        {'OK' if r1 else 'FALLO'}")
    print(f"  Fase 2 (GUI imports):   {'OK' if r2 else 'FALLO'}")
    if no_gui:
        print("  Fase 3 (accesibilidad): omitida (--no-gui)")
    elif r3:
        print("  Fase 3 (accesibilidad): OK, solo sin conectar")
    else:
        print("  Fase 3 (accesibilidad): FALLO / avisos")
    print()
    sys.exit(0 if (r1 and r2 and r3) else 1)


if __name__ == "__main__":
    main()
