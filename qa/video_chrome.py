"""Cómo se deja Chrome listo para la grabación y cómo se lo cierra.

Lee el perfil para que no pida restaurar, cierra las ventanas con WM_CLOSE,
abre about:blank fuera de la tarea y cierra la pestaña final con Ctrl+W,
siempre comprobando el primer plano antes de mandar una tecla.
"""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import time
from pathlib import Path

ESPERA_CORTA = 2.0


def _escritorio():
    from directo_real import _escritorio as escritorio
    return escritorio()


def _titulo_ventana(hwnd) -> str:
    buffer = ctypes.create_unicode_buffer(512)
    try:
        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, 512)
    except Exception:
        return ""
    return buffer.value


def traer_al_frente(ventana, paso: int) -> None:
    """Pone la ventana adelante y comprueba cuál quedó con el foco."""
    try:
        ventana.set_focus()
    except Exception as exc:
        raise RuntimeError(
            f"paso {paso}: no se pudo poner al frente "
            f"({type(exc).__name__}: {exc!r})") from exc
    time.sleep(0.3)
    try:
        propia = int(ventana.element_info.handle)
        adelante = ctypes.windll.user32.GetForegroundWindow()
    except Exception as exc:
        raise RuntimeError(
            f"paso {paso}: no se pudo comprobar el primer plano "
            f"({type(exc).__name__}: {exc!r})") from exc
    if adelante != propia:
        raise RuntimeError(
            f"paso {paso}: la ventana no quedó al frente, adelante está "
            f"«{_titulo_ventana(adelante)}»")


def _local_state_chrome():
    base = os.environ.get("LOCALAPPDATA", "")
    if not base:
        return None
    return Path(base) / "Google" / "Chrome" / "User Data" / "Local State"


def perfil_de_chrome(local_state=None):
    ruta = Path(local_state) if local_state else _local_state_chrome()
    if ruta is None:
        return None
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:
        datos = {}
    nombre = (datos.get("profile") or {}).get("last_used") or "Default"
    return ruta.parent / nombre


def corregir_perfil(local_state=None) -> bool:
    """Marca el perfil como cerrado bien, para que no pida restaurar."""
    carpeta = perfil_de_chrome(local_state)
    if carpeta is None:
        return False
    prefs = carpeta / "Preferences"
    try:
        datos = json.loads(prefs.read_text(encoding="utf-8"))
    except Exception:
        return False
    datos.setdefault("profile", {})
    datos["profile"]["exit_type"] = "Normal"
    datos["profile"]["exited_cleanly"] = True
    try:
        prefs.write_text(json.dumps(datos, ensure_ascii=False),
                         encoding="utf-8")
        return True
    except Exception:
        return False


def _hay_chrome() -> bool:
    try:
        salida = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chrome.exe"],
            capture_output=True, text=True, timeout=15)
        return "chrome.exe" in (salida.stdout or "").lower()
    except Exception:
        return False


def _cerrar_ventanas() -> None:
    try:
        for ventana in _escritorio().windows():
            try:
                if "chrome" in (ventana.window_text() or "").lower():
                    ventana.close()
            except Exception:
                pass
    except Exception:
        pass


def preparar_chrome(segundos: int = 60):
    """Cierra Chrome, corrige el perfil y lo abre fuera de la tarea."""
    _cerrar_ventanas()
    fin = time.time() + 20
    while _hay_chrome() and time.time() < fin:
        time.sleep(0.5)
    if _hay_chrome():
        raise RuntimeError("Chrome no terminó de cerrarse en 20 s")
    corregir_perfil()
    try:
        subprocess.Popen(["explorer.exe", "https://www.google.com/"])
    except Exception as exc:
        raise RuntimeError(
            f"no se pudo abrir Chrome: {type(exc).__name__}: {exc!r}") from exc
    return ventana_de_google(segundos)


def ventana_de_google(segundos: int = 30):
    """Ventana de Chrome que tiene abierta la página de Google."""
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            for ventana in _escritorio().windows():
                try:
                    rotulo = (ventana.window_text() or "").lower()
                except Exception:
                    continue
                if rotulo.rstrip().endswith("google chrome"):
                    return ventana
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("no apareció la ventana de Chrome")


def titulo_chrome(chrome) -> str:
    try:
        titulo = (chrome.window_text() or "").strip()
    except Exception:
        return "sin Chrome"
    return titulo or "sin Chrome"


def titulo_pestana(chrome) -> str:
    try:
        for pestania in chrome.descendants(control_type="TabItem"):
            if pestania.is_selected():
                return pestania.window_text() or titulo_chrome(chrome)
    except Exception:
        pass
    return titulo_chrome(chrome)


def cerrar_pestana(chrome, paso: int = 3) -> None:
    """Cierra la pestaña de la página de éxito, sin tocar el proceso."""
    print(f"[consentimiento] Cerrando pestaña: {titulo_pestana(chrome)}")
    traer_al_frente(chrome, paso)
    chrome.type_keys("^w")
