"""Cómo se conduce la app por los pasos del video de force-ssl.

Los pasos 1 y 3 a 10, con sus esperas, el registro de segundos y el id del
directo propio. Nunca escribe, comenta ni modera fuera del directo creado.
"""

from __future__ import annotations

import ctypes
import json
import time
from contextlib import contextmanager
from pathlib import Path

import directo_real as dr
import video_chrome
import video_consentimiento
from video_controles import (FalloPaso, activar_item, activar_menu, buscar,
                             con_foco, dentro_de, elegir, escribir, menu_item)
import video_montaje as montaje

DEMO_TITULO = "Guyrapu verification demo"
DEMO_PRIVACIDAD = "unlisted"
TEXTO_CHAT = "Hello from Guyrapu"
TEXTO_COMENTARIO = "Thanks for watching"
AL_AIRE = "live stream started on"
ENVIADO = "message sent to the chat"
FIN = "broadcast stopped"
OBJETIVO_AL_AIRE = 160.0


class Corte(Exception):
    """Corte pedido con `--hasta`: no es un fallo."""


class Recorrido:
    def __init__(self):
        self.inicio = time.time()
        self.pasos = []
        self.actual = None
        self.ultimo = 0

    def desde_inicio(self) -> float:
        return time.time() - self.inicio

    def empezar(self, numero: int) -> None:
        self.actual = (numero, self.desde_inicio())
        self.ultimo = numero
        print(f"Paso {numero}: empieza")

    def terminar(self) -> None:
        if self.actual is None:
            return
        numero, inicio = self.actual
        self.actual = None
        self.pasos.append({"numero": numero, "inicio": inicio,
                           "fin": self.desde_inicio(),
                           "texto": montaje.SUBTITULOS[numero]})
        print(f"Paso {numero}: termina")


@contextmanager
def paso_de(rec, numero):
    rec.empezar(numero)
    try:
        yield
    finally:
        rec.terminar()


def sesion_guardada(ruta_datos, segundos: int = 0) -> bool:
    fin = time.time() + segundos
    while True:
        try:
            datos = json.loads((Path(ruta_datos) / "credenciales.json")
                               .read_text(encoding="utf-8"))
            if datos.get("token"):
                return True
        except Exception:
            pass
        if time.time() >= fin:
            return False
        time.sleep(1)


def ventana_principal(segundos: int = 90):
    """Ventana principal cuyo título empieza con «Guyrapu»."""
    from pywinauto import Desktop
    fin = time.time() + segundos
    vistos = set()
    while time.time() < fin:
        try:
            for ventana in Desktop(backend="uia").windows():
                try:
                    titulo = (ventana.window_text() or "").strip()
                except Exception:
                    continue
                if titulo.startswith("Guyrapu"):
                    return ventana
                if titulo:
                    vistos.add(titulo)
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("no apareció la ventana principal que empieza con "
                       f"«Guyrapu»; vistas: {sorted(vistos)}")


def minimizar_consola() -> None:
    """Minimiza la consola del guion para que no salga en la grabación."""
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 6)
    except Exception:
        pass


def _abrir_por_menu(principal) -> bool:
    herramientas = buscar(principal, "MenuItem", "Tools", 10)
    if herramientas is None:
        return False
    if not activar_menu(herramientas):
        return False
    item = buscar(dr._escritorio(), "MenuItem", "Preferences", 10)
    return bool(item is not None and activar_menu(item))


def _abrir_preferencias(principal):
    """Primero Tools y Preferences por UI Automation, luego el atajo."""
    if _abrir_por_menu(principal):
        try:
            return dr._dialogo_hijo(principal, "Preferences", 20)
        except RuntimeError:
            pass
    video_chrome.traer_al_frente(principal, 1)
    principal.type_keys("{ESC}{ESC}")
    video_chrome.traer_al_frente(principal, 1)
    principal.type_keys("^+p")
    return dr._dialogo_hijo(principal, "Preferences", 20)


def _elegir_categoria(prefs, nombre) -> None:
    """Elige una categoría del Listbook, que es una lista, no pestañas."""
    try:
        lista = dr._control(prefs, "Categories", "List", 5)
    except RuntimeError:
        lista = prefs
    item = buscar(lista, "ListItem", nombre, 20)
    if item is None:
        raise FalloPaso(1, f"no apareció la categoría «{nombre}»")
    item.select()


def iniciar(principal, rec):
    """Paso 1: abre Preferencias, API and session, y pulsa Sign in."""
    with paso_de(rec, 1):
        prefs = _abrir_preferencias(principal)
        _elegir_categoria(prefs, "API and session")
        dr._control(prefs, "Sign in", "Button").invoke()
    return prefs


def consentir(chrome, datos, rec) -> bool:
    """Paso 3: acepta el permiso y espera la sesión en la copia."""
    ya_dado = False
    with paso_de(rec, 3):
        ya_dado = video_consentimiento.completar(
            chrome, lambda: sesion_guardada(datos), 120)
        if not sesion_guardada(datos, 60):
            raise FalloPaso(3, "la copia no guardó la sesión de Google")
    with paso_de(rec, 11):
        time.sleep(1.5)
    video_chrome.cerrar_pestana(chrome)
    return ya_dado


def _enviar_chat(principal, anuncios, chat) -> None:
    marca = len(dr._leer_anuncios(anuncios))
    video_chrome.traer_al_frente(principal, 6)
    principal.type_keys("%{ENTER}")
    time.sleep(0.3)
    campo = con_foco()
    if campo is None or campo.element_info.control_type != "Edit":
        raise FalloPaso(6, "Alt+Intro no dejó el foco en el compositor")
    escribir(campo, TEXTO_CHAT, 6)
    boton = buscar(principal, "Button", "Send", 10)
    if boton is None:
        raise FalloPaso(6, "no apareció el botón Send")
    boton.invoke()
    if dr._esperar_anuncio(anuncios, (ENVIADO,), 30, marca) is None:
        raise FalloPaso(6, f"sin «{ENVIADO}»")
    faltante, leidos = dr._comentario_faltante(chat, (TEXTO_CHAT,), 30)
    if faltante is not None:
        raise FalloPaso(6, f"«{TEXTO_CHAT}» no apareció en el chat "
                           f"({dr._detalle_lista_chat(leidos)})")


def _menu_timeout(principal) -> None:
    try:
        lista = dr._control(principal, "Live chat", "List", 5)
    except RuntimeError:
        lista = principal
    mensaje = buscar(lista, "ListItem", TEXTO_CHAT, 30)
    if mensaje is None:
        raise FalloPaso(7, "el mensaje propio no apareció en la lista")
    try:
        mensaje.select()
    except Exception:
        pass
    mensaje.right_click_input()
    entrada, vistos = menu_item("in timeout", 20)
    if entrada is None:
        raise FalloPaso(7, "no apareció la entrada; MenuItem vistos: "
                           + (", ".join(vistos) or "(ninguno)"))
    if not activar_item(entrada):
        raise FalloPaso(7, "no se pudo activar la entrada del timeout")
    confirmacion = dr._dialogo_hijo(principal, "Confirm moderation", 20)
    time.sleep(3)
    for clave in ("No", "Cancel", "Cancelar"):
        boton = buscar(confirmacion, "Button", clave, 2)
        if boton is not None:
            boton.invoke()
            return
    raise FalloPaso(7, "la confirmación no ofreció No ni Cancel")


def cliente_de_la_copia(copia):
    from guyrapu.youtube import youtube_api
    datos = json.loads((Path(copia) / "data" / "credenciales.json")
                       .read_text(encoding="utf-8"))
    app = json.loads((Path(copia) / "cliente_app.json")
                     .read_text(encoding="utf-8"))
    return youtube_api.ClienteYouTube({
        "token": datos.get("token") or "",
        "oauth_client_id": datos.get("oauth_client_id")
        or app.get("oauth_client_id") or "",
        "oauth_client_secret": datos.get("oauth_client_secret")
        or app.get("oauth_client_secret") or "",
        "api_key": datos.get("api_key") or app.get("api_key") or "",
    })


def _esperar_id(cliente, previos, segundos=90) -> str:
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            hallado, titulo, privacidad = dr._buscar_video_por_titulo(
                cliente, DEMO_TITULO)
        except Exception:
            hallado, titulo, privacidad = ("", "", "")
        if hallado and hallado not in previos \
                and titulo == DEMO_TITULO and privacidad == DEMO_PRIVACIDAD:
            return hallado
        time.sleep(3)
    raise FalloPaso(5, "la API no devolvió el id del directo creado")


def _lista_comentarios(principal):
    vistos = []
    try:
        for control in principal.descendants(control_type="List"):
            try:
                tipo = control.element_info.control_type
                nombre = control.window_text() or "(sin nombre)"
                vistos.append(f"{tipo}: {nombre}")
                if control.is_visible():
                    return control
            except Exception:
                pass
    except Exception:
        pass
    raise FalloPaso(9, "no apareció la lista de comentarios; List vistos: "
                       + (", ".join(vistos) or "(ninguno)"))


def _publicar_comentario(principal, id_video) -> None:
    pestania = dr._control(principal, "Comments", "TabItem")
    try:
        pestania.select()
    except Exception:
        pestania.invoke()
    boton = buscar(principal, "Button", "Comment on the video", 20)
    if boton is None:
        raise FalloPaso(9, "no apareció el botón para comentar")
    boton.invoke()
    dialogo = dr._dialogo_hijo(principal, "Comment", 20)
    campo = con_foco()
    if campo is None or campo.element_info.control_type != "Edit":
        raise FalloPaso(9, "el foco no quedó en el campo del comentario")
    if not dentro_de(campo, dialogo):
        raise FalloPaso(9, "el foco no quedó dentro del diálogo Comment")
    escribir(campo, TEXTO_COMENTARIO, 9)
    boton = buscar(dialogo, "Button", "Publish", 10)
    if boton is None:
        raise FalloPaso(9, "no apareció el botón Publish")
    boton.invoke()
    lista = _lista_comentarios(principal)
    fin = time.time() + 30
    while time.time() < fin:
        recargar = buscar(principal, "Button", "Reload comments", 2)
        if recargar is not None:
            recargar.invoke()
        if buscar(lista, "ListItem", TEXTO_COMENTARIO, 3) is not None:
            return
        time.sleep(2)
    raise FalloPaso(9, f"el comentario no apareció en la lista "
                       f"del video {id_video}")


def _crear_directo(principal, anuncios, estado) -> None:
    cliente = estado["cliente"]
    previos = set()
    try:
        respuesta = cliente._escritura().liveBroadcasts().list(
            part="id,snippet", mine=True, maxResults=25).execute()
        previos = {(item.get("id") or "") for item in respuesta.get("items", [])
                   if (item.get("snippet") or {}).get("title") == DEMO_TITULO}
    except Exception:
        pass
    estado["previos"] = previos
    dr._control(principal, "Broadcast live", "Button").invoke()
    destino = dr._dialogo_hijo(principal, "Broadcast to", 30)
    elegir(dr._control(destino, "Broadcast to", "ComboBox"),
                   ("TikTok", "YouTube"), "YouTube", 4)
    dr._control(destino, "Continue", "Button").invoke()
    directo = dr._dialogo_hijo(principal, "YouTube live stream", 120)
    escribir(dr._control(directo, "Live stream title", "Edit"),
                    DEMO_TITULO, 4)
    elegir(dr._control(directo, "Privacy", "ComboBox"),
                   ("Public", "Unlisted", "Private"), "Unlisted", 4)
    estado["marca"] = len(dr._leer_anuncios(anuncios))
    dr._control(directo, "Broadcast", "Button").invoke()
    estado["pulso"] = True


def _al_aire(anuncios, rec, estado) -> None:
    resultado = dr._esperar_anuncio(
        anuncios, (AL_AIRE, "no se pudo", "failed"), 240, estado["marca"])
    if resultado is None or AL_AIRE not in resultado.lower():
        raise FalloPaso(5, f"la app no anunció que salió al aire "
                           f"({resultado})")
    estado["id_video"] = _esperar_id(estado["cliente"], estado["previos"])
    while rec.desde_inicio() < OBJETIVO_AL_AIRE:
        time.sleep(1)


def _terminar_directo(principal, anuncios, estado) -> None:
    marca = len(dr._leer_anuncios(anuncios))
    dr._control(principal, "End live stream", "Button").invoke()
    confirmacion = dr._dialogo_hijo(principal, "End live stream", 20)
    dr._control(confirmacion, "End live stream", "Button").invoke()
    if dr._esperar_anuncio(anuncios, (FIN,), 90, marca) is None:
        raise FalloPaso(8, f"sin «{FIN}»")
    estado["finalizado"] = True


def _corta(rec, hasta, numero) -> None:
    if hasta is not None and numero >= hasta:
        raise Corte()


def por_el_directo(principal, rec, anuncios, chat, estado,
                   hasta=None) -> None:
    """Pasos 4 a 10, sobre el directo que crea este mismo guion."""
    with paso_de(rec, 4):
        _crear_directo(principal, anuncios, estado)
    _corta(rec, hasta, 4)
    with paso_de(rec, 5):
        _al_aire(anuncios, rec, estado)
    _corta(rec, hasta, 5)
    with paso_de(rec, 6):
        _enviar_chat(principal, anuncios, chat)
    _corta(rec, hasta, 6)
    with paso_de(rec, 7):
        _menu_timeout(principal)
    _corta(rec, hasta, 7)
    with paso_de(rec, 8):
        _terminar_directo(principal, anuncios, estado)
    _corta(rec, hasta, 8)
    with paso_de(rec, 9):
        _publicar_comentario(principal, estado["id_video"])
    _corta(rec, hasta, 9)
    with paso_de(rec, 10):
        time.sleep(4)
