"""Cómo se pasa la pantalla de consentimiento de Google en Chrome.

Maneja la ventana de Chrome por UI Automation, como el banco: elige la
cuenta si aparece el selector, pasa el aviso de aplicación sin verificar,
marca el permiso y pulsa Continue hasta que la aplicación queda con
sesión. Antes de aceptar deja el foco en la barra de direcciones para que
la dirección con el client_id se vea en el video.

Cada espera tiene plazo: si un paso no aparece, lanza un error con su
nombre. No crea ventanas ni toca la aplicación.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import video_chrome
from video_controles import FalloPaso, con_foco, leer

ESPERA_CORTA = 2.0
TIPOS_PAGINA = ("Button", "Hyperlink", "Custom", "CheckBox", "Text")
_FIN_ENVIADO = set()


def _buscar_en(raiz, tipos, claves, segundos: float = ESPERA_CORTA,
               exacto: bool = True, visible: bool = True):
    """Primer control visible de esos tipos cuyo texto coincida."""
    if isinstance(claves, str):
        claves = (claves,)
    claves = tuple(_normalizar(clave) for clave in claves)
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            for control in raiz.descendants():
                try:
                    if control.element_info.control_type not in tipos:
                        continue
                    if visible and not control.is_visible():
                        continue
                    rotulo = _normalizar(control.window_text())
                except Exception:
                    continue
                if any(coincide(rotulo, clave) if exacto else clave in rotulo
                       for clave in claves):
                    return control
        except Exception:
            pass
        time.sleep(0.25)
    return None


def _normalizar(texto: str) -> str:
    return " ".join((texto or "").lower().replace("’", "'").replace("‘", "'").split())


def coincide(texto: str, clave: str) -> bool:
    return _normalizar(texto) == _normalizar(clave)


def _llevar_a_la_vista(control, chrome, paso: int = 3) -> None:
    """ScrollItem y, si falla, un End por página cuando ya cargó."""
    try:
        control.iface_scroll_item.ScrollIntoView()
        return
    except Exception:
        pass
    titulo = _normalizar(video_chrome.titulo_chrome(chrome))
    if (not titulo or titulo in ("sin título", "untitled", "about:blank")
            or titulo in _FIN_ENVIADO):
        return
    _FIN_ENVIADO.add(titulo)
    video_chrome.traer_al_frente(chrome, paso)
    chrome.type_keys("{END}")
    time.sleep(0.5)


def _pulsar_texto(raiz, claves, chrome, paso: int = 3,
                  segundos: float = ESPERA_CORTA):
    control = _buscar_en(raiz, TIPOS_PAGINA, claves, segundos,
                         visible=False)
    if control is None:
        return None
    _llevar_a_la_vista(control, chrome, paso)
    control = _buscar_en(raiz, TIPOS_PAGINA, claves, segundos,
                         visible=False)
    return control if control is not None and _clic(control) else None


def _clic(control) -> bool:
    try:
        control.click_input()
        return True
    except Exception:
        return False


def _tipo_control(control) -> str:
    try:
        return (control.element_info.control_type or "?") if control else "-"
    except Exception:
        return "?"


def _hay_texto(chrome, claves) -> bool:
    return _buscar_en(chrome, ("Text", "Heading"), claves, 0.4,
                      exacto=False) is not None


def _pagina(chrome):
    """Contenedor de la página web, fuera de la barra de título y el marco."""
    try:
        for documento in chrome.descendants(control_type="Document"):
            if documento.is_visible():
                return documento
    except Exception:
        pass
    return chrome


def _texto_ajeno(rotulo: str) -> bool:
    bajo = (rotulo or "").lower()
    claves = (
        "use another account", "usar otra cuenta", "add another account",
        "agregar otra cuenta", "add account", "agregar cuenta",
        "minimizar", "maximizar", "restaurar", "cerrar", "close",
        "minimize", "maximize", "restore", "nueva pestaña", "new tab",
        "atrás", "back", "adelante", "forward", "recargar", "reload")
    return any(clave in bajo for clave in claves)


def _elegir_cuenta(pagina, chrome):
    """La primera fila con una dirección de correo, nunca otra cuenta."""
    for tipo in ("ListItem", "Button"):
        try:
            filas = list(pagina.descendants(control_type=tipo))
        except Exception:
            continue
        for fila in filas:
            try:
                rotulo = fila.window_text() or ""
                if (not fila.is_visible() or "@" not in rotulo
                        or _texto_ajeno(rotulo)):
                    continue
            except Exception:
                continue
            _llevar_a_la_vista(fila, chrome, 3)
            if _clic(fila):
                return fila
    return None


def comprobar_burbuja(chrome, paso: int = 2) -> None:
    """Falla si la burbuja de restaurar sigue a la vista, sin tocarla."""
    if _hay_texto(chrome, ("restaurar las páginas", "restore pages")):
        raise RuntimeError(f"paso {paso}: burbuja de restaurar de Chrome")


def _textos_visibles(raiz, limite: int = 10):
    vistos = []
    try:
        controles = raiz.descendants()
    except Exception:
        return vistos
    for control in controles:
        try:
            if control.element_info.control_type not in (
                    "Heading", "Text", "Button", "Hyperlink"):
                continue
            if not control.is_visible():
                continue
            rotulo = (control.window_text() or "").strip()
        except Exception:
            continue
        if rotulo and rotulo not in vistos:
            vistos.append(rotulo)
        if len(vistos) >= limite:
            break
    return vistos


def _marcar_permiso(pagina, chrome):
    """Marca la casilla del permiso youtube.force-ssl si está sin marcar."""
    control = _buscar_en(pagina, ("CheckBox", "Custom"),
                         ("youtube.force-ssl", "manage your youtube account"),
                         1.0, visible=False)
    if control is None:
        for candidato in _casillas(pagina):
            try:
                rotulo = _normalizar(candidato.window_text())
                if "select all" in rotulo or "seleccionar todo" in rotulo:
                    continue
                if not candidato.is_selected():
                    control = candidato
                    break
            except Exception:
                pass
    if control is None:
        return None
    try:
        if control.is_selected():
            return None
    except Exception:
        pass
    _llevar_a_la_vista(control, chrome, 3)
    return control if _clic(control) else None


def _casillas(pagina):
    try:
        return list(pagina.descendants(control_type="CheckBox"))
    except Exception:
        return []


def desplazamiento_client_id(valor: str) -> int:
    indice = valor.find("client_id=")
    if indice < 0:
        return 0
    return min(len(valor), len(valor) - indice + 15)


def mostrar_client_id(chrome, paso: int = 3) -> None:
    """Muestra el client_id en la barra de direcciones y espera cinco segundos."""
    video_chrome.traer_al_frente(chrome, paso)
    chrome.type_keys("^l")
    time.sleep(0.3)
    barra = con_foco()
    if barra is None or barra.element_info.control_type != "Edit":
        raise FalloPaso(paso, "Ctrl+L no dejó el foco en la barra de direcciones")
    valor = leer(barra)
    if not valor.startswith("https://accounts.google.com"):
        raise FalloPaso(paso, f"la barra no tiene una dirección de Google: "
                              f"«{valor}»")
    if "client_id=" not in valor:
        raise FalloPaso(paso, "la dirección no contiene client_id=")
    desplazamiento = desplazamiento_client_id(valor)
    from pywinauto import keyboard
    keyboard.send_keys("{END}" + "{LEFT}" * desplazamiento, pause=0)
    time.sleep(6)
    keyboard.send_keys("{ESC}")


AVISO_PERMISO = ("AVISO: el permiso ya estaba dado, este video no sirve "
                 "para Google; la limpieza lo revoca")


def permiso_ya_dado(textos) -> bool:
    return any("already has some access" in _normalizar(texto)
               or "ya tiene acceso" in _normalizar(texto)
               for texto in textos)


def decidir_permiso(hay_linea: bool, textos) -> str:
    if hay_linea:
        return "mostrar"
    if permiso_ya_dado(textos):
        return "aviso"
    return "error"


def mostrar_permiso(pagina, chrome, paso: int = 3) -> bool:
    """Muestra la línea del permiso o avisa si el permiso ya estaba dado."""
    control = _buscar_en(pagina, ("CheckBox", "Custom", "Text"),
                         ("youtube.force-ssl", "manage your youtube account",
                          "youtube"), 2.0, exacto=False, visible=False)
    textos = _textos_visibles(pagina, limite=40)
    decision = decidir_permiso(control is not None, textos)
    if decision == "mostrar":
        _llevar_a_la_vista(control, chrome, paso)
        time.sleep(4)
        return False
    if decision == "aviso":
        print(AVISO_PERMISO)
        return True
    raise FalloPaso(paso, "no se encontró la línea del permiso")


def revocar_token(programa) -> None:
    """Revoca el token de la copia para que el próximo consentimiento sea nuevo."""
    if not programa:
        return
    ruta = Path(programa) / "data" / "credenciales.json"
    if not ruta.exists():
        return
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        info = json.loads(datos.get("token") or "{}")
    except Exception as exc:
        print(f"No se pudo leer el token para revocar: "
              f"{type(exc).__name__}: {exc!r}")
        return
    valor = info.get("refresh_token") or info.get("token") or ""
    if not valor:
        return
    cuerpo = urllib.parse.urlencode({"token": valor}).encode()
    solicitud = urllib.request.Request(
        "https://oauth2.googleapis.com/revoke", data=cuerpo,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        urllib.request.urlopen(solicitud, timeout=30).read()
    except Exception as exc:
        print(f"No se pudo revocar el token: {type(exc).__name__}: {exc!r}")


def completar(chrome, sesion_lista, segundos: int = 120) -> bool:
    """Recorre la página hasta que la aplicación tiene sesión."""
    fin = time.time() + segundos
    titulo_advanced = None
    titulo_direccion = None
    ya_dado = False
    while time.time() < fin:
        try:
            if sesion_lista():
                return ya_dado
        except Exception:
            pass
        pagina = _pagina(chrome)
        titulo = video_chrome.titulo_chrome(chrome)
        control = _pulsar_texto(
            pagina, ("go to guyrapu (unsafe)",
                     "ir a guyrapu (no seguro)"), chrome)
        accion = "unsafe" if control is not None else "espera"
        if control is None:
            control = _marcar_permiso(pagina, chrome)
            if control is not None:
                accion = "permiso"
        if control is None and titulo_direccion != titulo:
            if _buscar_en(pagina, TIPOS_PAGINA, ("continue", "continuar"),
                          ESPERA_CORTA, visible=False) is not None:
                mostrar_client_id(chrome, 3)
                ya_dado = mostrar_permiso(pagina, chrome, 3) or ya_dado
                titulo_direccion = titulo
        if control is None:
            control = _pulsar_texto(pagina, ("continue", "continuar"), chrome)
            if control is not None:
                accion = "continue"
        if control is None and titulo_advanced != titulo:
            control = _pulsar_texto(pagina, ("advanced", "avanzado"), chrome)
            if control is not None:
                accion = "advanced"
                titulo_advanced = titulo
        if control is None:
            control = _elegir_cuenta(pagina, chrome)
            if control is not None:
                accion = "cuenta"
        textos = _textos_visibles(pagina)
        print(f"[consentimiento] Chrome «{titulo}» | "
              f"textos: {' / '.join(textos) or '(ninguno)'} | "
              f"acción: {accion} ({_tipo_control(control)})")
        time.sleep(1.5 if accion != "espera" else 0.5)
    raise RuntimeError(
        "la página de Google no llegó a la sesión de la aplicación")
