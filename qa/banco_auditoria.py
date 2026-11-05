"""Cómo se revisa una ventana con UI Automation.

Los nombres accesibles, el recorrido de Tab, el recuento de roles que expone
Windows, la espera de habilitados y la auditoría completa de un diálogo.
"""

from __future__ import annotations

import sys
import time

from banco_app import (
    Aplicacion, Resultado, _ESCENARIO_EN_CURSO, _TIEMPOS, _candidatas_uia,
)

# ── Comprobaciones ───────────────────────────────────────────────────────────

CLASES_INTERACTIVAS = {
    "Button", "BitmapButton", "TextCtrl", "Choice", "ComboBox", "ListBox",
    "ListCtrl", "CheckBox", "RadioButton", "RadioBox", "Slider",
    "DirPickerCtrl", "FilePickerCtrl", "SpinCtrl", "Notebook",
}

# wx le pone a cada control un nombre por defecto según su clase. Que exista no
# quiere decir que alguien lo haya nombrado, así que estos no cuentan.
NOMBRES_POR_DEFECTO = {
    "", "button", "text", "textctrl", "choice", "listctrl", "listbox",
    "checkbox", "panel", "staticbox", "dirpicker", "filepicker", "combobox",
    "radiobutton", "radiobox", "slider", "spinctrl", "notebook", "control",
}


def parece_clave_cruda(texto: str) -> bool:
    """¿Esto es lenguaje humano o una clave del `config.ini` que se escapó?

    Distinción pagada el 21/08/2026: una mutación cambió la etiqueta de un
    botón de atajos por su clave de configuración, `descargas_abrir`, y ni la
    suite ni este banco dijeron nada. El control tenía nombre, y el banco solo
    comprobaba que lo tuviera. Un lector de pantalla lee «descargas guion bajo
    abrir», que no es un nombre: es un identificador de programador.
    """
    t = (texto or "").strip()
    # Los botones de atajo se llaman «accion: Ctrl+S», asi que la parte que
    # tiene que ser legible es la de antes de los dos puntos.
    if ":" in t:
        t = t.split(":", 1)[0].strip()
    if not t or " " in t:
        return False
    return "_" in t and t == t.lower() and t.replace("_", "").isalnum()


def revisar_nombres(controles: list[dict], res: Resultado, donde: str) -> None:
    """Un control interactivo sin nombre ni etiqueta es mudo para el lector."""
    mudos = []
    crudos = []
    interactivos = 0
    for c in controles:
        if c.get("clase") not in CLASES_INTERACTIVAS or not c.get("visible"):
            continue
        interactivos += 1
        nombre = (c.get("nombre") or "").strip()
        etiqueta = (c.get("etiqueta") or "").strip()
        if nombre.lower() in NOMBRES_POR_DEFECTO and not etiqueta:
            mudos.append(c)
        # Solo se juzga el texto que de verdad se anuncia. El `name=` interno
        # de wx puede ser un identificador (`Atajo_silenciar_sonidos`) sin que
        # eso llegue al lector, y darlo por defecto llena el informe de ruido.
        elif parece_clave_cruda(etiqueta or nombre):
            crudos.append((c, etiqueta or nombre))
    for c in mudos:
        res.fallo(f"{donde}: un {c['clase']} no tiene nombre ni etiqueta")
    for c, texto in crudos:
        res.fallo(f"{donde}: un {c['clase']} se llama «{texto}», que parece "
                  "una clave de configuración y no una frase")
    if not mudos and not crudos:
        res.nota(f"{donde}: {interactivos} controles interactivos, "
                 "todos con nombre o etiqueta")


# Cuanto se le concede a un dialogo que consulta algo de fuera para volverse
# navegable entero. Medido: el de Transmision con OBS abierto tarda menos de
# dos segundos; el margen es para una maquina cargada.
SEGUNDOS_TAB_COMPLETO = 12.0

# La ventana Transmision tiene 28 controles con OBS abierto y crece con cada
# funcion nueva, asi que el tope de paradas necesita aire de sobra.
VUELTAS_TAB_TRANSMISION = 40


def recorrer_tab(app: Aplicacion, res: Resultado, donde: str,
                 vueltas: int = 20, ventana: str | None = None) -> list[str]:
    """Pulsa Tab y anota dónde cae el foco, preguntándoselo a wx."""
    inicio = time.monotonic()
    try:
        visto: list[str] = []
        for _ in range(vueltas):
            ctrl = app.foco()
            if ctrl:
                nombre = (ctrl.get("nombre") or "").strip()
                etiqueta = (ctrl.get("etiqueta") or "").strip().replace("&", "")
                legible = etiqueta or nombre
                if nombre.lower() in NOMBRES_POR_DEFECTO and not etiqueta:
                    legible = "(SIN NOMBRE)"
                etiq = f"{ctrl['clase']}: {legible}"
                if etiq not in visto:
                    visto.append(etiq)
            app.navegar(ventana)
        for v in visto:
            if "(SIN NOMBRE)" in v:
                res.fallo(f"{donde}: el foco cae en algo sin nombre, {v}")
        if not visto:
            res.fallo(f"{donde}: Tab no movió el foco a ningún sitio legible")
        return visto
    finally:
        _TIEMPOS.append({
            "escenario": _ESCENARIO_EN_CURSO,
            "orden": f"tab: {donde}",
            "segundos": time.monotonic() - inicio,
            "tipo": "tab",
            "inicio": inicio,
        })


def _con_tope(funcion, segundos: float, por_defecto):
    """Corre algo en un hilo aparte y se rinde si tarda de más.

    Hace falta porque una llamada de UI Automation a un proceso que no responde
    no tiene tope propio y no se puede interrumpir. El hilo queda colgado, pero
    es demonio y no impide salir: peor es que se cuelgue la corrida entera.
    """
    import threading
    resultado = [por_defecto]
    inicio = time.monotonic()

    def _correr():
        try:
            resultado[0] = funcion()
        except Exception:
            pass

    hilo = threading.Thread(target=_correr, daemon=True)
    hilo.start()
    hilo.join(segundos)
    nombre = (getattr(funcion, "__qualname__", "")
              or getattr(funcion, "__name__", ""))
    if getattr(funcion, "__name__", "") == "<lambda>":
        nombre = sys._getframe(1).f_code.co_qualname
    _TIEMPOS.append({
        "escenario": _ESCENARIO_EN_CURSO,
        "orden": nombre,
        "segundos": time.monotonic() - inicio,
        "tipo": "uia",
        "inicio": inicio,
    })
    return resultado[0]


def roles_segun_windows(titulo: str, tope: float = 20.0) -> dict[str, int]:
    """Qué roles expone esta ventana al servicio de accesibilidad de Windows.

    Es la única comprobación que necesita mirar desde fuera, y por eso usa
    pywinauto: desde dentro wx siempre dirá `CheckBox`, aunque Windows la esté
    exponiendo como botón. La diferencia es justo lo que discute `AGENTS.md`.
    """
    try:
        from pywinauto import Desktop
    except ImportError:
        return {}
    return _con_tope(lambda: _roles_sin_tope(titulo, Desktop), tope, {})


def _ventana_por_titulo(Desktop, objetivo):
    """La ventana cuyo titulo contiene `objetivo`, este donde este.

    Se mira primero entre las ventanas de raiz. Si no aparece ahi, se busca
    DENTRO de la ventana de la aplicacion, y esa segunda vuelta es la que hace
    falta de verdad: medido el 26/08/2026, el dialogo de Preferencias NO cuelga
    de la raiz sino de la ventana principal, porque un `wx.Dialog` modal tiene
    dueno y Windows lo expone como descendiente suyo.

    Ese detalle dejo muda la comprobacion de owner-drawn durante un dia entero:
    devolvia vacio y el banco lo anotaba como «no se pudo leer el arbol», que
    parece un problema del entorno y no una comprobacion que no se hace.

    La segunda vuelta se limita a la ventana de la aplicacion a proposito.
    Recorrer los descendientes de CADA ventana del escritorio tardo 72,4
    segundos contra 0,8, porque UI Automation pregunta a cada proceso ajeno y
    espera a su bucle de mensajes. Dentro de la propia aplicacion son 0,2.
    """
    for w in _candidatas_uia(Desktop):
        try:
            if (w.element_info.control_type in ("Window", "Pane")
                    and objetivo in (w.element_info.name or "").lower()):
                return w
        except Exception:
            continue
    return None


def _roles_sin_tope(titulo, Desktop) -> dict[str, int]:
    cuenta: dict[str, int] = {}
    _ULTIMOS_NOMBRES.clear()
    try:
        w = _ventana_por_titulo(Desktop, titulo.lower())
        if w is None:
            return cuenta
        for d in w.descendants():
            try:
                rol = d.element_info.control_type
                nombre = (d.element_info.name or "").strip()
            except Exception:
                continue
            cuenta[rol] = cuenta.get(rol, 0) + 1
            _ULTIMOS_NOMBRES.setdefault(rol, []).append(nombre)
    except Exception:
        pass
    return cuenta


# Se guardan los nombres del ultimo vistazo para poder decir QUE control es el
# que no cuadra, en vez de solo cuantos faltan. Un recuento sin nombre obliga a
# adivinar, y adivinar es como se producen los hallazgos falsos.
_ULTIMOS_NOMBRES: dict[str, list[str]] = {}


def nombres_segun_windows(rol: str) -> list[str]:
    return list(_ULTIMOS_NOMBRES.get(rol, []))


def faltan_habilitados(controles: list[dict],
                        nombres: tuple[str, ...]) -> list[str]:
    """Los `nombres` sin ningún control visible y habilitado que los mencione.

    Es la misma regla de `esperados`, pero exigiendo habilitado: un control
    deshabilitado no entra en el orden de Tab y no cuenta como listo.
    """
    faltan = []
    for e in nombres:
        aguja = e.lower()
        listo = False
        for c in controles:
            junto = ((c.get("nombre") or "") + " "
                     + (c.get("etiqueta") or "")).replace("&", "").lower()
            if (aguja in junto and c.get("habilitado", True)
                    and c.get("visible", True)):
                listo = True
                break
        if not listo:
            faltan.append(e)
    return faltan


def auditar_dialogo(app: Aplicacion, res: Resultado, etiqueta_menu: str,
                    titulo: str, vueltas_tab: int = 16,
                    esperados: tuple[str, ...] = (),
                    esperados_en_tab: tuple[str, ...] = (),
                    esperar_habilitados: tuple[str, ...] = (),
                    segundos_espera_habilitados: float = 20.0,
                    pestana: str | None = None) -> bool:
    """Abre un diálogo desde el menú, lo audita entero y lo cierra.

    Con `pestana`, elige esa página antes de recorrer el Tab, porque una
    pestaña que no está seleccionada esconde a sus hijos.
    """
    app.pedir("frente")
    try:
        app.abrir_por_menu(etiqueta_menu)
    except Exception as exc:
        res.fallo(f"{titulo}: no se pudo disparar «{etiqueta_menu}», {exc}")
        return False

    dlg = app.esperar_ventana(titulo, segundos=15)
    if dlg is None:
        res.fallo(f"{titulo}: el menú no abrió ninguna ventana con ese título")
        return False
    res.nota(f"{titulo}: abre desde «{etiqueta_menu}», clase {dlg['clase']}")

    if pestana is not None:
        paginas = app.pedir("pestanas", ventana=titulo).get(
            "datos", {}).get("paginas", [])
        indice = next((i for i, pagina in enumerate(paginas)
                       if pagina.strip().lower() == pestana.lower()), None)
        if indice is None:
            res.fallo(f"{titulo}: no hay pestaña «{pestana}»")
        else:
            app.pedir("pestanas", ventana=titulo, indice=indice)

    # Un diálogo que consulta algo de fuera nace con sus controles
    # deshabilitados y los habilita cuando la carga inicial termina. Si el
    # Tab se recorre antes, mide la pantalla de espera.
    if esperar_habilitados:
        limite_espera = time.monotonic() + segundos_espera_habilitados
        pendientes = list(esperar_habilitados)
        while True:
            try:
                pendientes = faltan_habilitados(app.arbol(titulo),
                                                esperar_habilitados)
            except Exception:
                pendientes = list(esperar_habilitados)
            if not pendientes or time.monotonic() >= limite_espera:
                break
            time.sleep(0.5)
        if not pendientes:
            res.nota(f"{titulo}: la carga inicial terminó, "
                     f"«{esperar_habilitados[0]}» está habilitado")
        else:
            res.nota(f"{titulo}: «{pendientes[0]}» no se habilitó en "
                     f"{segundos_espera_habilitados:.0f} segundos, "
                     "se audita igual")

    controles = app.arbol(titulo)
    revisar_nombres(controles, res, titulo)

    if esperados:
        # Se quita la marca de mnemonico: una etiqueta como "Aplicar &tamano"
        # no contiene "aplicar tamano", y eso daba fallos que no existian.
        juntos = " ".join(
            ((c.get("nombre") or "") + " " + (c.get("etiqueta") or ""))
            for c in controles).replace("&", "").lower()
        for e in esperados:
            if e.lower() not in juntos:
                res.fallo(f"{titulo}: no aparece nada llamado «{e}»")

    # `esperados` busca el texto en TODO el dialogo, asi que un rotulo o el
    # cuadro de estado pueden hacerlo pasar aunque el control no exista. Lo que
    # se pide aca tiene que estar en una parada de Tab, que es lo unico que
    # demuestra que hay un control alcanzable, con nombre y habilitado.
    #
    # Se reintenta con plazo porque un dialogo que consulta algo de fuera nace
    # con sus controles deshabilitados a proposito, y deshabilitado no entra en
    # el orden de Tab. Auditar en el primer instante mide la pantalla de espera,
    # no el dialogo. Lo que se exige entonces es que se vuelva navegable ANTES
    # del plazo, que es la propiedad que le importa a quien no ve.
    limite = time.monotonic() + SEGUNDOS_TAB_COMPLETO
    while True:
        orden = recorrer_tab(app, res, titulo, vueltas=vueltas_tab,
                             ventana=titulo)
        faltan = [e for e in esperados_en_tab
                  if e.lower() not in " ".join(orden).replace("&", "").lower()]
        if not faltan or time.monotonic() >= limite:
            break
        time.sleep(0.5)
    res.nota(f"{titulo}, orden de Tab, {len(orden)} paradas: "
             + " > ".join(orden))
    for e in faltan if esperados_en_tab else ():
        res.fallo(f"{titulo}: «{e}» no aparece en el orden de Tab "
                  f"en {SEGUNDOS_TAB_COMPLETO:.0f} segundos")

    app.pedir("cerrar_ventana", ventana=titulo)
    if app.esperar_ventana(titulo, segundos=4) is not None:
        res.fallo(f"{titulo}: el diálogo no cerró")
    return True
