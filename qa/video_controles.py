"""Cómo se encuentra, enfoca, escribe y lee un control de la app por UIA."""

from __future__ import annotations

import time


class FalloPaso(Exception):
    def __init__(self, paso: int, motivo: str):
        super().__init__(f"paso {paso}: {motivo}")
        self.paso = paso


def activar_menu(control) -> bool:
    """Los ítems de menú de wx se activan con un clic real en su rectángulo."""
    try:
        control.click_input()
        return True
    except Exception:
        return False


def buscar(raiz, tipo, clave, segundos=20):
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            for control in raiz.descendants(control_type=tipo):
                try:
                    rotulo = (control.window_text() or "").lower()
                    if clave.lower() in rotulo and control.is_visible():
                        return control
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.5)
    return None


def dentro_de(control, ventana) -> bool:
    try:
        for candidato in ventana.descendants():
            if candidato.element_info == control.element_info:
                return True
    except Exception:
        pass
    return False


def menu_item(clave, segundos=20):
    """Busca un MenuItem dentro de las ventanas Menu de nivel superior."""
    from pywinauto import Desktop
    fin = time.time() + segundos
    vistos = []
    while time.time() < fin:
        try:
            escritorio = Desktop(backend="uia")
            menus = [ventana for ventana in escritorio.windows()
                     if ventana.element_info.control_type == "Menu"]
            if not menus:
                menus = list(escritorio.children(control_type="Menu"))
            for menu in menus:
                try:
                    for item in menu.descendants(control_type="MenuItem"):
                        rotulo = item.window_text() or ""
                        if rotulo and rotulo not in vistos:
                            vistos.append(rotulo)
                        if clave.lower() in rotulo.lower():
                            return item, vistos
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.5)
    return None, vistos


def activar_item(control) -> bool:
    try:
        control.invoke()
        return True
    except Exception:
        pass
    try:
        control.click_input()
        return True
    except Exception:
        return False


def con_foco():
    from pywinauto.controls.uiawrapper import UIAWrapper
    from pywinauto.uia_defines import IUIA
    from pywinauto.uia_element_info import UIAElementInfo
    try:
        return UIAWrapper(UIAElementInfo(IUIA().iuia.GetFocusedElement()))
    except Exception:
        return None


def leer(control):
    for lector in (lambda: control.iface_value.CurrentValue,
                   lambda: control.get_value(),
                   lambda: control.legacy_properties()["Value"]):
        try:
            return lector()
        except Exception:
            pass
    return ""


def enfocar(control, paso: int, nombre: str) -> None:
    control.set_focus()
    if not control.has_keyboard_focus():
        raise FalloPaso(paso, f"{nombre} no tomó el foco")


def escribir(control, texto, paso: int) -> None:
    enfocar(control, paso, "el campo")
    control.type_keys("^a")
    control.type_keys(
        "".join("{" + c + "}" if c in "+^%~(){}" else c for c in texto),
        with_spaces=True, pause=0.03)
    valor = leer(control)
    if valor != texto:
        raise FalloPaso(paso, f"el campo quedó en «{valor}»")


def elegir(control, opciones, elegida, paso: int) -> None:
    from pywinauto import keyboard
    posicion = tuple(opciones).index(elegida)
    enfocar(control, paso, "el desplegable")
    keyboard.send_keys("{HOME}")
    for _ in range(posicion):
        keyboard.send_keys("{DOWN}")
    valor = leer(control)
    if valor != elegida:
        raise FalloPaso(paso, f"el desplegable quedó en «{valor}»")
