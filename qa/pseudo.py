"""Barrido de la aplicación con la pseudotraducción puesta.

Arranca la app con `GUYRAPU_IDIOMA=pseudo`, recorre la ventana principal,
los menús, los cuadros que abren, Preferencias y una sesión simulada, anota
cada texto que no lleva la marca `[¡...!]` y se lanza con
`python qa/pseudo.py`.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import time
from pathlib import Path

_QA = Path(__file__).resolve().parent
for _ruta in (_QA.parent, _QA):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))

from guyrapu.obs.fuente_chat import NOMBRE_FUENTE as NOMBRE_FUENTE_CHAT  # noqa: E402

TITULO_DIRECTO = "Directo de prueba"
AUTOR_MENSAJE = "rolon_100"
TEXTO_MENSAJE = "Hola a todos"
# «Chat en el vídeo» es el nombre real de la fuente en OBS y la app la reconoce por él.
PROPIOS = (TITULO_DIRECTO, AUTOR_MENSAJE, TEXTO_MENSAJE, NOMBRE_FUENTE_CHAT)

# Un nombre por defecto de wx no lo oye nadie, así que no cuenta.
NOMBRES_INTERNOS = {
    "", "panel", "frame", "dialog", "text", "textctrl", "button",
    "bitmapbutton", "statictext", "staticbox", "groupbox", "listbox", "listctrl",
    "checkbox", "choice", "combobox", "slider", "radiobutton", "radiobox",
    "spinctrl", "notebook", "control", "menu", "menubar", "statusbar",
    "toolbar", "scrolledwindow", "splitterwindow", "treectrl", "listview",
    "grid", "gauge", "togglebutton", "window", "toplevelwindow",
}

# Las entradas con «…» que dejan algo abierto al cerrarlas sin guardar.
OMITIDAS = {
    "guía de configuración de la api": "abre el navegador",
}

CON_ROTULO = {
    "StaticText", "Button", "BitmapButton", "CheckBox", "RadioButton",
    "ToggleButton", "StaticBox", "RadioBox",
}

# Los submenús que se arman con datos del usuario.
MENUS_DE_DATOS = ("elegir voz", "mensajes recientes del chat")

# Rótulos que delatan una lista con datos del usuario.
DATOS_DE_USUARIO = (
    "voz", "voces", "micrófono", "microfono", "escena", "escenas",
    "colección", "coleccion", "chat", "historial", "descarga", "música",
    "musica", "canción", "cancion", "álbum", "album", "artista", "fuente",
    "ventana que se captura", "dispositivo", "lista", "modelo", "proveedor",
    "mostrar", "género", "genero", "playlist",
)

_PROPIOS = re.compile(
    r"\b(?:Bellbird|YouTube|TikTok|OBS|NVDA|VLC|Google|Windows)\b",
    re.IGNORECASE)
_ATAJOS = re.compile(
    r"(?:\[¡[^\[\]]*!\]|Ctrl|Control|Alt|Shift|Mayús|Mayus|Windows|Win)"
    r"(?:\s*\+\s*(?:\[¡[^\[\]]*!\]|Ctrl|Control|Alt|Shift|Mayús|Mayus|"
    r"F\d{1,2}|[A-Za-z0-9]))+", re.IGNORECASE)
_TECLAS = re.compile(r"\bF(?:[1-9]|1[0-9]|2[0-4])\b", re.IGNORECASE)
_VERSIONES = re.compile(r"\bv?\d+(?:\.\d+)*[a-z]?\b", re.IGNORECASE)
# Un nombre de control sin espacios, con guion bajo o mayúscula interna, es un
# identificador para el banco y no texto para el usuario.
IDENTIFICADOR = re.compile(r"^[^ ]*(?:_|[a-záéíóúüñ][A-ZÁÉÍÓÚÜÑ])[^ ]*$")

NO_CUBRE = "No cubre: cabeceras de columnas, opciones de RadioBox y las entradas de menú con efecto externo (Guía de configuración de la API…)."


def _quitar_marcas(texto):
    salida = []
    i = 0
    while i < len(texto):
        if texto.startswith("[¡", i):
            nivel = 1
            i += 2
            while i < len(texto) and nivel:
                if texto.startswith("[¡", i):
                    nivel += 1
                    i += 2
                elif texto.startswith("!]", i):
                    nivel -= 1
                    i += 2
                else:
                    i += 1
            continue
        salida.append(texto[i])
        i += 1
    return "".join(salida)


def _es_nombre_interno(texto):
    limpio = re.sub(r"\d+$", "", str(texto or "").strip().casefold())
    return limpio in NOMBRES_INTERNOS


def sin_marcar(texto, propios=()):
    """El texto entero si le queda alguna letra sin traducir; None si no.

    Borra las marcas, los nombres propios, los atajos, las versiones, los
    números y la puntuación. Los textos de `propios` son los que inyectó el
    guion y no los escribe la aplicación.
    """
    original = str(texto or "")
    if not original.strip() or _es_nombre_interno(original):
        return None
    limpio = original
    for propio in propios:
        propio = str(propio or "").strip()
        if not propio:
            continue
        if original.strip() == propio:
            return None
        limpio = limpio.replace(propio, " ")
    limpio = _PROPIOS.sub(" ", limpio)
    limpio = _ATAJOS.sub(" ", limpio)
    limpio = _quitar_marcas(limpio)
    limpio = _TECLAS.sub(" ", limpio)
    limpio = _VERSIONES.sub(" ", limpio)
    if not any(caracter.isalpha() for caracter in limpio):
        return None
    return original


def _nombre_control(datos):
    nombre = str(datos.get("nombre") or "").strip()
    if nombre and not _es_nombre_interno(nombre):
        return nombre
    return str(datos.get("clase") or "control")


def _es_dato_de_usuario(datos):
    texto = f"{datos.get('nombre', '')} {datos.get('etiqueta', '')}".casefold()
    return any(palabra in texto for palabra in DATOS_DE_USUARIO)


class Recolector:

    def __init__(self, propios=()):
        self.propios = tuple(propios)
        self.hallados = {}

    def revisar(self, texto, ventana, control):
        falta = sin_marcar(texto, self.propios)
        if falta is not None and falta not in self.hallados:
            self.hallados[falta] = (ventana, control)

    def revisar_arbol(self, ventana, controles):
        for datos in controles:
            clase = datos.get("clase")
            control = _nombre_control(datos)
            nombre = str(datos.get("nombre") or "").strip()
            if not IDENTIFICADOR.match(nombre):
                self.revisar(nombre, ventana, control)
            if clase in CON_ROTULO:
                self.revisar(datos.get("etiqueta", ""), ventana, control)
            if clase == "Choice" and not _es_dato_de_usuario(datos):
                for opcion in datos.get("items") or ():
                    self.revisar(opcion, ventana, control)


def _titulos_visibles(app):
    return {v.get("titulo") or "" for v in app.ventanas() if v.get("visible")}


def _titulo_principal(app):
    for ventana in app.ventanas():
        titulo = ventana.get("titulo") or ""
        if ventana.get("visible") and "bellbird" in titulo.casefold():
            return titulo
    return ""


def _esperar_nueva(app, antes, segundos=10.0):
    limite = time.time() + segundos
    while time.time() < limite:
        for ventana in app.ventanas():
            titulo = ventana.get("titulo") or ""
            if ventana.get("visible") and titulo and titulo not in antes:
                return titulo
        time.sleep(0.2)
    return None


def _esperar_cierre(app, titulo, segundos=8.0):
    limite = time.time() + segundos
    while time.time() < limite:
        if titulo not in _titulos_visibles(app):
            return True
        time.sleep(0.2)
    return False


def _revisar_pestanas(app, recolector, titulo):
    try:
        respuesta = app.pedir("pestanas", ventana=titulo, tolerar=True)
    except Exception:
        return
    if not respuesta.get("ok"):
        return
    for nombre in respuesta.get("datos", {}).get("paginas", []):
        recolector.revisar(nombre, titulo, "pestaña")


def _revisar_ventana(app, recolector, titulo, solo_marco=False):
    recolector.revisar(titulo, titulo, "título")
    _revisar_pestanas(app, recolector, titulo)
    if solo_marco:
        return True
    try:
        controles = app.arbol(titulo)
    except Exception:
        return False
    recolector.revisar_arbol(titulo, controles)
    return True


def _revisar_menus(app, recolector, ventana, res):
    try:
        items = app.menus()
    except Exception as exc:
        res.fallo(f"menús: no se pudieron leer, {exc}")
        return
    for datos in items:
        camino = str(datos.get("camino") or "")
        if any(fragmento in camino.casefold() for fragmento in MENUS_DE_DATOS):
            continue
        recolector.revisar(datos.get("etiqueta", ""), ventana,
                           f"menú {camino}")


def _cerrar(app, titulo):
    try:
        app.pedir("cerrar_ventana", ventana=titulo)
    except Exception:
        pass
    _esperar_cierre(app, titulo)


def _abrir_y_revisar(app, recolector, res, etiqueta, solo_marco=False):
    antes = _titulos_visibles(app)
    try:
        app.abrir_por_menu(etiqueta)
    except Exception as exc:
        res.fallo(f"menú «{etiqueta}»: no se pudo abrir, {exc}")
        return
    titulo = _esperar_nueva(app, antes)
    if titulo is None:
        res.nota(f"«{etiqueta}» no abrió una ventana que la sonda vea")
        return
    if not _revisar_ventana(app, recolector, titulo, solo_marco):
        res.nota(f"«{etiqueta}»: no se pudo leer el árbol de «{titulo}»")
    _cerrar(app, titulo)


def _abrir_cuadros(app, recolector, res):
    try:
        items = app.menus()
    except Exception as exc:
        res.fallo(f"cuadros: no se pudieron leer los menús, {exc}")
        return
    for datos in items:
        etiqueta = str(datos.get("etiqueta") or "")
        visible = etiqueta.strip()
        if visible.startswith("[¡") and visible.endswith("!]"):
            visible = visible[2:-2]
        if datos.get("submenu") or not visible.endswith(("...", "…")):
            continue
        base = re.sub(r"(?:\.\.\.|…)$", "", visible.replace("&", "").strip()).casefold()
        if base in OMITIDAS:
            res.nota(f"no se abre «{etiqueta}»: {OMITIDAS[base]}")
            continue
        _abrir_y_revisar(app, recolector, res, etiqueta,
                         solo_marco=(base == "preferencias"))


def _recorrer_preferencias(app, recolector, res):
    antes = _titulos_visibles(app)
    try:
        app.abrir_por_menu("Preferencias")
    except Exception as exc:
        res.fallo(f"preferencias: no se pudo abrir, {exc}")
        return
    titulo = _esperar_nueva(app, antes)
    if not titulo:
        res.fallo("preferencias: no abrió")
        return
    try:
        respuesta = app.pedir("pestanas", ventana=titulo)
    except Exception as exc:
        res.fallo(f"preferencias: no se pudieron listar las categorías, {exc}")
        _cerrar(app, titulo)
        return
    paginas = respuesta.get("datos", {}).get("paginas", [])
    for indice, nombre in enumerate(paginas):
        try:
            app.pedir("pestanas", ventana=titulo, indice=indice)
            time.sleep(0.6)
            visibles = [c for c in app.arbol(titulo)
                        if c.get("en_pantalla")]
        except Exception as exc:
            res.fallo(f"preferencias/{nombre}: no se pudo recorrer, {exc}")
            continue
        recolector.revisar_arbol(f"{titulo}/{nombre}", visibles)
    _cerrar(app, titulo)


def _recorrer_sesion(app, recolector, res):
    try:
        app.simular_sesion_youtube(TITULO_DIRECTO)
        app.mensaje(AUTOR_MENSAJE, TEXTO_MENSAJE)
    except Exception as exc:
        res.fallo(f"sesión simulada: no se pudo montar, {exc}")
        return
    time.sleep(1.0)
    try:
        app.teclas("f2")
    except Exception as exc:
        res.nota(f"no se pudo pulsar F2: {exc}")
    titulo = _titulo_principal(app)
    if titulo:
        _revisar_ventana(app, recolector, titulo)


def _revisar_anuncios(app, recolector):
    for anuncio in app.anuncios:
        if anuncio.get("canal") != "sonda":
            recolector.revisar(anuncio.get("texto", ""), "anuncios", "voz")


def _una_linea(texto):
    return " ".join(str(texto).split())


def _informe(recolector):
    filas = sorted(
        (ventana, control, texto)
        for texto, (ventana, control) in recolector.hallados.items())
    if not filas:
        print("Sin textos sin marcar.")
    else:
        for ventana, control, texto in filas:
            print(f"{_una_linea(ventana)} · {_una_linea(control)}: "
                  f"«{_una_linea(texto)}»")
        ventanas = {ventana for ventana, _control, _texto in filas}
        print(f"{len(filas)} textos sin marcar en {len(ventanas)} ventanas.")
    print(NO_CUBRE)


def _recorrer_todo(app, recolector, res):
    titulo = _titulo_principal(app)
    if titulo:
        _revisar_ventana(app, recolector, titulo)
    else:
        res.fallo("no se encontró la ventana principal")
    _revisar_menus(app, recolector, titulo, res)
    _abrir_cuadros(app, recolector, res)
    _recorrer_preferencias(app, recolector, res)
    _recorrer_sesion(app, recolector, res)
    _revisar_anuncios(app, recolector)


def main():
    from conducir import (Aplicacion, Resultado, cerrar_obs_del_banco,
                          debe_cerrar_obs_al_final, obs_abierto)

    os.environ["GUYRAPU_IDIOMA"] = "pseudo"
    carpeta = Path(tempfile.mkdtemp(prefix="guyrapu-pseudo-"))
    app = Aplicacion(carpeta)
    res = Resultado()
    recolector = Recolector(PROPIOS)
    obs_al_empezar = obs_abierto()
    app.arrancar()
    try:
        if not app.esperar_lista(segundos=60):
            print("La aplicación no contestó al ping en 60 segundos.")
            return 2
        _recorrer_todo(app, recolector, res)
    finally:
        try:
            app.cerrar()
        except Exception:
            pass
        try:
            if debe_cerrar_obs_al_final(obs_al_empezar, obs_abierto()):
                cerrar_obs_del_banco(res)
        except Exception:
            pass
    _informe(recolector)
    if res.fallos:
        return 2
    return 1 if recolector.hallados else 0


if __name__ == "__main__":
    sys.exit(main())
