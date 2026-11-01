"""Sonda de QA: se mete dentro de la aplicación para grabarla y manejarla.

No es parte de la aplicación y la aplicación no la conoce. Se instala desde
fuera, antes de arrancar `main.py`, y hace dos cosas.

**Graba lo que la aplicación diría, sin decirlo.** Sustituye el objeto por el
que `accesibilidad.anunciar` habla con el lector de pantalla. El dueño es ciego y corre
estas pruebas él mismo: una prueba que hable le secuestra el lector mientras
trabaja.

**Recibe órdenes y las ejecuta dentro del proceso.** Esto es lo que corrige el
error de la primera versión, que manejaba la aplicación desde fuera con teclas
sintéticas. Para poder teclear había que robarle el primer plano a Windows, y
el truco para conseguirlo era mandar un ALT sintético, que activa la barra de
menú y hace que los aceleradores dejen de llegar. O sea que la herramienta
rompía justo lo que estaba midiendo.

Desde dentro no hace falta nada de eso: `wx.UIActionSimulator` es la
herramienta que wxWidgets trae para manejar sus propias pruebas, y
`wx.GetTopLevelWindows()` dice qué diálogos hay abiertos sin tener que
adivinarlo desde el árbol de UI Automation.

El canal de órdenes son dos archivos de líneas JSON, uno de entrada y otro de
salida. Es más fácil de depurar que un socket y sobrevive a que un lado muera.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

VAR_DESTINO = "YTCHAT_QA_ANUNCIOS"
VAR_ORDENES = "YTCHAT_QA_ORDENES"
VAR_RESULTADOS = "YTCHAT_QA_RESULTADOS"


class GrabadorAnuncios:
    """Ocupa el lugar del lector de pantalla y escribe en vez de hablar.

    Tiene que responder a `speak` y a `braille` porque `accesibilidad.anunciar` llama a
    los dos, y cada uno dentro de su propio try. Si alguno faltara, la
    excepción quedaría tapada y la grabación saldría incompleta sin avisar.
    """

    def __init__(self, ruta: str):
        self._ruta = ruta
        self._inicio = time.monotonic()
        self._lock = threading.Lock()

    def _apuntar(self, canal: str, texto: str) -> None:
        registro = {
            "t": round(time.monotonic() - self._inicio, 3),
            "canal": canal,
            "texto": texto,
        }
        with self._lock:
            with open(self._ruta, "a", encoding="utf-8") as f:
                f.write(json.dumps(registro, ensure_ascii=False) + "\n")
                f.flush()

    def speak(self, texto, interrupt=False):
        self._apuntar("voz", str(texto))

    def braille(self, texto):
        self._apuntar("braille", str(texto))


# ── Traducción de nombres de tecla a lo que entiende wx ───────────────────────

def _mapa_teclas():
    import wx
    return {
        "tab": wx.WXK_TAB, "enter": wx.WXK_RETURN, "return": wx.WXK_RETURN,
        "esc": wx.WXK_ESCAPE, "escape": wx.WXK_ESCAPE, "space": wx.WXK_SPACE,
        "up": wx.WXK_UP, "down": wx.WXK_DOWN,
        "left": wx.WXK_LEFT, "right": wx.WXK_RIGHT,
        "home": wx.WXK_HOME, "end": wx.WXK_END,
        "delete": wx.WXK_DELETE, "back": wx.WXK_BACK,
        # La tecla Aplicaciones, que es como abre el menu contextual
        # quien no usa raton. Sin ella no se puede probar ese menu.
        "menu": wx.WXK_WINDOWS_MENU, "aplicaciones": wx.WXK_WINDOWS_MENU,
        **{f"f{n}": getattr(wx, f"WXK_F{n}") for n in range(1, 13)},
    }


def _modificadores(nombres):
    import wx
    total = wx.MOD_NONE
    for n in nombres or ():
        n = n.lower()
        if n in ("ctrl", "control"):
            total |= wx.MOD_CONTROL
        elif n == "alt":
            total |= wx.MOD_ALT
        elif n == "shift":
            total |= wx.MOD_SHIFT
    return total


def _codigo_tecla(nombre: str) -> int:
    nombre = str(nombre)
    mapa = _mapa_teclas()
    if nombre.lower() in mapa:
        return mapa[nombre.lower()]
    if len(nombre) == 1:
        # Las letras van en mayúscula: UIActionSimulator espera el código de
        # tecla física, no el carácter que saldría.
        return ord(nombre.upper())
    raise ValueError(f"tecla desconocida: {nombre!r}")


def _limpiar_etiqueta(texto) -> str:
    """El texto de una entrada sin mnemónico ni puntos suspensivos."""
    limpio = str(texto or "").replace("&", "")
    for puntos in ("...", "…"):
        limpio = limpio.replace(puntos, "")
    return limpio.strip().casefold()


# ── Inspección de la interfaz, desde dentro ──────────────────────────────────

def _describir(ventana, profundidad=0):
    """Describe un control de wx como lo vería quien lo usa."""
    import wx

    try:
        nombre = ventana.GetName()
    except Exception:
        nombre = ""
    try:
        etiqueta = ventana.GetLabel()
    except Exception:
        etiqueta = ""
    datos = {
        "clase": ventana.__class__.__name__,
        "nombre": nombre,
        "etiqueta": etiqueta,
        "habilitado": bool(ventana.IsEnabled()),
        "visible": bool(ventana.IsShown()),
        # `IsShown` es la bandera propia del control. Lo que de verdad importa
        # es si está en pantalla, porque una pestaña no seleccionada esconde a
        # sus hijos y el servicio de accesibilidad no los expone. Comparar el
        # árbol de wx entero contra lo que ve Windows sin esto da una
        # diferencia enorme y falsa.
        "en_pantalla": bool(ventana.IsShownOnScreen()),
        "acepta_foco": bool(ventana.AcceptsFocus()),
        "nivel": profundidad,
    }
    if isinstance(ventana, wx.TextCtrl):
        try:    datos["valor"] = ventana.GetValue()
        except Exception: pass
    # Si la casilla no dice si está marcada, el banco no puede comprobar que
    # una preferencia guardada se muestra al reabrir Preferencias.
    if isinstance(ventana, wx.CheckBox):
        try:    datos["marcado"] = bool(ventana.GetValue())
        except Exception: pass
    # El valor del deslizador es lo que NVDA lee al moverlo con flechas, y
    # sin esto el banco no puede comprobar que la flecha movió algo.
    if isinstance(ventana, wx.Slider):
        try:    datos["valor"] = int(ventana.GetValue())
        except Exception: pass
    # El contenido de las listas es lo que de verdad lee el usuario, así que
    # sin esto no se puede comprobar que un mensaje llegó al chat. Los
    # desplegables también: «Colecciones» elige la fuente de la Biblioteca.
    if isinstance(ventana, (wx.ListBox, wx.Choice)):
        try:
            datos["items"] = list(ventana.GetStrings())
            datos["seleccion"] = int(ventana.GetSelection())
        except Exception: pass
    elif isinstance(ventana, wx.ListCtrl):
        try:
            filas = []
            for f in range(ventana.GetItemCount()):
                cols = []
                for c in range(max(1, ventana.GetColumnCount())):
                    try:    cols.append(ventana.GetItemText(f, c))
                    except Exception: break
                filas.append(cols)
            datos["items"] = filas
        except Exception: pass
    return datos


def _arbol(ventana, profundidad=0, tope=8):
    salida = [_describir(ventana, profundidad)]
    if profundidad >= tope:
        return salida
    try:
        hijos = list(ventana.GetChildren())
    except Exception:
        hijos = []
    for h in hijos:
        salida.extend(_arbol(h, profundidad + 1, tope))
    return salida


def _buscar_notebook(ventana):
    """El primer cuaderno de pestanas que cuelgue de esta ventana.

    Se reconoce por lo que sabe hacer y no por su clase: `wx.Notebook`,
    `wx.Listbook` y `wx.Treebook` no comparten antepasado util, y en este
    archivo `wx` solo esta importado dentro de las funciones que lo usan.
    """
    if all(hasattr(ventana, m) for m in
           ("GetPageCount", "GetPageText", "SetSelection", "GetSelection")):
        return ventana
    for hijo in ventana.GetChildren():
        encontrado = _buscar_notebook(hijo)
        if encontrado is not None:
            return encontrado
    return None


def _buscar_control(raiz, nombre: str):
    """Busca por nombre accesible, y si no por etiqueta. None si no está."""
    objetivo = (nombre or "").strip().lower()
    candidatos = []
    for ctrl in _iterar(raiz):
        try:
            n = (ctrl.GetName() or "").strip().lower()
            e = (ctrl.GetLabel() or "").strip().lower().replace("&", "")
        except Exception:
            continue
        if n == objetivo or e == objetivo:
            return ctrl
        if objetivo and (objetivo in n or objetivo in e):
            candidatos.append(ctrl)
    return candidatos[0] if candidatos else None


def _items_de_menu(menu, camino, salida):
    for item in menu.GetMenuItems():
        try:
            if item.IsSeparator():
                continue
            etiqueta = item.GetItemLabelText()
            completa = item.GetItemLabel()
            # El acelerador viaja pegado a la etiqueta tras un tabulador.
            acelerador = completa.split("\t", 1)[1] if "\t" in completa else ""
            datos = {
                "camino": " > ".join(camino + [etiqueta]),
                "etiqueta": etiqueta,
                "acelerador": acelerador,
                "habilitado": bool(item.IsEnabled()),
                "marcable": bool(item.IsCheckable()),
                "id": item.GetId(),
            }
            if item.IsCheckable():
                try:    datos["marcado"] = bool(item.IsChecked())
                except Exception: pass
            sub = item.GetSubMenu()
            if sub is not None:
                datos["submenu"] = True
                salida.append(datos)
                _items_de_menu(sub, camino + [etiqueta], salida)
            else:
                salida.append(datos)
        except Exception:
            continue


def _recorrer_menus(barra):
    salida = []
    if barra is None:
        return salida
    for i in range(barra.GetMenuCount()):
        try:
            titulo = barra.GetMenuLabelText(i)
            salida.append({
                "camino": titulo,
                "etiqueta": titulo,
                "acelerador": "",
                "habilitado": bool(barra.IsEnabledTop(i)),
                "marcable": False,
                "id": None,
                "submenu": True,
            })
            _items_de_menu(barra.GetMenu(i), [titulo], salida)
        except Exception:
            continue
    return salida


def _buscar_item_menu(barra, objetivo: str):
    """Devuelve (id, etiqueta) del ítem cuyo texto coincida. None si no está.

    La exacta gana: «subir volumen» no puede caer en «Subir volumen de la
    voz» solo porque ese menú se recorra antes. Sin exacta, como antes, la
    primera que la contiene. Con «menú > ítem» solo se busca dentro de ese
    menú de nivel superior, sin `&` y sin mayúsculas a la izquierda."""
    # Ojo: los ids que reparte `wx.ID_ANY` son NEGATIVOS. Descartar por
    # `id < 0` para saltarse los menús de nivel superior se lleva puestos
    # todos los ítems de verdad, y el síntoma es "no existe ese menú".
    texto = str(objetivo or "").strip().lower()
    menu = None
    if ">" in texto:
        pedido, _, resto = texto.partition(">")
        menu = _limpiar_etiqueta(pedido)
        texto = resto.strip()
    candidatos = [datos for datos in _recorrer_menus(barra)
                  if not datos.get("submenu") and datos.get("id") is not None]
    if menu is not None:
        candidatos = [d for d in candidatos
                      if _limpiar_etiqueta(str(d.get("camino", ""))
                                           .split(" > ", 1)[0]) == menu]
    for datos in candidatos:
        if datos["etiqueta"].strip().lower() == texto:
            return datos["id"], datos["etiqueta"]
    for datos in candidatos:
        if texto in datos["etiqueta"].strip().lower():
            return datos["id"], datos["etiqueta"]
    return None


def _iterar(ventana):
    yield ventana
    try:
        hijos = list(ventana.GetChildren())
    except Exception:
        hijos = []
    for h in hijos:
        yield from _iterar(h)


# La bandera 2 de `PrintWindow`: dibuja fuera de pantalla, con la ventana
# tapada y con la cortina de pantalla de NVDA, que ennegrece cualquier
# captura de la pantalla física. `ImageGrab` o `mss` no sirven acá.
PW_RENDERFULLCONTENT = 2


def _todos_los_libros(ventana):
    """Cada cuaderno de pestañas que cuelgue de esta ventana.

    Se reconoce igual que `_buscar_notebook`: por lo que sabe hacer y no
    por su clase, porque `wx.Notebook`, `wx.Listbook` y `wx.Choicebook` no
    comparten antepasado útil.
    """
    libros = []

    def _recorrer(v):
        if all(hasattr(v, m) for m in
               ("GetPageCount", "GetPageText", "SetSelection",
                "GetSelection")):
            if not any(b is v for b in libros):
                libros.append(v)
        try:
            hijos = list(v.GetChildren())
        except Exception:
            hijos = []
        for h in hijos:
            _recorrer(h)

    _recorrer(ventana)
    return libros


def _dibujar_ventana_a_rgb(ventana):
    """Dibuja la ventana con `PrintWindow` y devuelve `(ancho, alto, rgb)`.

    Los bytes salen BGRA de 32 bits de arriba hacia abajo y se pasan a RGB
    con `capturas.bgra_a_rgb`, que es lo que espera `wx.Image`. Libera
    siempre el bitmap y los DC, en un `finally`.
    """
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    hwnd = ventana.GetHandle()
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError("no se pudo leer el rectángulo de la ventana")
    ancho = rect.right - rect.left
    alto = rect.bottom - rect.top
    if ancho <= 0 or alto <= 0:
        raise RuntimeError(f"tamaño inválido: {ancho}x{alto}")

    class _Cabecera(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD),
                    ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]

    class _Info(ctypes.Structure):
        _fields_ = [("bmiHeader", _Cabecera),
                    ("bmiColors", wintypes.DWORD * 3)]

    hdc_pantalla = user32.GetDC(None)
    if not hdc_pantalla:
        raise RuntimeError("no se pudo pedir el DC de pantalla")
    try:
        hdc_mem = gdi32.CreateCompatibleDC(hdc_pantalla)
        if not hdc_mem:
            raise RuntimeError("no se pudo crear el DC compatible")
        try:
            hbmp = gdi32.CreateCompatibleBitmap(hdc_pantalla, ancho, alto)
            if not hbmp:
                raise RuntimeError("no se pudo crear el bitmap")
            try:
                anterior = gdi32.SelectObject(hdc_mem, hbmp)
                try:
                    if not user32.PrintWindow(hwnd, hdc_mem,
                                             PW_RENDERFULLCONTENT):
                        raise RuntimeError("PrintWindow devolvió falso")
                    info = _Info()
                    info.bmiHeader.biSize = ctypes.sizeof(_Cabecera)
                    info.bmiHeader.biWidth = ancho
                    # Alto negativo: de arriba hacia abajo.
                    info.bmiHeader.biHeight = -alto
                    info.bmiHeader.biPlanes = 1
                    info.bmiHeader.biBitCount = 32
                    info.bmiHeader.biCompression = 0
                    bufer = ctypes.create_string_buffer(ancho * alto * 4)
                    if not gdi32.GetDIBits(hdc_mem, hbmp, 0, alto, bufer,
                                           ctypes.byref(info), 0):
                        raise RuntimeError("GetDIBits devolvió cero")
                    import capturas
                    rgb = capturas.bgra_a_rgb(bufer.raw)
                finally:
                    gdi32.SelectObject(hdc_mem, anterior)
            finally:
                gdi32.DeleteObject(hbmp)
        finally:
            gdi32.DeleteDC(hdc_mem)
    finally:
        user32.ReleaseDC(None, hdc_pantalla)
    return ancho, alto, rgb


def _dejar_pintar(ventana) -> None:
    """Deja que la ventana se pinte antes de capturarla.

    Cede el bucle durante 400 ms: rondas de `SafeYield()` y `Update()`
    con `time.sleep(0.01)` entre ellas. Sin la espera real la captura
    sale en negro porque el pintado no alcanza a llegar.
    """
    import wx
    try:
        ventana.Refresh()
    except Exception:
        pass
    try:
        ventana.Update()
    except Exception:
        pass
    inicio = time.monotonic()
    while time.monotonic() - inicio < 0.4:
        try:
            wx.SafeYield()
        except Exception:
            break
        try:
            ventana.Update()
        except Exception:
            pass
        time.sleep(0.01)


def _guardar_png(ventana, ruta) -> tuple:
    """Guarda la ventana en `ruta` como PNG y devuelve su tamaño."""
    import wx
    ancho, alto, rgb = _dibujar_ventana_a_rgb(ventana)
    imagen = wx.Image(ancho, alto, bytes(rgb))
    if not imagen.IsOk():
        raise RuntimeError("la imagen quedó vacía")
    if not imagen.SaveFile(str(ruta), wx.BITMAP_TYPE_PNG):
        raise RuntimeError(f"no se pudo guardar {ruta}")
    return ancho, alto


# ── Servidor de órdenes ──────────────────────────────────────────────────────

class Sonda:
    def __init__(self, grabador: GrabadorAnuncios, ordenes: str, resultados: str):
        self.grabador = grabador
        self.ruta_ordenes = ordenes
        self.ruta_resultados = resultados
        self._leidas = 0
        self._lock = threading.Lock()

    def responder(self, id_orden, ok, datos=None, error=None):
        registro = {"id": id_orden, "ok": bool(ok)}
        if datos is not None:
            registro["datos"] = datos
        if error is not None:
            registro["error"] = str(error)
        with self._lock:
            with open(self.ruta_resultados, "a", encoding="utf-8") as f:
                f.write(json.dumps(registro, ensure_ascii=False) + "\n")
                f.flush()

    # Todo lo que toca la interfaz corre acá, en el hilo de la interfaz.
    def ejecutar(self, orden):
        import wx
        from bellbird.ui import gui

        op = orden.get("op")
        id_orden = orden.get("id")
        frame = getattr(gui, "_gui_frame", None)
        try:
            if op == "ping":
                self.responder(id_orden, True, {"listo": frame is not None})

            elif op == "frente":
                # Trae al frente la ventana que de verdad esta arriba, que con
                # un dialogo abierto NO es la principal. Levantar siempre el
                # frame le roba el foco al dialogo, y entonces el recorrido de
                # Tab dentro de Preferencias o del gestor de descargas daba dos
                # paradas en vez de veinte. Medido el 21/08/2026.
                #
                # El foco no se toca: moverlo al frame se lo quita al control
                # que lo tuviera, y sin foco dentro de un control los
                # aceleradores no llegan.
                if frame is None:
                    raise RuntimeError("todavía no hay ventana principal")
                # Ojo: `_ventana_por_titulo` devuelve el frame cuando no se
                # le pasa titulo, asi que preguntarle siempre nunca dejaba
                # elegir el dialogo.
                objetivo = None
                if orden.get("ventana"):
                    objetivo = self._ventana_por_titulo(orden["ventana"], frame)
                if objetivo is None:
                    objetivo = frame
                    for v in wx.GetTopLevelWindows():
                        try:
                            if v is frame or not v.IsShown():
                                continue
                        except Exception:
                            continue
                        objetivo = v
                        if getattr(v, "IsModal", lambda: False)():
                            break
                if objetivo is frame:
                    frame.Iconize(False)
                objetivo.Raise()
                # Windows solo deja pasar al frente al proceso que recibió la
                # última entrada. `IsActive` es lo que cree wx, no lo que tiene
                # Windows delante, así que se comprueba con
                # `GetForegroundWindow`. Si no está al frente, se desbloquea
                # con una pulsación de F24, que no usa ninguna aplicación ni
                # NVDA, y se repite el `Raise`. Nunca con Alt: un Alt sintético
                # abre la barra de menú y rompe los aceleradores. Medido el
                # 29/09/2026: sin esto la primera tecla de la corrida se pierde.
                import ctypes
                try:
                    al_frente_windows = (ctypes.windll.user32.GetForegroundWindow()
                                         == objetivo.GetHandle())
                except Exception:
                    al_frente_windows = False
                if not al_frente_windows:
                    try:
                        wx.UIActionSimulator().Char(wx.WXK_F24)
                    except Exception:
                        pass
                    try:
                        objetivo.Raise()
                    except Exception:
                        pass
                    try:
                        al_frente_windows = (
                            ctypes.windll.user32.GetForegroundWindow()
                            == objetivo.GetHandle())
                    except Exception:
                        al_frente_windows = False
                self.responder(id_orden, True, {
                    "activa": bool(objetivo.IsActive()) and al_frente_windows,
                    "frente_windows": bool(al_frente_windows),
                    "ventana": objetivo.GetTitle(),
                })

            elif op == "ventanas":
                abiertas = []
                for v in wx.GetTopLevelWindows():
                    try:
                        abiertas.append({
                            "titulo": v.GetTitle(),
                            "clase": v.__class__.__name__,
                            "visible": bool(v.IsShown()),
                            "modal": bool(getattr(v, "IsModal", lambda: False)()),
                        })
                    except Exception:
                        continue
                self.responder(id_orden, True, {"ventanas": abiertas})

            elif op == "hilos":
                # Los hilos vivos, por nombre. Sirve para atar un congelamiento
                # de la ventana a quien lo esta causando: si `ReproductorWarmup`
                # sigue vivo mientras los `ping` no vuelven, el precalentamiento
                # de libVLC y el bloqueo son el mismo suceso y no dos.
                self.responder(id_orden, True, {
                    "vivos": sorted(h.name for h in threading.enumerate()),
                })

            elif op == "llamar":
                # Llama a un método público del frame. Es lo que usa `main.py`
                # desde el hilo de captura, así que permite montar una sesión
                # entera sin red: conectado, tipo de vídeo, mensajes, todo.
                # Se llama desde el hilo de interfaz, igual que lo hace la
                # aplicación con `wx.CallAfter`.
                if frame is None:
                    raise RuntimeError("todavía no hay ventana principal")
                nombre = orden.get("metodo", "")
                if nombre.startswith("_") or not hasattr(frame, nombre):
                    raise RuntimeError(f"el frame no tiene método {nombre!r}")
                metodo = getattr(frame, nombre)
                if not callable(metodo):
                    raise RuntimeError(f"{nombre!r} no es un método")
                devuelto = metodo(*orden.get("args", []),
                                  **orden.get("kwargs", {}))
                try:
                    json.dumps(devuelto)
                except (TypeError, ValueError):
                    devuelto = repr(devuelto)
                self.responder(id_orden, True, {"devuelto": devuelto})

            elif op == "menus":
                if frame is None:
                    raise RuntimeError("todavía no hay ventana principal")
                self.responder(id_orden, True,
                               {"menus": _recorrer_menus(frame.GetMenuBar())})

            elif op == "menu_click":
                if frame is None:
                    raise RuntimeError("todavía no hay ventana principal")
                objetivo = (orden.get("etiqueta") or "").strip().lower()
                encontrado = _buscar_item_menu(frame.GetMenuBar(), objetivo)
                if encontrado is None:
                    raise RuntimeError(f"no hay ítem de menú {objetivo!r}")
                # Se contesta ANTES de disparar: si el ítem abre un diálogo
                # modal, el control no vuelve hasta que se cierre, y quien
                # espera la respuesta se quedaría colgado creyendo que falló.
                self.responder(id_orden, True, {"etiqueta": encontrado[1]})
                evento = wx.CommandEvent(wx.EVT_MENU.typeId, encontrado[0])
                evento.SetEventObject(frame)
                # Una casilla de menú hay que alternarla A MANO antes de
                # despachar. Windows lo hace solo cuando el usuario pulsa, pero
                # un CommandEvent construido acá no toca el estado, y entonces
                # `evento.IsChecked()` sale siempre falso: el manejador cree que
                # lo están APAGANDO aunque estuviera apagado. Se descubrió el
                # 25/08/2026 probando el panel de chat, que anunciaba «apagado»
                # cada vez que el banco intentaba encenderlo.
                item = frame.GetMenuBar().FindItemById(encontrado[0])
                if item is not None and item.IsCheckable():
                    nuevo = not item.IsChecked()
                    item.Check(nuevo)
                    evento.SetInt(1 if nuevo else 0)
                frame.GetEventHandler().ProcessEvent(evento)

            elif op == "arbol":
                objetivo = self._ventana_por_titulo(orden.get("ventana"), frame)
                if objetivo is None:
                    raise RuntimeError(f"no hay ventana {orden.get('ventana')!r}")
                self.responder(id_orden, True, {"controles": _arbol(objetivo)})

            elif op == "pestanas":
                # Sin esto solo se audita la pestana visible, porque una que no
                # esta seleccionada esconde a sus hijos y el servicio de
                # accesibilidad de Windows no los expone. Cambiar de pagina es
                # la unica forma de mirar el resto con el mismo rasero.
                objetivo = self._ventana_por_titulo(orden.get("ventana"), frame)
                if objetivo is None:
                    raise RuntimeError(f"no hay ventana {orden.get('ventana')!r}")
                libro = _buscar_notebook(objetivo)
                if libro is None:
                    raise RuntimeError("esa ventana no tiene ningun cuaderno "
                                       "de pestanas")
                indice = orden.get("indice")
                if indice is not None:
                    libro.SetSelection(int(indice))
                    wx.SafeYield()
                self.responder(id_orden, True, {
                    "paginas": [libro.GetPageText(i)
                                for i in range(libro.GetPageCount())],
                    "actual": libro.GetSelection(),
                })

            elif op == "foco":
                objetivo = self._ventana_por_titulo(orden.get("ventana"), frame)
                ctrl = _buscar_control(objetivo, orden.get("nombre", ""))
                if ctrl is None:
                    raise RuntimeError(f"no encontré {orden.get('nombre')!r}")
                ctrl.SetFocus()
                self.responder(id_orden, True, {"clase": ctrl.__class__.__name__})

            elif op == "navegar":
                # Recorre el orden de Tab por la cadena de foco de wx, sin
                # mandar una tecla al sistema. `UIActionSimulator` entrega la
                # pulsacion a la ventana que tenga el foco DEL ESCRITORIO, y
                # cuando el banco corre sin traer la app al frente esa ventana
                # es otra: el foco no se movia nunca y el recorrido daba
                # siempre una sola parada, en todos los dialogos.
                #
                # `Navigate` es la misma travesia que hace wx al recibir Tab,
                # asi que mide el orden real. Lo que NO cubre es el camino del
                # teclado del sistema operativo hasta la ventana.
                ctrl = wx.Window.FindFocus()
                objetivo = self._ventana_por_titulo(
                    orden.get("ventana"), frame)
                # Sin nombre de ventana, el recorrido se queda dentro de la que
                # ya tiene el foco. Salirse de ella es lo que hacia que el
                # informe nombrara controles de otro dialogo.
                if not orden.get("ventana") and ctrl is not None:
                    objetivo = wx.GetTopLevelParent(ctrl)
                # El foco puede estar en OTRA ventana: un dialogo que quedo
                # abierto, o la principal mientras se audita un dialogo. Si se
                # navega desde ahi se recorre el orden de Tab equivocado y el
                # informe nombra controles que no son de esta ventana.
                if objetivo is not None and (
                        ctrl is None or wx.GetTopLevelParent(ctrl) is not objetivo):
                    ctrl = None
                    for hijo in objetivo.GetChildren():
                        if hijo.IsShownOnScreen() and hijo.IsEnabled():
                            hijo.SetFocus()
                            ctrl = wx.Window.FindFocus() or hijo
                            break
                movido = False
                if ctrl is not None:
                    try:
                        movido = bool(ctrl.Navigate(wx.NavigationKeyEvent.IsForward))
                    except Exception:
                        movido = False
                # `Navigate` no baja dentro de la pagina de un cuaderno de
                # pestanas: recorre el nivel de arriba y salta al siguiente
                # hermano. Todo lo que vive en la pestana queda sin auditar, y
                # ahi estan los veinte y pico de botones de atajos de
                # Preferencias. Cuando el foco queda en un cuaderno, se entra a
                # mano en su pagina seleccionada.
                despues = wx.Window.FindFocus()
                if despues is not None and isinstance(despues, wx.Notebook):
                    pagina = despues.GetCurrentPage()
                    if pagina is not None:
                        for hijo in pagina.GetChildren():
                            if hijo.IsShownOnScreen() and hijo.IsEnabled() and                                     hijo.AcceptsFocus():
                                hijo.SetFocus()
                                movido = True
                                break
                self.responder(id_orden, True, {"movido": movido})

            elif op == "quien_tiene_foco":
                ctrl = wx.Window.FindFocus()
                self.responder(id_orden, True,
                               {"control": _describir(ctrl) if ctrl else None})

            elif op == "teclas":
                sim = wx.UIActionSimulator()
                for paso in orden.get("secuencia", []):
                    tecla = paso[0]
                    mods = paso[1] if len(paso) > 1 else []
                    codigo = _codigo_tecla(tecla)
                    # Char pulsa y suelta, modificadores incluidos. La
                    # documentación de wx avisa de que un modificador sin su
                    # KeyUp queda pegado en Windows, y Char lo evita.
                    sim.Char(codigo, _modificadores(mods))
                    wx.MilliSleep(40)
                self.responder(id_orden, True)

            elif op == "texto":
                ctrl = wx.Window.FindFocus()
                if ctrl is None:
                    raise RuntimeError("no hay nada con el foco")
                if hasattr(ctrl, "SetValue"):
                    ctrl.SetValue(orden.get("valor", ""))
                else:
                    raise RuntimeError(
                        f"{ctrl.__class__.__name__} no acepta texto")
                self.responder(id_orden, True)

            elif op == "pulsar":
                objetivo = self._ventana_por_titulo(orden.get("ventana"), frame)
                ctrl = _buscar_control(objetivo, orden.get("nombre", ""))
                if ctrl is None:
                    raise RuntimeError(f"no encontré {orden.get('nombre')!r}")
                # Como en `menu_click`: si el botón abre un diálogo modal, el
                # control no vuelve hasta que se cierre, y quien pide con
                # `responder_ya` se quedaría esperando una respuesta que ya no
                # puede llegar.
                if orden.get("responder_ya"):
                    self.responder(id_orden, True)
                evento = wx.CommandEvent(wx.EVT_BUTTON.typeId, ctrl.GetId())
                evento.SetEventObject(ctrl)
                ctrl.GetEventHandler().ProcessEvent(evento)
                if not orden.get("responder_ya"):
                    self.responder(id_orden, True)

            elif op == "elegir":
                # Elige la fila `indice` de una lista o un desplegable, como
                # con las flechas: la selecciona y dispara su evento.
                objetivo = self._ventana_por_titulo(orden.get("ventana"), frame)
                ctrl = _buscar_control(objetivo, orden.get("nombre", ""))
                if ctrl is None:
                    raise RuntimeError(f"no encontré {orden.get('nombre')!r}")
                if isinstance(ctrl, wx.ListBox):
                    tipo = wx.EVT_LISTBOX.typeId
                elif isinstance(ctrl, wx.Choice):
                    tipo = wx.EVT_CHOICE.typeId
                else:
                    raise RuntimeError(
                        f"{orden.get('nombre')!r} no es una lista ni un "
                        "desplegable")
                try:
                    indice = int(orden.get("indice"))
                except (TypeError, ValueError):
                    raise RuntimeError(
                        f"índice inválido: {orden.get('indice')!r}")
                if not 0 <= indice < ctrl.GetCount():
                    raise RuntimeError(
                        f"índice {indice} fuera de la lista "
                        f"{orden.get('nombre')!r}")
                ctrl.SetSelection(indice)
                evento = wx.CommandEvent(tipo, ctrl.GetId())
                evento.SetEventObject(ctrl)
                evento.SetInt(indice)
                ctrl.GetEventHandler().ProcessEvent(evento)
                self.responder(id_orden, True, {"indice": indice})

            elif op == "tecla_en":
                # Manda la tecla al control nombrado, no al foco del
                # escritorio: el evento pasa por el `EVT_KEY_DOWN` que la
                # ventana enganchó sobre ese control.
                objetivo = self._ventana_por_titulo(orden.get("ventana"), frame)
                ctrl = _buscar_control(objetivo, orden.get("nombre", ""))
                if ctrl is None:
                    raise RuntimeError(f"no encontré {orden.get('nombre')!r}")
                if orden.get("responder_ya"):
                    self.responder(id_orden, True)
                codigo = _codigo_tecla(orden.get("tecla", ""))
                mods = _modificadores(orden.get("modificadores"))
                evento = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
                evento.SetKeyCode(codigo)
                evento.SetControlDown(bool(mods & wx.MOD_CONTROL))
                evento.SetShiftDown(bool(mods & wx.MOD_SHIFT))
                evento.SetAltDown(bool(mods & wx.MOD_ALT))
                evento.SetEventObject(ctrl)
                ctrl.GetEventHandler().ProcessEvent(evento)
                if not orden.get("responder_ya"):
                    self.responder(id_orden, True)

            elif op == "menu_contextual":
                # Despliega el menú contextual real del control, pero
                # sustituye solo el dibujado para elegir una entrada. Así el
                # evento, el armado del menú y su despacho son los de la app.
                objetivo = self._ventana_por_titulo(orden.get("ventana"), frame)
                ctrl = _buscar_control(objetivo, orden.get("nombre", ""))
                if ctrl is None:
                    raise RuntimeError(f"no encontré {orden.get('nombre')!r}")
                estado = {"llamado": False, "falta": None,
                          "respondido": False, "error": None}

                def _elegir_en_menu(menu, *args, **kwargs):
                    # El error no puede escapar al manejador de wx, que lo
                    # imprime y sigue: la orden respondería `ok: true` con la
                    # entrada muerta. Se guarda y se levanta después, fuera de
                    # `ProcessEvent`, para que la orden falle de verdad.
                    try:
                        estado["llamado"] = True
                        partes = [parte.strip() for parte in
                                  str(orden.get("entrada") or "").split(">")]
                        actual = menu
                        elegido = None
                        etiquetas = []
                        for parte in partes:
                            buscada = _limpiar_etiqueta(parte)
                            elegido = None
                            etiquetas = []
                            for item in actual.GetMenuItems():
                                if item.IsSeparator():
                                    continue
                                etiqueta = item.GetItemLabelText()
                                etiquetas.append(etiqueta)
                                if _limpiar_etiqueta(etiqueta) == buscada:
                                    elegido = item
                                    break
                            if elegido is None:
                                estado["falta"] = etiquetas
                                return
                            submenu = elegido.GetSubMenu()
                            if submenu is not None:
                                actual = submenu
                        if (orden.get("responder_ya")
                                and not estado["respondido"]):
                            self.responder(id_orden, True)
                            estado["respondido"] = True
                        evento = wx.CommandEvent(
                            wx.EVT_MENU.typeId, elegido.GetId())
                        evento.SetEventObject(actual)
                        # `wx.Menu` es un `wx.EvtHandler`: despacha su
                        # `EVT_MENU` igual que el frame.
                        actual.ProcessEvent(evento)
                    except Exception as exc:
                        estado["error"] = repr(exc)

                ctrl.PopupMenu = _elegir_en_menu
                try:
                    evento = wx.ContextMenuEvent(
                        wx.EVT_CONTEXT_MENU.typeId, ctrl.GetId())
                    evento.SetEventObject(ctrl)
                    ctrl.GetEventHandler().ProcessEvent(evento)
                finally:
                    try:
                        del ctrl.PopupMenu
                    except AttributeError:
                        pass
                if estado["error"] is not None:
                    raise RuntimeError(
                        f"el menú de {orden.get('nombre')!r} falló al "
                        f"ejecutar «{orden.get('entrada')}»: "
                        f"{estado['error']}")
                if estado["falta"] is not None:
                    raise RuntimeError(
                        f"el menú de {orden.get('nombre')!r} no tiene "
                        f"«{orden.get('entrada')}»; ofrece: "
                        + ", ".join(repr(e) for e in estado["falta"]))
                if not estado["llamado"]:
                    raise RuntimeError(
                        "el menú contextual de "
                        f"{orden.get('nombre')!r} no se desplegó")
                if not estado["respondido"]:
                    self.responder(id_orden, True)

            elif op == "activar":
                # Activa la fila seleccionada de una lista, como Intro: en la
                # ventana Música dispara lo mismo que el doble clic.
                objetivo = self._ventana_por_titulo(orden.get("ventana"), frame)
                ctrl = _buscar_control(objetivo, orden.get("nombre", ""))
                if ctrl is None:
                    raise RuntimeError(f"no encontré {orden.get('nombre')!r}")
                if not isinstance(ctrl, wx.ListBox):
                    raise RuntimeError(
                        f"{orden.get('nombre')!r} no es una lista")
                # Como en `pulsar`: si abre un diálogo modal, el control no
                # vuelve hasta que se cierre.
                if orden.get("responder_ya"):
                    self.responder(id_orden, True)
                evento = wx.CommandEvent(wx.EVT_LISTBOX_DCLICK.typeId,
                                         ctrl.GetId())
                evento.SetEventObject(ctrl)
                try:
                    evento.SetInt(int(ctrl.GetSelection()))
                except Exception:
                    pass
                ctrl.GetEventHandler().ProcessEvent(evento)
                if not orden.get("responder_ya"):
                    self.responder(id_orden, True)

            elif op == "casilla":
                # Invierte o fija una casilla sin teclas del sistema. Como en
                # `menu_click`: un evento construido acá no toca el estado
                # solo, así que se cambia el valor a mano antes de despachar
                # su `wx.EVT_CHECKBOX`, igual que el ítem marcable.
                objetivo = self._ventana_por_titulo(orden.get("ventana"), frame)
                ctrl = _buscar_control(objetivo, orden.get("nombre", ""))
                if ctrl is None:
                    raise RuntimeError(f"no encontré {orden.get('nombre')!r}")
                if not isinstance(ctrl, wx.CheckBox):
                    raise RuntimeError(
                        f"{orden.get('nombre')!r} no es una casilla")
                if "valor" in orden and orden["valor"] is not None:
                    nuevo = bool(orden["valor"])
                else:
                    nuevo = not bool(ctrl.GetValue())
                ctrl.SetValue(nuevo)
                evento = wx.CommandEvent(wx.EVT_CHECKBOX.typeId, ctrl.GetId())
                evento.SetEventObject(ctrl)
                evento.SetInt(1 if nuevo else 0)
                ctrl.GetEventHandler().ProcessEvent(evento)
                self.responder(id_orden, True, {"valor": nuevo})

            elif op == "cerrar_ventana":
                objetivo = self._ventana_por_titulo(orden.get("ventana"), frame)
                if objetivo is None:
                    raise RuntimeError("no está esa ventana")
                # Por defecto se fuerza, como antes. Con `forzar=False` se
                # cierra sin forzar, que sí se puede vetar y pregunta.
                forzar = orden.get("forzar", True)
                objetivo.Close(bool(forzar))
                self.responder(id_orden, True)

            elif op == "reproductor":
                # Solo lectura: la posición que la aplicación le da al
                # usuario, no lo que anuncia. No toca nada del panel.
                if frame is None:
                    raise RuntimeError("todavía no hay ventana principal")
                panel = getattr(frame, "_rep_panel", None)
                if panel is None:
                    raise RuntimeError("no hay panel del reproductor")
                estado_fn = getattr(panel, "_estado_vlc_actual", None)
                directo_fn = getattr(panel, "_es_directo_actual", None)
                self.responder(id_orden, True, {
                    "pos_ms": getattr(panel, "_pos_ms", 0),
                    "dur_ms": getattr(panel, "_dur_ms", 0),
                    "estado": (estado_fn() if callable(estado_fn)
                               else "desconocido"),
                    "desfase": getattr(panel, "_relevo_desfase", 0),
                    "cargando": bool(getattr(panel, "_cargando", False)),
                    "directo": (bool(directo_fn()) if callable(directo_fn)
                                else False),
                })

            elif op == "directo_sin_imagen":
                # Abre la pregunta de directo huérfano con un id inventado.
                # Se responde ANTES de agendar: el diálogo es modal y la
                # respuesta se puede perder, igual que en `menu_click`.
                if frame is None:
                    raise RuntimeError("todavía no hay ventana principal")
                from bellbird.ui import gui_directo_huerfano
                self.responder(id_orden, True)
                wx.CallAfter(gui_directo_huerfano._preguntar, frame,
                             [("qa-sin-id", "Prueba del banco")])

            elif op == "salir":
                self.responder(id_orden, True)
                for v in list(wx.GetTopLevelWindows()):
                    try:    v.Destroy()
                    except Exception: pass

            elif op == "pid":
                # El pid del proceso de la aplicación, para el medidor de
                # sonido de `musica_real`. En Windows el `python.exe` del
                # `.venv` es un lanzador que crea otro proceso, así que el
                # pid del `Popen` no es el que suena.
                self.responder(id_orden, True, {"pid": os.getpid()})

            elif op == "capturar":
                # Guarda un PNG de una ventana con `PrintWindow`, sin mover
                # el foco ni mandar teclas. `ventana` es el título exacto o
                # "principal"; `base` la pone quien pide (ya trae el número,
                # el escenario y el título) y a cada página se le suma
                # `_pPP_pestana`. Cada página que falla queda anotada en su
                # entrada en vez de reventar la orden entera.
                import capturas
                pedida = str(orden.get("ventana") or "")
                carpeta = Path(orden.get("carpeta") or ".")
                base = str(orden.get("base") or "captura").strip()
                base = base or "captura"
                con_paginas = bool(orden.get("paginas"))
                if not pedida.strip() or pedida.strip().lower() == "principal":
                    objetivo = frame
                else:
                    objetivo = None
                    for v in wx.GetTopLevelWindows():
                        try:
                            if (v.GetTitle() or "") == pedida:
                                objetivo = v
                                break
                        except Exception:
                            continue
                if objetivo is None:
                    raise RuntimeError(f"no hay ventana {pedida!r}")
                carpeta.mkdir(parents=True, exist_ok=True)
                try:
                    titulo_real = objetivo.GetTitle() or pedida
                except Exception:
                    titulo_real = pedida
                try:
                    minimo = objetivo.GetMinSize()
                    minimo = [int(minimo.GetWidth()),
                              int(minimo.GetHeight())]
                except Exception:
                    minimo = None
                archivos = []

                def _una(ruta, pestana):
                    try:
                        _dejar_pintar(objetivo)
                        ancho, alto = _guardar_png(objetivo, ruta)
                        entrada = {
                            "archivo": Path(ruta).name,
                            "titulo": titulo_real, "pestana": pestana,
                            "ancho": ancho, "alto": alto, "minimo": minimo,
                        }
                        try:
                            imagen = wx.Image(str(ruta))
                            negra = capturas.es_todo_negro(imagen.GetData())
                        except Exception:
                            negra = False
                        if negra:
                            _dejar_pintar(objetivo)
                            ancho, alto = _guardar_png(objetivo, ruta)
                            entrada["ancho"] = ancho
                            entrada["alto"] = alto
                            try:
                                imagen = wx.Image(str(ruta))
                                if capturas.es_todo_negro(imagen.GetData()):
                                    entrada["fallo"] = ("la captura salió "
                                                        "en negro")
                            except Exception:
                                pass
                        archivos.append(entrada)
                    except Exception as exc:
                        archivos.append({
                            "archivo": None,
                            "titulo": titulo_real, "pestana": pestana,
                            "ancho": 0, "alto": 0, "minimo": minimo,
                            "fallo": str(exc),
                        })

                libros = (_todos_los_libros(objetivo) if con_paginas
                          else [])
                if not libros:
                    _una(carpeta / f"{base}.png", "")
                else:
                    for libro in libros:
                        try:
                            anterior = libro.GetSelection()
                        except Exception:
                            anterior = 0
                        try:
                            for i in range(libro.GetPageCount()):
                                try:
                                    pest = libro.GetPageText(i)
                                except Exception:
                                    pest = f"página {i + 1}"
                                libro.SetSelection(i)
                                _una(carpeta / (capturas.nombre_pagina(
                                    base, i + 1, pest) + ".png"), pest)
                        finally:
                            try:
                                libro.SetSelection(anterior)
                                objetivo.Update()
                            except Exception:
                                pass
                self.responder(id_orden, True, {"archivos": archivos})

            else:
                raise RuntimeError(f"orden desconocida: {op!r}")
        except Exception as exc:
            self.responder(id_orden, False, error=repr(exc))

    def _ventana_por_titulo(self, titulo, frame):
        import wx
        if not titulo:
            return frame
        objetivo = titulo.strip().lower()
        for v in wx.GetTopLevelWindows():
            try:
                if objetivo in (v.GetTitle() or "").lower():
                    return v
            except Exception:
                continue
        return None

    def vigilar(self):
        """Hilo de fondo: lee órdenes nuevas y las manda al hilo de interfaz."""
        import wx
        while True:
            try:
                if os.path.exists(self.ruta_ordenes):
                    with open(self.ruta_ordenes, encoding="utf-8") as f:
                        lineas = f.read().splitlines()
                    while self._leidas < len(lineas):
                        cruda = lineas[self._leidas].strip()
                        self._leidas += 1
                        if not cruda:
                            continue
                        try:
                            orden = json.loads(cruda)
                        except ValueError:
                            continue
                        wx.CallAfter(self.ejecutar, orden)
            except Exception:
                pass
            time.sleep(0.05)


def instalar() -> str:
    """Silencia la voz, abre el canal de órdenes, y deja constancia de ambos."""
    ruta = os.environ.get(VAR_DESTINO)
    if not ruta:
        raise RuntimeError(
            f"Falta la variable {VAR_DESTINO} con la ruta de la grabación")

    from bellbird.ui import gui
    from bellbird.ui import accesibilidad
    grabador = GrabadorAnuncios(ruta)

    # No alcanza con asignar `accesibilidad._lector` acá: `iniciar_gui` llama a
    # `_lector_init()` por dentro, después, y vuelve a poner el objeto real
    # encima. Costó una corrida entera creer que la sonda estaba puesta cuando
    # no lo estaba, y peor: creer que la aplicación no iba a hablar cuando sí.
    if not hasattr(gui, "_lector_init") or not hasattr(accesibilidad, "_lector") \
            or not hasattr(accesibilidad, "_lector_init"):
        raise RuntimeError(
            "gui o accesibilidad ya no tienen _lector_init: la sonda quedó vieja y no puede "
            "garantizar que la aplicación no hable. Revisala antes de seguir.")

    def _init_grabando():
        accesibilidad._lector = grabador
        grabador._apuntar("sonda", "la aplicación pidió inicializar la voz y "
                                   "se le dio el grabador")

    gui._lector_init = _init_grabando
    accesibilidad._lector_init = _init_grabando
    accesibilidad._lector = grabador
    grabador._apuntar("sonda", "grabador instalado antes de arrancar")

    try:
        gui._snd.silenciar_todo(True)
    except Exception:
        pass

    ordenes = os.environ.get(VAR_ORDENES)
    resultados = os.environ.get(VAR_RESULTADOS)
    if ordenes and resultados:
        sonda = Sonda(grabador, ordenes, resultados)
        hilo = threading.Thread(target=sonda.vigilar, daemon=True,
                                name="QA-Sonda")
        hilo.start()
        grabador._apuntar("sonda", "canal de órdenes abierto")

    return ruta


def arrancar_aplicacion(ruta_main: str) -> None:
    """Instala la sonda y cede el control a `main.py` como si nada."""
    instalar()
    import runpy
    runpy.run_path(ruta_main, run_name="__main__")
