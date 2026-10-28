"""Vuelca la barra de menús real y comprueba sus convenciones.

La parte pura no importa wx: una Entrada por elemento del menú y una
función por regla que recibe la lista y devuelve las faltas como textos.
La construcción crea un wx.App sin mostrar ninguna ventana, llama a
gui_menu.construir_menu con un doble de frame y recorre el wx.MenuBar
real. No cambia ningún texto de la app: solo informa.

Se corre así, en la PC donde no molesta a NVDA:

    python scripts/convenciones_comandos.py
"""

from __future__ import annotations

from typing import NamedTuple


class Entrada(NamedTuple):
    """Un elemento de la barra: ruta de menús que lo contienen, etiqueta
    visible sin & ni tecla, letra de atajo, tecla tras el tabulador, tipo
    (menu, submenu, normal, casilla, radio) y nivel (0 barra, 1 menú,
    2 submenú)."""

    ruta: tuple
    etiqueta: str
    letra: str
    tecla: str
    tipo: str
    nivel: int


PERMITIDAS = ("YouTube", "TikTok", "OBS", "IA", "API", "VLC", "NVDA",
              "Bellbird", "ElevenLabs", "SAPI5", "yt-dlp", "Windows",
              "TTS")

TECLAS_INGLES = ("Left", "Right", "Up", "Down", "Home", "End", "PageUp",
                 "PageDown", "Delete", "Del", "Insert", "Space", "Back",
                 "Escape", "Esc", "Enter", "Return", "Tab")

ARTICULOS = ("el", "la", "los", "las", "un", "una", "unos", "unas",
             "al", "del")

_PUNTUACION = "«»\"'()[]{}:;,.!?…—–-"


def _palabra_limpia(palabra: str) -> str:
    return palabra.strip(_PUNTUACION)


def _empieza_con_mayuscula(palabra: str) -> bool:
    limpio = _palabra_limpia(palabra)
    if not limpio or limpio in PERMITIDAS:
        return False
    primero = limpio[0]
    return primero.isalpha() and primero.isupper()


def faltas_mayusculas(entradas: list) -> list:
    """Mayúscula solo en la primera palabra, salvo siglas permitidas."""
    faltas = []
    for entrada in entradas:
        if entrada.tipo not in ("menu", "submenu", "normal", "casilla",
                                "radio"):
            continue
        palabras = entrada.etiqueta.replace("…", " ").split()
        for palabra in palabras[1:]:
            limpio = _palabra_limpia(palabra)
            if not limpio or limpio[0].isdigit() or not limpio[0].isalpha():
                continue
            if _empieza_con_mayuscula(palabra):
                faltas.append(
                    f"Mayúscula a mitad de rótulo en "
                    f"«{entrada.etiqueta}»: «{limpio}»")
                break
    return faltas


def _nombre_de_padre(ruta: tuple) -> str:
    if not ruta:
        return "la barra"
    return f"«{ruta[-1]}»"


def faltas_letras_repetidas(entradas: list) -> list:
    """Ninguna letra de atajo repetida entre hermanos de un mismo menú,
    ni entre los títulos de la barra, sin distinguir mayúsculas."""
    faltas = []
    grupos: dict = {}
    for entrada in entradas:
        if entrada.tipo not in ("menu", "submenu", "normal", "casilla",
                                "radio"):
            continue
        if not entrada.letra:
            continue
        grupos.setdefault((entrada.ruta, entrada.nivel), []).append(entrada)
    for (ruta, _nivel), hermanos in grupos.items():
        vistas: dict = {}
        for entrada in hermanos:
            clave = entrada.letra.lower()
            if clave in vistas:
                primera = vistas[clave]
                faltas.append(
                    f"Letra «{clave}» repetida en {_nombre_de_padre(ruta)}: "
                    f"«{primera.etiqueta}» y «{entrada.etiqueta}»")
            else:
                vistas[clave] = entrada
    return faltas


def faltas_profundidad(entradas: list) -> list:
    """Un solo nivel de submenú: barra, menú y submenú, nada más hondo."""
    faltas = []
    for entrada in entradas:
        if entrada.nivel > 2:
            ruta = " > ".join(entrada.ruta)
            faltas.append(
                f"Submenú demasiado hondo en «{ruta}»: "
                f"«{entrada.etiqueta}»")
    return faltas


def faltas_shift(entradas: list) -> list:
    """Nombres de teclas como en Windows en español: falta si dice Shift."""
    faltas = []
    for entrada in entradas:
        if entrada.tipo not in ("normal", "casilla", "radio"):
            continue
        if "Shift" in entrada.tecla:
            faltas.append(f"«Shift» en la tecla de «{entrada.etiqueta}»")
    return faltas


def _resto_activar(etiqueta: str) -> str | None:
    for verbo in ("Activar ", "Desactivar "):
        if etiqueta.startswith(verbo):
            return etiqueta[len(verbo):]
    return None


def faltas_activar_desactivar(entradas: list) -> list:
    """Lo que se activa y desactiva es una casilla: falta si dos hermanos
    empiezan con Activar y Desactivar seguidos de lo mismo."""
    faltas = []
    grupos: dict = {}
    for entrada in entradas:
        if entrada.tipo not in ("normal", "casilla", "radio"):
            continue
        grupos.setdefault((entrada.ruta, entrada.nivel), []).append(entrada)
    for (ruta, _nivel), hermanos in grupos.items():
        restos: dict = {}
        for entrada in hermanos:
            resto = _resto_activar(entrada.etiqueta)
            if resto is None:
                continue
            verbo = "Activar" if entrada.etiqueta.startswith("Activar ") else "Desactivar"
            restos.setdefault(resto, {})[verbo] = entrada.etiqueta
        for resto, verbos in restos.items():
            if "Activar" in verbos and "Desactivar" in verbos:
                faltas.append(
                    f"«Activar {resto}» y «Desactivar {resto}» "
                    f"conviven en {_nombre_de_padre(ruta)}")
    return faltas


def faltas_teclas_ingles(entradas: list) -> list:
    """Nombres de teclas como en Windows en español: falta cada nombre
    en inglés que aparece en la tecla del comando."""
    faltas = []
    for entrada in entradas:
        if entrada.tipo not in ("normal", "casilla", "radio"):
            continue
        for parte in entrada.tecla.split("+"):
            if parte.strip() in TECLAS_INGLES:
                faltas.append(f"«{parte.strip()}» en la tecla de "
                              f"«{entrada.etiqueta}»")
    return faltas


def todas_las_faltas(entradas: list) -> list:
    """Todas las faltas en orden fijo: mayúsculas, letras, profundidad,
    Shift, parejas de activar y desactivar y teclas en inglés."""
    return (faltas_mayusculas(entradas)
            + faltas_letras_repetidas(entradas)
            + faltas_profundidad(entradas)
            + faltas_shift(entradas)
            + faltas_activar_desactivar(entradas)
            + faltas_teclas_ingles(entradas))


def informativos_puntos(entradas: list) -> list:
    """Comandos con puntos suspensivos: lista informativa, no es falta."""
    avisos = []
    for entrada in entradas:
        if entrada.tipo not in ("normal", "casilla", "radio"):
            continue
        if "…" in entrada.etiqueta or "..." in entrada.etiqueta:
            avisos.append(f"«{entrada.etiqueta}» lleva puntos suspensivos")
    return avisos


def informativos_largos(entradas: list) -> list:
    """Rótulos de más de tres palabras, sin contar artículos ni el texto
    tras el tabulador: lista informativa, no es falta."""
    avisos = []
    for entrada in entradas:
        if entrada.tipo not in ("menu", "submenu", "normal", "casilla",
                                "radio"):
            continue
        palabras = [p for p in entrada.etiqueta.replace("…", " ").split()
                    if p.lower().strip(_PUNTUACION) not in ARTICULOS]
        if len(palabras) > 3:
            avisos.append(
                f"«{entrada.etiqueta}» tiene {len(palabras)} palabras")
    return avisos


def _extraer_letra(crudo: str) -> str:
    """Letra tras el primer & simple: && es un & literal, no un atajo."""
    visible = crudo.split("\t")[0]
    for i, caracter in enumerate(visible):
        if caracter == "&":
            siguiente = visible[i + 1:i + 2]
            if siguiente == "&":
                continue
            return siguiente
    return ""


def _extraer_tecla(crudo: str) -> str:
    partes = crudo.split("\t")
    return partes[1] if len(partes) > 1 else ""


def _visible(crudo: str) -> str:
    return crudo.split("\t")[0].replace("&&", "&").replace("&", "")


def _tipo_desde_kind(kind) -> str:
    import wx

    if kind == wx.ITEM_CHECK:
        return "casilla"
    if kind == wx.ITEM_RADIO:
        return "radio"
    return "normal"


def _recorrer(menu, ruta: tuple, nivel: int, entradas: list) -> None:
    for item in menu.GetMenuItems():
        if item.IsSeparator():
            continue
        crudo = item.GetItemLabel()
        if item.IsSubMenu():
            etiqueta = _visible(crudo)
            entradas.append(Entrada(tuple(ruta), etiqueta,
                                    _extraer_letra(crudo), "", "submenu",
                                    nivel))
            _recorrer(item.GetSubMenu(), tuple(ruta) + (etiqueta,),
                      nivel + 1, entradas)
        else:
            entradas.append(Entrada(
                tuple(ruta), _visible(crudo), _extraer_letra(crudo),
                _extraer_tecla(crudo), _tipo_desde_kind(item.GetKind()),
                nivel))


class _DobleFrame:
    """Doble de frame para construir_menu: delega Bind y la barra en un
    wx.Frame oculto y responde a todo lo demás sin la ventana principal."""

    def __init__(self, real, config: dict, accel) -> None:
        self._real = real
        self._config = config
        self._accel = accel

    def __getattr__(self, nombre: str):
        return lambda *args, **kwargs: None

    def GetMenuBar(self):
        return self._real.GetMenuBar()

    def SetMenuBar(self, barra) -> None:
        self._real.SetMenuBar(barra)

    def Bind(self, *args, **kwargs):
        return self._real.Bind(*args, **kwargs)

    def Destroy(self) -> None:
        self._real.Destroy()

    def _bind_menu(self, item, fn, *args) -> None:
        import wx

        self._real.Bind(wx.EVT_MENU,
                        lambda e: wx.CallAfter(fn, *args), item)

    def _sincronizar_pausa(self) -> None:
        return None


def construir_entradas_reales() -> list:
    """Construye el menú real con gui_menu y devuelve sus entradas."""
    import wx

    from ytchat.core.config import todos_los_atajos_default
    from ytchat.ui import gui_menu
    from ytchat.ui.gui import _fmt_accel

    app = wx.App(False)
    defaults = todos_los_atajos_default()
    frame = _DobleFrame(
        wx.Frame(None),
        {"mostrar_botones_reproductor": True,
         "avisar_sobrecarga": True,
         "grabar_al_transmitir": False,
         "musica_aleatorio": False},
        lambda accion: ("\t" + _fmt_accel(defaults[accion])
                        if defaults.get(accion) else ""))
    gui_menu.construir_menu(frame)
    barra = frame.GetMenuBar()
    entradas: list = []
    for i in range(barra.GetMenuCount()):
        titulo = _visible(barra.GetMenuLabel(i))
        entradas.append(Entrada((), titulo, _extraer_letra(
            barra.GetMenuLabel(i)), "", "menu", 0))
        _recorrer(barra.GetMenu(i), (titulo,), 1, entradas)
    frame.Destroy()
    app.Destroy()
    return entradas


def imprimir_menu(entradas: list) -> None:
    """Una línea por elemento, con cuatro espacios por nivel."""
    for entrada in entradas:
        print("    " * entrada.nivel
              + f"{entrada.etiqueta} [{entrada.tipo}]"
              + (f" <{entrada.letra}>" if entrada.letra else "")
              + (f" ({entrada.tecla})" if entrada.tecla else ""))


def informar(entradas: list) -> None:
    """Imprime las faltas de cada regla y las dos listas informativas."""
    grupos = [("Mayúsculas", faltas_mayusculas(entradas)),
              ("Letras repetidas", faltas_letras_repetidas(entradas)),
              ("Profundidad", faltas_profundidad(entradas)),
              ("Shift", faltas_shift(entradas)),
              ("Activar y desactivar",
               faltas_activar_desactivar(entradas)),
              ("Teclas en inglés", faltas_teclas_ingles(entradas))]
    for titulo, faltas in grupos:
        print(f"{titulo}: {len(faltas)}")
        for falta in faltas:
            print(f"    {falta}")
    puntos = informativos_puntos(entradas)
    print(f"Puntos suspensivos: {len(puntos)}")
    for aviso in puntos:
        print(f"    {aviso}")
    largos = informativos_largos(entradas)
    print(f"Rótulos largos: {len(largos)}")
    for aviso in largos:
        print(f"    {aviso}")


def main() -> None:
    entradas = construir_entradas_reales()
    imprimir_menu(entradas)
    informar(entradas)


if __name__ == "__main__":
    main()
