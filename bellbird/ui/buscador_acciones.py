"""Lo que se hace con un resultado elegido de la búsqueda.

Razón del módulo: ejecutar la acción pedida en el menú contextual sobre el
resultado o los resultados elegidos. Recibe dependencias por parámetro,
sin leer la página.
"""

from __future__ import annotations

import webbrowser

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.ui.gui import anunciar, copiar_al_portapapeles
from bellbird.voice import sound_player as _snd

logger = diagnostico.obtener_logger(__name__)

SITIOS_URL = "https://github.com/yt-dlp/yt-dlp/blob/master/supported_sites.md"

def textos() -> dict:
    """Los rótulos del menú, traducidos al pedirlos y no al importar."""
    return {
        "agregar": _("&Agregar a la cola"),
        "audio": _("Descargar como a&udio"),
        "video": _("Descargar como &vídeo"),
        "bellbird": _("Abrir en &Bellbird"),
        "musica": _("Agregar a la &música"),
        "contenido": _("Ver co&ntenido"),
        "copiar": _("&Copiar enlace"),
        "navegador": _("Abrir en el navega&dor"),
        "sitios": _("Ver &sitios compatibles"),
    }


def opciones_de(entrada, hay_bellbird, hay_musica) -> tuple:
    """Qué ofrece el menú para ese resultado o esos resultados.

    Un directo solo sirve en Bellbird, uno programado todavía no sirve
    para nada más que copiarlo, y con varios elegidos solo vale agregar
    si todos se pueden bajar.
    """
    if isinstance(entrada, (list, tuple)):
        resultados = list(entrada)
        if resultados and all(_descargable(r) for r in resultados):
            return ("agregar", "audio", "video", "sitios")
        return ("sitios",)
    resultado = entrada
    if resultado.programado:
        base = ("copiar", "navegador")
    elif resultado.en_directo:
        base = ("bellbird", "musica", "copiar", "navegador")
    elif resultado.tipo == "lista":
        base = ("contenido", "agregar", "musica", "copiar", "navegador")
    elif resultado.tipo == "canal":
        base = ("contenido", "copiar", "navegador")
    else:
        base = ("agregar", "audio", "video", "bellbird", "musica",
                "copiar", "navegador")
    if not hay_bellbird:
        base = tuple(o for o in base if o != "bellbird")
    if not hay_musica:
        base = tuple(o for o in base if o != "musica")
    return base + ("sitios",)


def _descargable(resultado) -> bool:
    """Un vídeo o una lista que se puede bajar ahora mismo."""
    if resultado.tipo not in ("video", "lista"):
        return False
    return not resultado.en_directo and not resultado.programado


def anunciar_agregados(cuantos: int) -> None:
    """Avisa cuántos enlaces entraron a la cola, si entró alguno."""
    if cuantos == 1:
        anunciar(_("Agregado a la cola"))
    elif cuantos > 1:
        anunciar(_("{cantidad} agregados a la cola").format(cantidad=cuantos))


def reparto_para_agregar(resultados) -> tuple[list, list]:
    """URLs para encolar y rechazos sin repetir, en el orden elegido."""
    urls, rechazos = [], []
    for resultado in resultados or []:
        if resultado.tipo == "canal":
            rechazos.append(_("Un canal no se puede agregar a la cola."))
        elif resultado.en_directo:
            rechazos.append(_("Un directo en curso no se puede descargar."))
        elif resultado.programado:
            rechazos.append(_("Este directo todavía no empezó."))
        else:
            urls.append(resultado.url)
    return urls, list(dict.fromkeys(rechazos))


def construir_menu(opciones, resultados, acciones, al_ver_contenido,
                   al_agregar):
    """El menú con esas opciones, actuando sobre esos resultados.

    `al_ver_contenido(resultado)` entra a la vista y `al_agregar(urls)`
    encola. Los sitios compatibles van siempre al final, separados.
    """
    menu = wx.Menu()
    unico = resultados[0] if len(resultados) == 1 else None
    llamadas = {
        "agregar": lambda: al_agregar([r.url for r in resultados]),
        "audio": lambda: acciones.como_audio(list(resultados)),
        "video": lambda: acciones.como_video(list(resultados)),
        "bellbird": lambda: acciones.en_bellbird(unico),
        "musica": lambda: acciones.a_musica(unico),
        "contenido": lambda: al_ver_contenido(unico),
        "copiar": lambda: acciones.copiar(unico),
        "navegador": lambda: acciones.abrir_en_navegador(unico),
        "sitios": lambda: acciones.ver_sitios(),
    }
    for opcion in opciones:
        if opcion == "sitios" and menu.GetMenuItemCount():
            menu.AppendSeparator()
        ident = wx.NewIdRef()
        menu.Append(ident, textos()[opcion])
        menu.Bind(wx.EVT_MENU, lambda _e, f=llamadas[opcion]: f(), id=ident)
    return menu


class AccionesResultado:
    """Ejecuta cada acción del menú sobre el resultado dado."""

    def __init__(self, agregar_urls, abrir_en_bellbird=None,
                 agregar_a_musica=None):
        self._agregar_urls = agregar_urls
        self._abrir_en_bellbird = abrir_en_bellbird
        self._agregar_a_musica = agregar_a_musica

    def copiar(self, resultado) -> None:
        if resultado is None:
            return
        copiar_al_portapapeles(resultado.url)
        try:
            _snd.reproducir("copiar")
        except Exception as error:
            logger.debug("sin sonido: %s", error)
        anunciar(_("Enlace copiado"))

    def abrir_en_navegador(self, resultado) -> None:
        if resultado is None:
            return
        try:
            webbrowser.open(resultado.url)
        except Exception as error:
            logger.debug("no se pudo abrir el navegador: %s", error)

    def ver_sitios(self, _resultado=None) -> None:
        try:
            webbrowser.open(SITIOS_URL)
        except Exception as error:
            logger.debug("no se pudo abrir el navegador: %s", error)

    def en_bellbird(self, resultado) -> None:
        if resultado is None or self._abrir_en_bellbird is None:
            return
        self._abrir_en_bellbird(resultado.url)

    def a_musica(self, resultado) -> None:
        if resultado is None or self._agregar_a_musica is None:
            return
        self._agregar_a_musica(resultado.url)

    def como_audio(self, resultados) -> None:
        self._agregar_urls(
            [r.url for r in resultados or []], formato="audio")

    def como_video(self, resultados) -> None:
        self._agregar_urls(
            [r.url for r in resultados or []], formato="video")
