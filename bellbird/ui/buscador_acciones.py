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
        "escuchar": _("&Escuchar"),
        "audio": _("Descargar como a&udio"),
        "video": _("Descargar como &vídeo"),
        "formato": _("Elegir &formato…"),
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
        base = ("agregar", "escuchar", "audio", "video", "formato", "bellbird",
                "musica", "copiar", "navegador")
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


def texto_agregados(cuantos, titulo=None, hay_turno=True) -> str:
    """Lo que se anuncia al agregar: lo que pasa de verdad. Función pura."""
    if cuantos != 1:
        return _("{cantidad} descargas agregadas").format(cantidad=cuantos)
    if hay_turno:
        if titulo:
            return _("Descargando: {titulo}").format(titulo=titulo)
        return _("Descargando")
    if titulo:
        return _("En cola: {titulo}").format(titulo=titulo)
    return _("En cola")


def anunciar_agregados(cuantos, titulo=None, hay_turno=True) -> None:
    """Avisa lo que pasó al agregar, si entró algo, con su sonido."""
    if not cuantos:
        return
    anunciar(texto_agregados(cuantos, titulo, hay_turno))
    try:
        _snd.reproducir("descarga_encolada")
    except Exception as error:
        logger.debug("sin sonido: %s", error)


def titulo_para_anunciar(resultados):
    """El título para el anuncio de agregado, o None si no hay uno solo.

    Solo con un vídeo solo se conoce el título; con varios elegidos, con
    una lista entera o con un enlace pegado se anuncia sin título.
    """
    if len(resultados) == 1 and resultados[0].tipo == "video":
        return resultados[0].titulo or None
    return None


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


def _llamadas_menu(resultados, unico, acciones, al_ver_contenido,
                 al_agregar, al_escuchar):
    """Qué hace cada opción del menú sobre esos resultados."""
    return {
        "agregar": lambda: al_agregar(
            [r.url for r in resultados], titulo=titulo_para_anunciar(resultados)),
        "escuchar": lambda: al_escuchar(unico),
        "audio": lambda: acciones.como_audio(list(resultados)),
        "video": lambda: acciones.como_video(list(resultados)),
        "formato": lambda: acciones.elegir_formato(unico),
        "bellbird": lambda: acciones.en_bellbird(unico),
        "musica": lambda: acciones.a_musica(unico),
        "contenido": lambda: al_ver_contenido(unico),
        "copiar": lambda: acciones.copiar(unico),
        "navegador": lambda: acciones.abrir_en_navegador(unico),
        "sitios": lambda: acciones.ver_sitios(),
    }


def construir_menu(opciones, resultados, acciones, al_ver_contenido,
                   al_agregar, al_escuchar=None):
    """El menú con esas opciones, actuando sobre esos resultados.

    `al_ver_contenido(resultado)` entra a la vista, `al_agregar(urls,
    titulo)` encola y `al_escuchar(resultado)` escucha la previa. Los
    sitios compatibles van siempre al final, separados.
    """
    menu = wx.Menu()
    unico = resultados[0] if len(resultados) == 1 else None
    llamadas = _llamadas_menu(resultados, unico, acciones, al_ver_contenido,
                              al_agregar, al_escuchar)
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
        self._consulta_formato = None

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
            [r.url for r in resultados or []], formato="audio",
            titulo=titulo_para_anunciar(resultados or []))

    def como_video(self, resultados) -> None:
        self._agregar_urls(
            [r.url for r in resultados or []], formato="video",
            titulo=titulo_para_anunciar(resultados or []))

    def elegir_formato(self, resultado) -> None:
        from bellbird.ui import elegir_formato
        # Una sola consulta por página: si se creara una por llamada, el
        # aviso de consulta en curso nunca actuaría.
        if self._consulta_formato is None:
            self._consulta_formato = elegir_formato.ConsultaFormatos(
                self._agregar_urls)
        self._consulta_formato.pedir(resultado)
